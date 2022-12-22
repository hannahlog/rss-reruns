"""FeedModifier test cases (with PyTest)."""

from pathlib import Path

import pytest
from dateutil import parser

from feedmodifier import AtomFeedModifier, RSSFeedModifier


def as_RSS(filename: str) -> RSSFeedModifier:
    """Initialize RSSFeedModifier with the given RSS feed."""
    return RSSFeedModifier(Path("".join(["test/data/", filename])))


def as_Atom(filename: str) -> AtomFeedModifier:
    """Initialize AtomFeedModifier with the given Atom feed."""
    return AtomFeedModifier(Path("".join(["test/data/", filename])))


@pytest.fixture
def rss_simple_examples():
    """List of RSSFeedModifiers for simple RSS feeds."""
    return (
        as_RSS(fname) for fname in ("no_items.rss", "one_item.rss", "two_items.rss")
    )


@pytest.fixture
def atom_simple_examples():
    """List of AtomFeedModifiers for simple Atom feeds."""
    return (
        as_Atom(fname) for fname in ("no_items.atom", "one_item.atom", "two_items.atom")
    )


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


def rss_len_examples() -> tuple[RSSFeedModifier, int]:
    """Test cases for RSSFeedModifier's expected number of entries."""
    return [
        (as_RSS("no_items.rss"), 0),
        (as_RSS("one_item.rss"), 1),
        (as_RSS("two_items.rss"), 2),
    ]


def atom_len_examples() -> tuple[AtomFeedModifier, int]:
    """Test cases for AtomFeedModifier's expected number of entries."""
    return [
        (as_Atom("no_items.atom"), 0),
        (as_Atom("one_item.atom"), 1),
        (as_Atom("two_items.atom"), 2),
    ]


@pytest.mark.parametrize("rss_fm, expected_len", rss_len_examples())
def test_RSSFeedModifier_feed_entries_len(rss_fm, expected_len):
    """Test feed_entries() for RSSFeedModifiers."""
    assert len(rss_fm.feed_entries()) == expected_len


@pytest.mark.parametrize("atom_fm, expected_len", atom_len_examples())
def test_AtomFeedModifier_feed_entries_len(atom_fm, expected_len):
    """Test feed_entries() for AtomFeedModifiers."""
    assert len(atom_fm.feed_entries()) == expected_len


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
