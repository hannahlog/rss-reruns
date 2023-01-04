"""Modify a given XML-based feed (RSS or Atom)."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime  # , timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Callable

from lxml import etree as ET

# Underscores present because those are the class names in lxml.etree
Element = ET._Element
ElementTree = ET._ElementTree


class FeedModifier(ABC):
    """Modify a given XML-based feed.

    Concrete subclasses correspond to the specific kind of feed, i.e. RSS or Atom.
    """

    def __init__(
        self, input_path: str | Path, title_kwargs={"prefix": "RERUNS: "}
    ) -> None:
        """Initialization."""
        self.input_path: Path = Path(input_path)
        self.tree: ElementTree = ET.parse(self.input_path)
        self.root: Element = self.tree.getroot()

        # Dictionary of XML namespaces to use with `find()`, `findall()`, etc.
        #
        # The extra logic is due to the representation of a Default Namespace
        # in the `root.nsmap` dictionary -- if there is a default namespace, its
        # key is `None` rather than an empty string. This makes Mypy find its
        # keys to have type `Optional[str]` instead of `str`, which unfortunately
        # makes it believe the dictionary is incompatible with the type signature
        # of `find()`, `findall()` etc.
        #
        # This comprehension creates an equivalent dictionary, but replacing a `None`
        # key with an empty string `""` if encountered.
        #
        # TODO: Review and make sure this replacement is correct and introduces no
        # problems. Possibly use a named function in place of the anonymous
        # comprehension.
        self.nsmap: dict[str, str] = {
            (k if k is not None else ""): v for k, v in self.root.nsmap.items()
        }

        # Element containing metadata and entry/item elements:
        # `feed` for Atom (which is also the root), and `channel` for RSS (not the root)
        self.channel = self.feed_channel()
        self.set_feed_title(**title_kwargs)

    def set_feed_title(
        self,
        *,
        title: str | None = None,
        prefix: str | None = None,
        func: Callable[[str], str] | None = None,
    ) -> str:
        """Specify the new feed's title, either exactly, or with a prefix or function.

        The new title may be specified through exactly one of the keyword arguments:
        `title` to give an exact string, `prefix` to prepend a string to the original
        title, or `func` to provide a function that, given the old title as a string,
        creates a new title string.

        Args:
            title (str):
                Exact string to use as the republished feed's title.
            prefix (str):
                String to prepend to the original title.
            func (str -> str):
                Function taking the original title and returning the new title.

        Returns:
            str: the title of the republished feed, as it will be written to file.
        """
        num_kwargs = len([arg for arg in (title, prefix, func) if arg is not None])
        if num_kwargs != 1:
            raise ValueError(f"Expected exactly one kwarg, found: {num_kwargs}")

        if title is not None:
            self._title = title
        else:
            title_element = self.get_subelement(self.channel, "title")
            old_title = (
                title_element.text
                if title_element is not None and title_element.text is not None
                else ""
            )
            if prefix is not None:
                self._title = "".join([prefix, old_title])
            elif func is not None:
                self._title = func(old_title)

        return self._title

    @abstractmethod
    def feed_channel(self) -> Element:
        """Returns the `feed` (Atom) or `channel` (RSS) element of the tree."""
        pass

    @abstractmethod
    def feed_entries(self) -> Sequence[Element]:
        """Returns iterator over the feed's entry/item elements."""
        pass

    @abstractmethod
    def update_entry_pubdate(self, entry: Element, date: datetime) -> list[Element]:
        """Update a given entry/item's date of publication."""
        pass

    @staticmethod
    @abstractmethod
    def format_datetime(date: datetime) -> str:
        """Format a datetime as a string, in the format to be written to file."""
        pass

    def set_subelement_text(
        self, element: Element, subelement_name: str, text: str
    ) -> Element:
        """Update the text of a specified entry's subelement.

        If no subelement with the specified name is found, add the subelement before
        setting its text.

        Args:
            entry (Element):
                Parent XML element whose subelement is to be updated.
            subelement_name (str):
                Name of the subelement to update.
            text (str):
                Text to be enclosed by the specified subelement.

        Returns:
            Element: the modified (possibly newly created) subelement.
        """
        subelement = self.get_subelement(element, subelement_name)
        if subelement is None:
            subelement = ET.SubElement(element, subelement_name)

        subelement.text = text
        return subelement

    def get_subelement(self, element: Element, subelement_name: str) -> Element | None:
        """Get a specified element's subelement.

        Args:
            entry (Element):
                Parent XML element whose subelement is to be found.
            subelement_name (str):
                Name of the subelement to find.

        Returns:
            Optional[Element]: the found subelement, or None if not found.
        """
        return element.find(subelement_name, self.nsmap)


class RSSFeedModifier(FeedModifier):
    """Modify a given RSS feed."""

    def feed_channel(self) -> Element:
        """Returns the `feed` (Atom) or `channel` (RSS) element of the tree."""
        # For RSS, the `channel` element is a child of the root `rss` element
        channel = self.root.find("channel", self.nsmap)
        if channel is None:
            raise ValueError("RSS feed must contain `channel` element (not found).")
        else:
            return channel

    def feed_entries(self) -> Sequence[Element]:
        """Returns iterator over the feed's item elements."""
        return self.channel.findall("item", self.nsmap)

    def update_entry_pubdate(self, entry: Element, date: datetime) -> list[Element]:
        """Update a given entry/item's date of publication."""
        formatted_date: str = self.format_datetime(date)
        return [self.set_subelement_text(entry, "pubDate", formatted_date)]

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
        return format_datetime(date)


class AtomFeedModifier(FeedModifier):
    """Modify a given Atom feed."""

    def feed_channel(self) -> Element:
        """Returns the `feed` (Atom) or `channel` (RSS) element of the tree."""
        # For Atom, the `feed` element is the root itself
        return self.root

    def feed_entries(self) -> Sequence[Element]:
        """Returns iterator over the feed's entry elements."""
        return self.channel.findall("entry", self.nsmap)

    def update_entry_pubdate(self, entry: Element, date: datetime) -> list[Element]:
        """Update a given entry/item's date of publication."""
        formatted_date: str = self.format_datetime(date)
        published = self.set_subelement_text(entry, "published", formatted_date)
        updated = self.set_subelement_text(entry, "updated", formatted_date)
        return [published, updated]

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
