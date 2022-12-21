"""Modify a given XML-based feed (RSS or Atom)."""

import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime  # , timezone
from email.utils import format_datetime
from pathlib import Path

Element = ET.Element
ElementTree = ET.ElementTree


class FeedModifier(ABC):
    """Modify a given XML-based feed.

    Concrete subclasses correspond to the specific kind of feed, i.e. RSS or Atom.
    """

    def __init__(self, input_path: str | Path) -> None:
        """Initialization."""
        self.input_path: Path = Path(input_path)
        self.tree: ElementTree = ET.parse(self.input_path)
        self.root: Element = self.tree.getroot()

    @abstractmethod
    def feed_entries(self) -> Sequence[Element]:
        """Returns iterator over the feed's entry/item elements."""
        pass

    @abstractmethod
    def update_entry_pubdate(self, entry: Element, date: datetime) -> None:
        """Update a given entry/item's date of publication."""
        pass

    @staticmethod
    @abstractmethod
    def format_datetime(date: datetime) -> str:
        """Format a datetime as a string, in the format to be written to file."""
        pass

    def update_subelement_text(
        self, element: Element, subelement_name: str, text: str
    ) -> None:
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
            None
        """
        subelement = element.find(subelement_name)
        if not subelement:
            subelement = ET.SubElement(element, subelement_name)

        subelement.text = text
        pass


class RSSFeedModifier(FeedModifier):
    """Modify a given RSS feed."""

    def feed_entries(self) -> Sequence[Element]:
        """Returns iterator over the feed's item elements."""
        channel = self.root.find("channel")
        return [] if channel is None else channel.findall("entry")

    def update_entry_pubdate(self, entry: Element, date: datetime) -> None:
        """Update a given entry/item's date of publication."""
        formatted_date: str = self.format_datetime(date)
        self.update_subelement_text(entry, "pubDate", formatted_date)
        pass

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
        return self.root.findall("entry")

    def update_entry_pubdate(self, entry: Element, date: datetime) -> None:
        """Update a given entry/item's date of publication."""
        formatted_date: str = self.format_datetime(date)
        self.update_subelement_text(entry, "published", formatted_date)
        self.update_subelement_text(entry, "updated", formatted_date)
        pass

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
