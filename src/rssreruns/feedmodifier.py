"""Modify a given XML-based feed (RSS or Atom)."""

import copy
import email.utils
import random
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests
from dateutil import parser
from lxml import etree as ET

from .elementwrapper import ElementWrapper, ElementWrapperFactory

# Underscores present because those are the class names in lxml.etree
Element = ET._Element
ElementTree = ET._ElementTree
QName = ET.QName


class FeedModifier(ABC):
    """Modify a given XML-based feed.

    Concrete subclasses correspond to the specific kind of feed, i.e. RSS or Atom.
    """

    def __init__(
        self,
        path: str | Path,
        schedule_kwargs: Optional[Any] = None,
        run_forever: Optional[bool] = None,
        title_kwargs: dict[str, Any] = {},
        entry_title_kwargs: dict[str, str] = {},
    ) -> None:
        """Initialization."""
        self.path: Path = Path(path)

        # If blank text is preserved, then `ET.write` will not properly indent
        # any newly added elements which contain text, even with pretty printing.
        # However, if the parser removes blank text, then `write()` will add new
        # indentation to the entire document, so all elements wil be properly indented
        # (if pretty printing is enabled.)
        #
        # See: "Why doesn't the pretty_print option reformat my XML output?"
        # lxml.de/FAQ.html#why-doesn-t-the-pretty-print-option-reformat-my-xml-output
        parser = ET.XMLParser(remove_blank_text=True, strip_cdata=False)
        self._tree: ElementTree = ET.parse(self.path, parser=parser)
        root = self._tree.getroot()

        # Prefix and URI for the `reruns` XML namespace
        self._ns_prefix = "reruns"
        self._ns_uri = "https://github.com/hannahlog/rss-reruns"

        # Local names of elements containing feed and entry data
        self._meta_channel_tag = f"{self._ns_prefix}:channel_data"
        self._meta_entry_tag = f"{self._ns_prefix}:entry_data"

        # Declaration added to the root element as
        #   `xmlns:reruns="https://github.com/hannahlog/rss-reruns"`
        self.add_namespace(prefix=self._ns_prefix, uri=self._ns_uri)
        self._nsmap = self._clean_nsmap(root.nsmap)

        self._default_EWF = ElementWrapperFactory("" if "" in self._nsmap else None)
        self._root: ElementWrapper = self._default_EWF(root)

        # Element containing metadata and entry/item elements:
        # `feed` for Atom (which is also the root), `channel` for RSS (not the root)
        self._channel: ElementWrapper = self.feed_channel()

        # Subelement of the channel containing data and settings for the FeedModifier
        self._meta_channel: ElementWrapper = self._channel[self._meta_channel_tag]

        # Default meta channel values:
        meta_channel_defaults = {
            "order": "chronological",
            "rate": "1",
            "run_forever": "True",
            "original_title": self._channel["title"].text or "",
            "title_prefix": "[Reruns:]",
            "title_suffix": None,
            "entry_title_prefix": "[Rerun:]",
            "entry_title_suffix": "(Originally published: %b %d %Y)",
        }
        self._create_defaults_if_missing(self._meta_channel, meta_channel_defaults)

        # Default meta entry values:
        for entry in self.feed_entries():
            entry_meta = entry[self._meta_entry_tag]
            meta_entry_defaults = {
                "original_pubdate": self.get_entry_pubdate(entry),
                "original_title": entry["title"].text or "",
                "reran": "False",
            }
            self._create_defaults_if_missing(entry_meta, meta_entry_defaults)

        if run_forever is not None:
            self.run_forever = run_forever

        self.set_feed_title(**title_kwargs)
        self.set_entry_titles(**entry_title_kwargs)

    def _clean_nsmap(self, nsmap: dict[Optional[str], str]) -> dict[str, str]:
        """Replace `None` keys with empty strings."""
        return {(k or ""): v for k, v in nsmap.items()}

    def add_namespace(self, prefix: str, uri: str) -> None:
        """Add the given namespace to the root element (if not already present)."""
        nsmap = {k: v for k, v in self._tree.getroot().nsmap.items() if k}
        nsmap[prefix] = uri

        # All pre-existing namespaces are kept.
        # If a default namespace was present, it will be kept, even though it
        # is not included here in nsmap or all_prefixes.
        all_prefixes = list(nsmap)
        ET.cleanup_namespaces(
            self._tree, top_nsmap=nsmap, keep_ns_prefixes=all_prefixes
        )
        pass

    def _create_defaults_if_missing(
        self, parent: ElementWrapper, defaults: dict[str, Optional[str]]
    ) -> None:
        """Create subelements with given text only if the subelement does not exist."""
        for tag, text in defaults.items():
            # Defaults do not override already-existing elements or their texts.
            # Specifically, if the subelement already exists with no text (<tag/>),
            # then this will preserve the subelement having no text.
            # E.g. a modified feed that previously had entry_title_prefix set
            # to None will remain that way:
            #   `<reruns:entry_title_prefix/>`
            # Preseving such None-text is why it is written this way, and not
            #   `parent[tag].text = parent[tag].text or text`
            # which would overwrite "" as well as None.
            if tag not in parent:
                parent[tag].text = text

    @classmethod
    def from_url(
        cls, url, path=None, feed_format=None, *args, **kwargs
    ) -> "FeedModifier":
        """Create a FeedModifier from a given source feed's url."""
        saved_path = cls.url_to_file(url, path)
        kwargs["source_url"] = url
        return cls.from_file(saved_path, *args, **kwargs)

    @classmethod
    def from_file(cls, path, feed_format=None, *args, **kwargs) -> "FeedModifier":
        """Create a FeedModifier from a given source feed's path."""
        if feed_format is not None:
            concrete_subclass = (
                RSSFeedModifier if "rss" in feed_format.lower() else AtomFeedModifier
            )
        else:
            concrete_subclass = cls._infer_format(path)

        return concrete_subclass(path, *args, **kwargs)

    @classmethod
    def _infer_format(cls, path: str | Path) -> type["FeedModifier"]:
        """Guess the format, RSS or Atom, of a given feed file."""
        path = Path(path)
        if not (path.exists() and path.is_file()):
            raise ValueError(f"Given path does not refer to a feed file: {path}")

        # Trust the file extension if it specifies .rss or .atom
        if ".rss" in [suffix.lower() for suffix in path.suffixes]:
            return RSSFeedModifier
        elif ".atom" in [suffix.lower() for suffix in path.suffixes]:
            return AtomFeedModifier

        # Otherwise, parse the file
        # TODO: Wasteful to parse the entire file just to infer the feed's
        # format -- find less wasteful solution?
        # (To just check the root element?)
        root: Element = ET.parse(path).getroot()

        if "rss" in root.tag.lower():
            return RSSFeedModifier
        elif "feed" in root.tag.lower():
            return AtomFeedModifier
        else:
            raise ValueError(
                f"Format of file {path} could not be determined. "
                f"Root element: {root.tag}"
            )

    @staticmethod
    def url_to_file(url: str, path: Optional[str | Path] = None) -> Path:
        """Download and save XML from given URL."""
        path = Path(path or "downloads/feed.xml")
        response = requests.get(url)
        if not response.ok:
            raise ValueError(
                f"Requested url {url} returned status code: {response.status_code}"
            )

        path.parents[0].mkdir(exist_ok=True, parents=True)
        with open(path, "wb") as f:
            f.write(response.content)
        return path

    @property
    def run_forever(self):
        """Getter function for retrieving `forever` text from the etree."""
        return self._meta_channel["run_forever"].text.lower() == "true"

    @run_forever.setter
    def run_forever(self, forever: bool | str):
        """Setter function for setting `forever` text in the etree."""
        if str(forever).capitalize() in {"True", "False"}:
            self._meta_channel["run_forever"].text = str(forever).capitalize()
        else:
            raise ValueError(
                f"Invalid value {forever} for `forever`: expected True or False."
            )
        pass

    def __getitem__(self, name) -> str:
        """Access meta channel subelements as if they're items of the FeedModifier."""
        return self._meta_channel[name].text

    def __setitem__(self, name, value):
        """Access meta channel subelements as if they're items of the FeedModifier."""
        self._meta_channel[name].text = value
        pass

    def __delitem__(self, name):
        """Access meta channel subelements as if they're items of the FeedModifier."""
        del self._meta_channel[name]
        pass

    def set_feed_title(
        self,
        *,
        prefix: str | None = None,
        suffix: str | None = None,
    ) -> str:
        """Specify the new feed's title by a prefix and suffix string.

        TODO: Functionality overhauled: rewrite docstring.

        The new title may be specified through exactly one of the keyword arguments:
        `title` to give an exact string, `prefix` to prepend a string to the original
        title, or `func` to provide a function that, given the old title as a string,
        creates a new title string.

        Args:
            prefix (str | None):
                String to prepend to the original title.
            suffix (str | None):
                Suffix to append to the original title.

        Returns:
            str: the title of the republished feed, as it will be written to file.
        """
        # Set the new prefix and suffix strings if given
        if prefix:
            self["title_prefix"] = prefix
        if suffix:
            self["title_suffix"] = suffix

        new_title_list: list[str] = [
            part_text
            for part in (
                "title_prefix",
                "original_title",
                "title_suffix",
            )
            if part in self._meta_channel
            and (part_text := self._meta_channel[part].text) is not None
        ]
        self._channel["title"].text = " ".join(new_title_list)
        return self._channel["title"]

    def set_entry_titles(
        self, prefix: Optional[str] = None, suffix: Optional[str] = None
    ):
        """Set the entry titles."""
        # Set the new prefix and suffix strings if given
        if prefix:
            self["entry_title_prefix"] = prefix
        if suffix:
            self["entry_title_suffix"] = suffix
        for entry in self.feed_entries():
            # TODO: This is unacceptably sloppy. Organize and make this readable.
            # Consider refactoring somehow.
            meta_entry = entry[self._meta_entry_tag]

            # Initialize dict of the title parts that exist
            part_keys = ("entry_title_prefix", "original_title", "entry_title_suffix")
            part_parents = (self._meta_channel, meta_entry, self._meta_channel)
            title_parts: dict[str, str] = {
                part: part_text
                for part, parent in zip(part_keys, part_parents)
                if part in parent and (part_text := parent[part].text) is not None
            }

            # Apply the original date to the prefix and/or suffix if the original date
            # is available
            original_date = meta_entry["original_pubdate"].text
            if original_date is not None:
                dt = parser.parse(original_date)
                affixes = {"entry_title_prefix", "entry_title_suffix"}.intersection(
                    title_parts
                )
                for affix in affixes:
                    title_parts[affix] = dt.strftime(title_parts[affix])

            title_list: list[str] = [title_parts[part] for part in part_keys]
            entry["title"].text = " ".join(title_list)
        pass

    def _entries_to_rerun(self) -> list[ElementWrapper]:
        """Entries that have not yet been rebroadcast."""
        not_reran = [
            self._default_EWF(meta_entry.getparent())
            for meta_entry in self._feed_meta_entries()
            if meta_entry["reran"].text.lower() == "false"
        ]

        if len(not_reran) == 0 and self.run_forever:
            self._mark_all_not_reran()
            return self.feed_entries()
        else:
            return not_reran

    def _feed_meta_entries(self) -> list[ElementWrapper]:
        """Returns iterator over the meta subelements of the feed's entries."""
        return [entry[self._meta_entry_tag] for entry in self.feed_entries()]

    def _mark_all_not_reran(self) -> None:
        """Mark all entries as not having been rebroadcast yet."""
        for meta_entry in self._feed_meta_entries():
            meta_entry["reran"].text = "False"
        pass

    def rebroadcast(
        self, num: int = 1, use_datetime: Optional[datetime | str] = None
    ) -> list[ElementWrapper]:
        """Update the publication date for the given number of entries."""
        if num < 0:
            raise ValueError(f"Cannot select negative number of entries: {num}")

        reran = []
        remaining = num
        while remaining > 0:
            entries = self._entries_to_rerun()
            if remaining >= len(entries):
                for entry in entries:
                    self._rebroadcast_entry(entry, use_datetime)
                reran += entries
                remaining -= len(entries)
            else:
                if self._meta_channel["order"].text.lower() == "chronological":
                    entries.sort(key=self.get_entry_original_pubdate)
                else:
                    random.shuffle(entries)
                for i in range(remaining):
                    self._rebroadcast_entry(entries[i], use_datetime)
                reran += entries[0:remaining]
                remaining = 0
        return reran

    def _rebroadcast_entry(
        self, entry: ElementWrapper, use_datetime: Optional[datetime | str] = None
    ) -> None:
        """AAAAAAAAAAAA."""
        if use_datetime is None:
            dt = datetime.now(timezone.utc)
        else:
            dt = (
                use_datetime
                if isinstance(use_datetime, datetime)
                else parser.parse(use_datetime)
            )
        self.update_entry_pubdate(entry, dt)
        entry[self._meta_entry_tag]["reran"].text = "True"

    def write(
        self,
        path: str | Path,
        with_reruns_data: bool = True,
        use_datetime: Optional[datetime | str] = None,
    ) -> None:
        """Write modified feed (RSS or Atom) to XML file."""
        # Update when the feed itself was last built before writing out
        if use_datetime is None:
            dt = datetime.now(timezone.utc)
        else:
            dt = (
                use_datetime
                if isinstance(use_datetime, datetime)
                else parser.parse(use_datetime)
            )
        self.update_feed_builddate(dt)

        if with_reruns_data:
            self._tree.write(
                path, pretty_print=True, xml_declaration=True, encoding="utf-8"
            )
        else:
            stripped_tree = copy.deepcopy(self._tree)
            stripped_root = stripped_tree.getroot()

            # Remove `reruns` elements from the tree's copy
            ET.strip_elements(
                stripped_tree,
                self._meta_entry_tag.split(":")[1],
                self._meta_channel_tag.split(":")[1],
            )

            # Remove `reruns` namespace declaration
            nsmap: dict[str, str] = {
                k: v
                for k, v in stripped_root.nsmap.items()
                if k is not None and k != self._ns_prefix
            }
            ET.cleanup_namespaces(
                stripped_tree, top_nsmap=nsmap, keep_ns_prefixes=list(nsmap)
            )
            stripped_tree.write(
                path, pretty_print=True, xml_declaration=True, encoding="utf-8"
            )
        pass

    def get_entry_original_pubdate(self, entry: ElementWrapper) -> datetime:
        """Get a given entry/item's original date of publication."""
        original_date = entry[self._meta_entry_tag]["original_pubdate"].text
        if original_date is None:
            raise ValueError("Entry missing original_pubdate")
        return parser.parse(original_date)

    @abstractmethod
    def feed_channel(self) -> ElementWrapper:
        """Returns the `feed` (Atom) or `channel` (RSS) element of the tree."""
        pass

    @abstractmethod
    def feed_entries(self) -> list[ElementWrapper]:
        """Returns iterator over the feed's entry/item elements."""
        pass

    @abstractmethod
    def get_entry_pubdate(self, entry: ElementWrapper) -> Optional[str]:
        """Get a given entry/item's date of publication."""
        pass

    @abstractmethod
    def update_entry_pubdate(
        self, entry: ElementWrapper, date: datetime
    ) -> list[ElementWrapper]:
        """Update a given entry/item's date of publication."""
        pass

    @abstractmethod
    def update_feed_builddate(self, date: datetime) -> list[ElementWrapper]:
        """Update the feed's datetime of last publication."""
        pass

    @staticmethod
    @abstractmethod
    def format_datetime(date: datetime) -> str:
        """Format a datetime as a string, in the format to be written to file."""
        pass


