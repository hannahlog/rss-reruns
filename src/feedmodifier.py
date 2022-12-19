"""Modify a given XML-based feed (RSS or Atom)."""

import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

Element = ET.Element


class FeedModifier(ABC):
    """Modify a given XML-based feed.

    Concrete subclasses correspond to the specific kind of feed, i.e. RSS or Atom.
    """

    def __init__(self, input_path: str | Path) -> None:
        """Initialization."""
        self.input_path: Path = Path(input_path)
        self.tree = ET.parse(self.input_path)
        self.root = self.tree.getroot()

    @abstractmethod
    def feed_entries(self) -> Sequence[Element]:
        """Returns iterator over the feed's entry/item elements."""
        pass

    @abstractmethod
    def update_entry_pubdate(self, entry: Element, date) -> None:
        """Update a given entry/item's date of publication."""
        pass

    @abstractmethod
    def format_datetime(self, date) -> str:
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

    def update_entry_pubdate(self, entry: Element, date) -> None:
        """Update a given entry/item's date of publication."""
        date = self.format_datetime(date)
        self.update_subelement_text(entry, "pubDate", date)
        pass

    def format_datetime(self, date) -> str:
        """Format a datetime as a string, in the format required for RSS."""
        raise NotImplementedError


class AtomFeedModifier(FeedModifier):
    """Modify a given Atom feed."""

    def feed_entries(self) -> Sequence[Element]:
        """Returns iterator over the feed's entry elements."""
        return self.root.findall("entry")

    def update_entry_pubdate(self, entry: Element, date) -> None:
        """Update a given entry/item's date of publication."""
        date = self.format_datetime(date)
        self.update_subelement_text(entry, "published", date)
        self.update_subelement_text(entry, "updated", date)
        pass

    def format_datetime(self, date) -> str:
        """Format a datetime as a string, in the format required for Atom."""
        raise NotImplementedError


if __name__ == "__main__":
    pass
