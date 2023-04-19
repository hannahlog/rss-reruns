"""Modify a given XML-based feed (RSS or Atom)."""
from __future__ import annotations

import copy
import email.utils
import random
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
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

    _bool_attributes = {"run_forever", "overwrite_entry_ids"}

    def __init__(
        self,
        path: str | Path | None,
        contents: str | bytes | None = None,
        schedule_kwargs: Optional[Any] = None,
        run_forever: Optional[bool] = None,
        initialize_all_pubdates: bool = False,
        overwrite_self_link: str | None = None,
        overwrite_entry_ids: bool | None = None,
        title_kwargs: dict[str, Any] = {},
        entry_title_kwargs: dict[str, str] = {},
    ) -> None:
        """Initialization."""
        if path is None and contents is None:
            raise ValueError("Arguments path and contents cannot both be None.")

        self.path = Path(path) if path is not None else None

        self._tree: ElementTree = self._parse_file_or_string(
            path=path, contents=contents
        )

        # Prefix and URI for the `reruns` XML namespace
        self._ns_prefix = "reruns"
        self._ns_uri = "https://github.com/hannahlog/rss-reruns"

        # Local names of elements containing feed and entry data
        self._meta_channel_tag = f"{self._ns_prefix}:channel_data"
        self._meta_entry_tag = f"{self._ns_prefix}:entry_data"

        # Declaration added to the root element as
        #   `xmlns:reruns="https://github.com/hannahlog/rss-reruns"`
        self.add_namespace(prefix=self._ns_prefix, uri=self._ns_uri)

        self._default_EWF = ElementWrapperFactory("" if "" in self._nsmap else None)
        self._root: ElementWrapper = self._default_EWF(self._tree.getroot())

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
            "original_self_link": self.source_url(),
            "overwrite_entry_ids": "False",
            "title_prefix": None,
            "title_suffix": None,
            "entry_title_prefix": None,
            "entry_title_suffix": None,
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
            if initialize_all_pubdates:
                self.update_entry_pubdate(entry, datetime.now(timezone.utc))

        if run_forever is not None:
            self["run_forever"] = run_forever

        if overwrite_entry_ids is not None:
            self["overwrite_entry_ids"] = overwrite_entry_ids

        if overwrite_self_link:
            self._overwrite_self_link(new_self_link=overwrite_self_link)

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
        self._nsmap = self._clean_nsmap(self._tree.getroot().nsmap)
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
    def _parse_file_or_string(cls, path=None, contents=None) -> ElementTree:
        """Parse from filepath or string."""
        # If blank text is preserved, then `ET.write` will not properly indent
        # any newly added elements which contain text, even with pretty printing.
        # However, if the parser removes blank text, then `write()` will add new
        # indentation to the entire document, so all elements wil be properly indented
        # (if pretty printing is enabled.)
        #
        # See: "Why doesn't the pretty_print option reformat my XML output?"
        # lxml.de/FAQ.html#why-doesn-t-the-pretty-print-option-reformat-my-xml-output
        parser = ET.XMLParser(remove_blank_text=True, strip_cdata=False)
        if path is not None:
            # base_url="" is needed to prevent lxml from using the document's filepath
            # as an implicit base URI if no `xml:base` is declared
            return ET.parse(path, parser=parser, base_url="")
        elif contents is not None:
            return ET.fromstring(contents, parser=parser).getroottree()
        else:
            raise ValueError("Either path or contents must not be None.")

    @classmethod
    def from_url(cls, url, *, path=None, feed_format=None, **kwargs) -> "FeedModifier":
        """Create a FeedModifier from a given source feed's url."""
        if path is not None:
            saved_path = cls.url_to_file(url, path)
            kwargs.pop("url", None)
            return cls.from_file(saved_path, **kwargs)
        else:
            contents = cls.url_to_contents(url)
            kwargs.pop("url", None)
            return cls.from_string(contents, **kwargs)

    @classmethod
    def from_string(
        cls, contents: str | bytes, *, feed_format=None, **kwargs
    ) -> "FeedModifier":
        """Create a FeedModifier from a given source feed's string."""
        if feed_format is not None:
            concrete_subclass = (
                RSSFeedModifier if "rss" in feed_format.lower() else AtomFeedModifier
            )
        else:
            concrete_subclass = cls._infer_format_from_contents(
                path=None, contents=contents
            )

        kwargs.pop("feed_format", None)
        kwargs.pop("path", None)
        kwargs.pop("contents", None)
        return concrete_subclass(path=None, contents=contents, **kwargs)

    @classmethod
    def from_file(cls, path, *, feed_format=None, **kwargs) -> "FeedModifier":
        """Create a FeedModifier from a given source feed's path."""
        if feed_format is not None:
            concrete_subclass = (
                RSSFeedModifier if "rss" in feed_format.lower() else AtomFeedModifier
            )
        else:
            concrete_subclass = cls._infer_format(path)

        kwargs.pop("feed_format", None)
        return concrete_subclass(path, **kwargs)

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

        # Otherwise, inspect the actual contents
        try:
            return cls._infer_format_from_contents(path=path)
        except ValueError as e:
            raise ValueError(f"Format of file {path} could not be determined.") from e

    @classmethod
    def _infer_format_from_contents(
        cls, path=None, contents=None
    ) -> type["FeedModifier"]:
        """Guess the format, RSS or Atom, of a given feed from its string contents."""
        # TODO: Wasteful to parse the entire file just to infer the feed's
        # format -- find less wasteful solution?
        # (To just check the root element?)
        root: Element = cls._parse_file_or_string(
            path=path, contents=contents
        ).getroot()

        if "rss" in root.tag.lower():
            return RSSFeedModifier
        elif "feed" in root.tag.lower():
            return AtomFeedModifier
        else:
            raise ValueError(
                f"Format of feed could not be determined. " f"Root element: {root.tag}"
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

    @staticmethod
    def url_to_contents(url: str) -> bytes:
        """Download XML from given URL."""
        response = requests.get(url)
        if not response.ok:
            raise ValueError(
                f"Requested url {url} returned status code: {response.status_code}"
            )
        return response.content

    def __getitem__(self, name) -> str:
        """Access meta channel subelements as if they're items of the FeedModifier."""
        if name in self._meta_channel:
            text = self._meta_channel[name].text
        elif name in self._channel:
            text = self._channel[name].text
        else:
            raise KeyError(name)
        return text if name not in self._bool_attributes else bool(text)

    def __setitem__(self, name, value):
        """Access meta channel subelements as if they're items of the FeedModifier."""
        if name in self._bool_attributes and str(value).capitalize() not in {
            "True",
            "False",
        }:
            raise ValueError(
                f"Invalid value {value} for attribute {name}: expected True or False."
            )
        self._meta_channel[name].text = (
            value if name not in self._bool_attributes else str(value).capitalize()
        )
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
            self._meta_channel[tag].text
            for tag in (
                "title_prefix",
                "original_title",
                "title_suffix",
            )
            if tag in self._meta_channel and self._meta_channel[tag].text is not None
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
            tags = ("entry_title_prefix", "original_title", "entry_title_suffix")
            parents = (self._meta_channel, meta_entry, self._meta_channel)
            title_parts: dict[str, str] = {
                tag: parent[tag].text
                for tag, parent in zip(tags, parents)
                if tag in parent and parent[tag].text
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

            title_list: list[str] = list(title_parts.values())
            entry["title"].text = " ".join(title_list)
        pass

    def num_remaining(self) -> int:
        """Number of entries that have not yet been rebroadcast."""
        return len(self._entries_to_rerun())

    def _entries_to_rerun(self) -> list[ElementWrapper]:
        """Entries that have not yet been rebroadcast."""
        not_reran = [
            self._default_EWF(meta_entry.getparent())
            for meta_entry in self._feed_meta_entries()
            if meta_entry["reran"].text.lower() == "false"
        ]

        if len(not_reran) == 0 and self["run_forever"]:
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
        self._update_entry_uuid(entry)
        entry[self._meta_entry_tag]["reran"].text = "True"

    def write(
        self,
        path: str | Path | None,
        with_reruns_data: bool = True,
        pretty_print: bool = True,
        use_datetime: datetime | str | None = None,
    ) -> str:
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

        # If reruns metadata is included, write out the original tree
        tree_to_write = self._tree
        if not with_reruns_data:
            # Otherwise, make a stripped copy of the tree
            stripped_tree = copy.deepcopy(self._tree)
            stripped_root = stripped_tree.getroot()

            # Remove entries marked as not having been rebroadcasted
            for meta_entry in self._default_EWF(stripped_root).iterdescendants(
                self._meta_entry_tag
            ):
                entry = self._default_EWF(meta_entry.getparent())

                # (Unless the entry was rebroadcasted recently -- i.e. if the entry
                # was just rebroadcasted, but all of the feed's entries were exhausted,
                # so all entries were marked as not having been rebroadcasted again)
                # (TODO: change logic of `_mark_all_not_reran` or `_entries_to_rerun` so
                # this check isn't necessary)
                if (meta_entry["reran"].text.lower() == "false") and abs(
                    parser.parse(self.get_entry_pubdate(entry))
                    - datetime.now(timezone.utc)
                ) > timedelta(days=1):
                    entry.getparent().remove(entry._element)

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

            tree_to_write = stripped_tree

        if path is not None:
            tree_to_write.write(
                path,
                pretty_print=pretty_print,
                xml_declaration=True,
                encoding="utf-8",
            )
        return ET.tounicode(
            tree_to_write,
            pretty_print=pretty_print,  # xml_declaration=True, encoding="utf-8"
        )

    def to_string(self, **kwargs) -> str:
        """Output the tree as a string. See `write` for optional kwargs."""
        return self.write(path=None, **kwargs)

    def get_entry_original_pubdate(self, entry: ElementWrapper) -> datetime:
        """Get a given entry/item's original date of publication."""
        original_date = entry[self._meta_entry_tag]["original_pubdate"].text
        if original_date is None:
            raise ValueError("Entry missing original_pubdate")
        return parser.parse(original_date)

    def feed_type(self) -> str:
        """Returns the feed format, "RSS" or "Atom".

        NOTE: Relies on the class name of the concrete instance. If more subclasses
        are made without 'RSS' or 'Atom' in the class name, for some other XML-based
        syndication format (lol), that subclass should override this method.
        """
        if "rss" in self.__class__.__name__.lower():
            return "RSS"
        elif "atom" in self.__class__.__name__.lower():
            return "Atom"
        else:
            raise RuntimeError(
                f"Feed format of {self} instance could not be determined."
            )

    def _absolute_url(self, entry: ElementWrapper) -> str:
        """Resolve a relative url and its base url into an absolute url."""
        return entry.href if not entry.base else "".join([entry.base, entry.href])

    def _generate_entry_uuid(self, entry: ElementWrapper) -> str:
        """Generate a UUID for a given entry.

        The generated UUID will not be the same as the atom:id or rss:guid for the entry
        (if one is already present.)

        It may not technically be "correct" to replace an item's existing uuid if one
        considers the republished entry to be "the same" as the original. Unfortunately,
        some feed readers cache the entry's information (including publication date)
        with the uuid as the key -- as a result, the reader won't recognize that an
        entry has had its publication date changed if the entry's uuid remains the same.
        """
        return uuid.uuid4().urn

    @abstractmethod
    def _update_entry_uuid(self, entry: ElementWrapper) -> ElementWrapper:
        """Update the entry's uuid (the guid or id for RSS or Atom respectively).

        Returns the element (<guid> or <id>) containing the new uuid.
        """
        pass

    @abstractmethod
    def feed_channel(self) -> ElementWrapper:
        """Returns the `feed` (Atom) or `channel` (RSS) element of the tree."""
        pass

    @abstractmethod
    def feed_entries(self) -> list[ElementWrapper]:
        """Returns iterator over the feed's entry/item elements."""
        pass

    @abstractmethod
    def get_entry_pubdate(self, entry: ElementWrapper) -> str:
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

    @abstractmethod
    def source_url(self) -> str:
        """Return the original feed's url."""
        pass

    @abstractmethod
    def _overwrite_self_link(self, new_self_link: str) -> None:
        """Create or write over the url of the `<atom:link rel='self'/>` element."""
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

    def get_entry_pubdate(self, entry: ElementWrapper) -> str:
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

    def source_url(self) -> str:
        """Return the original feed's url."""
        return self._channel["link"].text

    def _overwrite_self_link(self, new_self_link: str) -> None:
        """Create or write over the url of the `<atom:link rel='self'/>` element."""
        if "atom" not in self._nsmap:
            self.add_namespace(prefix="atom", uri="http://www.w3.org/2005/Atom")

        # Per w3c recommendations for RSS:
        # https://validator.w3.org/feed/docs/warning/MissingAtomSelfLink.html
        atom_link = self._channel["atom", "link"]
        self._channel["link"].addprevious(atom_link._element)
        atom_link.clear_xml_base()
        atom_link.href = new_self_link
        atom_link.rel = "self"
        atom_link.type = "application/rss+xml"

    def _update_entry_uuid(self, entry: ElementWrapper) -> ElementWrapper:
        """Update the entry's uuid in the <guid> subelement.

        Returns the subelement containing the new uuid.
        """
        entry["guid"].text = self._generate_entry_uuid(entry)
        entry["guid"].isPermaLink = "false"
        return entry["guid"]

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

    def get_entry_pubdate(self, entry: ElementWrapper) -> str:
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

    def source_url(self) -> str:
        """Return the original feed's url."""
        if "original_self_link" in self._meta_channel:
            return self._meta_channel["original_self_link"].text
        links = self._channel.iterfind("link")
        # An Atom feed may have multiple link elements, and "SHOULD" have one
        # link element with the attribute `rel="self"`.
        # (See RFC 4287:
        # https://datatracker.ietf.org/doc/html/rfc4287#section-4.1.1)
        self_links = [link for link in links if link.rel == "self"]
        if links:
            link = (self_links or links)[0]
        else:
            # TODO: not actually a ValueError
            raise ValueError("Atom feed contains no feed link element.")

        # The only reason to not just immediately return
        #
        #    (self_links or links)[0].href
        #
        # in the above is edge cases resolving uris relative to xml:base
        return self._absolute_url(link)

    def _overwrite_self_link(self, new_self_link: str) -> None:
        """Create or write over the url of the `<atom:link rel='self'/>` element."""
        links = self._channel.iterfind("link")
        self_links = [link for link in links if link.rel == "self"]
        self_link = (
            self_links[0] if self_links else self._channel.create_subelement("link")
        )
        if not self_links:
            links[0].addprevious(self_link._element)

        self_link.clear_xml_base()
        self_link.href = new_self_link
        self_link.rel = "self"
        self_link.type = "application/atom+xml"

    def _update_entry_uuid(self, entry: ElementWrapper) -> ElementWrapper:
        """Update the entry's uuid in the <id> subelement.

        Returns the subelement containing the new uuid.
        """
        entry["id"].text = self._generate_entry_uuid(entry)
        entry["id"].isPermaLink = "false"
        return entry["id"]

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