class RSSFeedModifier(FeedModifier):
    """Modify a given RSS feed."""

    def feed_channel(self) -> ElementWrapper:
        """Returns the `feed` (Atom) or `channel` (RSS) element of the tree."""
        # For RSS, the `channel` element is a child of the root `rss` element
        channel = self._default_EWF(self._root)["channel"]
        if channel is None:
            raise ValueError("RSS feed must contain `channel` element (not found).")
        else:
            return channel

    def feed_entries(self) -> list[ElementWrapper]:
        """Returns iterator over the feed's item elements."""
        return self._channel.iterfind("item")

    def get_entry_pubdate(self, entry: ElementWrapper) -> Optional[str]:
        """Get a given entry/item's date of publication."""
        pubdate = entry["pubDate"]
        if pubdate is not None:
            return pubdate.text
        raise ValueError(f"RSS entry has no 'pubdate': {entry._element}")

    def update_entry_pubdate(
        self, entry: ElementWrapper, date: datetime
    ) -> list[ElementWrapper]:
        """Update a given entry/item's date of publication."""
        formatted_date: str = self.format_datetime(date)
        entry["pubDate"].text = formatted_date
        return [entry["pubDate"]]

    def update_feed_builddate(self, date: datetime) -> list[ElementWrapper]:
        """Update the feed's datetime of last publication."""
        # For RSS, this updates the channel's `lastBuildDate` and `pubDate`
        formatted_date: str = self.format_datetime(date)
        self._channel["pubDate"].text = formatted_date
        self._channel["lastBuildDate"].text = formatted_date
        return [self._channel["pubDate"], self._channel["lastBuildDate"]]

    @staticmethod
    def format_datetime(date: datetime) -> str:
        """Format a datetime as a string, in the format required for RSS.

        The RSS 2.0 specification stipulates:

        "All date-times in RSS conform to the Date and Time Specification of RFC 822,
        with the exception that the year may be expressed with two characters or four
        characters (four preferred)."
        (https://www.rssboard.org/rss-specification)

        The functions `formatdate` and `format_datetime` in `emails.util` conform to
        RFC 2822, which means their datetimes conform to RFC 822.
        (https://docs.python.org/3/library/email.utils.html#email.utils.format_datetime)

        `format_datetime`is used below for our purposes.

        Args:
            date (datetime):
                Date to be formatted.

        Returns:
            str: correctly-formatted string representing the datetime.
        """
        return email.utils.format_datetime(date)


