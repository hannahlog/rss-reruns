"""Modify a given XML-based feed (RSS or Atom)."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime  # , timezone
from email.utils import format_datetime
from pathlib import Path

from lxml import etree as ET

# Underscores present because those are the class names in lxml.etree
Element = ET._Element
ElementTree = ET._ElementTree


class FeedModifier(ABC):
    """Modify a given XML-based feed.

    Concrete subclasses correspond to the specific kind of feed, i.e. RSS or Atom.
    """

    def __init__(self, input_path: str | Path) -> None:
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

    def update_subelement_text(
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
        subelement = element.find(subelement_name, self.nsmap)
        if subelement is None:
            subelement = ET.SubElement(element, subelement_name)

        subelement.text = text
        return subelement


class RSSFeedModifier(FeedModifier):
    """Modify a given RSS feed."""

    def feed_entries(self) -> Sequence[Element]:
        """Returns iterator over the feed's item elements."""
        channel = self.root.find("channel", self.nsmap)
        return [] if channel is None else channel.findall("item", self.nsmap)

    def update_entry_pubdate(self, entry: Element, date: datetime) -> list[Element]:
        """Update a given entry/item's date of publication."""
        formatted_date: str = self.format_datetime(date)
        return [self.update_subelement_text(entry, "pubDate", formatted_date)]

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

    def feed_entries(self) -> Sequence[Element]:
        """Returns iterator over the feed's entry elements."""
        return self.root.findall("entry", self.nsmap)

    def update_entry_pubdate(self, entry: Element, date: datetime) -> list[Element]:
        """Update a given entry/item's date of publication."""
        formatted_date: str = self.format_datetime(date)
        published = self.update_subelement_text(entry, "published", formatted_date)
        updated = self.update_subelement_text(entry, "updated", formatted_date)
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
