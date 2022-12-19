"""FeedModifier test cases (with PyTest)."""

from pathlib import Path

import pytest
from dateutil import parser

from feedmodifier import AtomFeedModifier, RSSFeedModifier


@pytest.fixture
def rss_one_item():
    """Return RSSFeedModifier for an RSS feed with only one item."""
    return RSSFeedModifier(Path("test/data/rss_one_item.xml"))


@pytest.fixture
def rss_two_items():
    """Return RSSFeedModifier for an RSS feed with two items."""
    return RSSFeedModifier(Path("test/data/rss_two_items.xml"))


@pytest.fixture
def rss_simple_examples(rss_one_item, rss_two_items):
    """List of RSSFeedModifiers for simple RSS feeds."""
    return [rss_one_item, rss_two_items]


@pytest.fixture
def atom_one_item():
    """Return RSSFeedModifier for an Atom feed with only one item."""
    return AtomFeedModifier(Path("test/data/atom_one_item.xml"))


@pytest.fixture
def atom_two_items():
    """Return AtomFeedModifier for an Atom feed with two items."""
    return AtomFeedModifier(Path("test/data/atom_two_items.xml"))


@pytest.fixture
def atom_simple_examples(atom_one_item, atom_two_items):
    """List of RSSFeedModifiers for simple RSS feeds."""
    return [atom_one_item, atom_two_items]


def test_RSSFeedModifier_init(rss_simple_examples):
    """Test initialization performs correctly for RSSFeedModifiers."""
    for rss_fm in rss_simple_examples:
        assert rss_fm.tree is not None
        assert rss_fm.root is not None


def test_AtomFeedModifier_init(atom_simple_examples):
    """Test initialization performs correctly for AtomFeedModifiers."""
    for atom_fm in atom_simple_examples:
        assert atom_fm.tree is not None
        assert atom_fm.root is not None


def test_RSSFeedModifier_format_datetime_simple():
    """Test formatting of datetimes to strings for RSSFeedModifier."""
    example_datetimes = [
        "Mon, 15 Mar 2021 14:32:20 -0400",
        "Sun, 19 May 2002 15:21:36 +0000",
    ]

    for dt in example_datetimes:
        dt_parsed = parser.parse(dt)
        dt_formatted = RSSFeedModifier.format_datetime(dt_parsed)
        assert dt == dt_formatted


def test_AtomFeedModifier_format_datetime_simple():
    """Test formatting of datetimes to strings for AtomFeedModifiers.

    Adapted from https://datatracker.ietf.org/doc/html/rfc4287#section-3.3
    """
    example_datetimes = [
        "2003-12-13T18:30:02Z",
        "2003-12-13T18:30:02.700000Z",
        "2003-12-13T18:30:02+01:00",
        "2003-12-13T18:30:02.700000+01:00",
    ]

    for dt in example_datetimes:
        dt_parsed = parser.parse(dt)
        dt_formatted = AtomFeedModifier.format_datetime(dt_parsed)
        assert dt == dt_formatted