class AtomFeedModifier(FeedModifier):
    """Modify a given Atom feed."""

    def feed_channel(self) -> ElementWrapper:
        """Returns the `feed` (Atom) or `channel` (RSS) element of the tree."""
        # For Atom, the `feed` element is the root itself
        return self._default_EWF(self._root)

    def feed_entries(self) -> list[ElementWrapper]:
        """Returns iterator over the feed's entry elements."""
        return self._default_EWF(self._root).iterfind("entry")

    def get_entry_pubdate(self, entry: ElementWrapper) -> Optional[str]:
        """Get a given entry/item's date of publication."""
        if "updated" in entry:
            return entry["updated"].text
        elif "published" in entry:
            return entry["published"].text
        raise ValueError(
            f"Atom entry has no 'updated' nor 'published': {entry._element}"
        )

    def update_entry_pubdate(
        self, entry: ElementWrapper, date: datetime
    ) -> list[ElementWrapper]:
        """Update a given entry/item's date of publication."""
        formatted_date: str = self.format_datetime(date)
        entry["published"].text = formatted_date
        entry["updated"].text = formatted_date
        return [entry["published"], entry["updated"]]

    def update_feed_builddate(self, date: datetime) -> list[ElementWrapper]:
        """Update the feed's datetime of last publication."""
        # For Atom, this updates the channel's `updated` element
        formatted_date: str = self.format_datetime(date)
        self._channel["updated"] = formatted_date
        return [self._channel["updated"]]

    @staticmethod
    def format_datetime(date: datetime) -> str:
        """Format a datetime as a string, in the format required for Atom.

        The Atom specification stipulates:

        "A Date construct is an element whose content MUST conform to the "date-time"
        production in [RFC3339].  In addition, an uppercase "T" character MUST be used
        to separate date and time, and an uppercase "Z" character MUST be present in the
        absence of a numeric time zone offset. [...]

        Such date values happen to be compatible with the following specifications:
        [ISO.8601.1988], [W3C.NOTE-datetime-19980827], and
        [W3C.REC-xmlschema-2-20041028]."

        (https://datatracker.ietf.org/doc/html/rfc4287#section-3.3)

        Args:
            date (datetime):
                Date to be formatted.

        Returns:
            str: correctly-formatted string representing the datetime.
        """
        return date.isoformat("T").replace("+00:00", "Z")


if __name__ == "__main__":
    pass
