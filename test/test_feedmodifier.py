"""FeedModifier test cases (with PyTest)."""

from datetime import datetime, timezone
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
    return [
        as_RSS(fname) for fname in ("no_items.rss", "one_item.rss", "two_items.rss")
    ]


@pytest.fixture
def atom_simple_examples():
    """List of AtomFeedModifiers for simple Atom feeds."""
    return [
        as_Atom(fname) for fname in ("no_items.atom", "one_item.atom", "two_items.atom")
    ]


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


@pytest.mark.parametrize("fms", ["atom_simple_examples", "rss_simple_examples"])
def test_update_subelement_text(fms, request):
    """Test `update_subelement_text` for FeedModifiers."""
    fms = request.getfixturevalue(fms)
    # (Don't test the FeedModifiers with 0 entries)
    fms = [fm for fm in fms if len(fm.feed_entries()) > 0]

    for fm in fms:
        num_entries = len(fm.feed_entries())
        contents = []
        for index, entry in enumerate(fm.feed_entries()):
            new_content = f"The content is {index}"
            content_element = fm.update_subelement_text(entry, "content", new_content)
            contents.append((content_element, new_content))

        # The number of entries should remain the same
        assert len(fm.feed_entries()) == num_entries

        # Check that the element texts have been updated correctly, and that updating
        # one entry's subelement did not affect a different entry's subelement.
        for element, content in contents:
            assert element.text == content


def test_update_entry_pubdate(atom_simple_examples, rss_simple_examples):
    """Test `update_entry_pubdate` for FeedModifiers."""
    # (Don't test the FeedModifiers with 0 entries)
    # atom_fms = [fm for fm in atom_simple_examples if len(fm.feed_entries()) > 0]
    # rss_fms = [fm for fm in rss_simple_examples if len(fm.feed_entries()) > 0]

    for fm in [*atom_simple_examples, *rss_simple_examples]:
        num_entries = len(fm.feed_entries())
        elements_dates = []
        for entry in fm.feed_entries():
            dt_now = datetime.now(timezone.utc)
            updated = fm.update_entry_pubdate(entry, dt_now)
            elements_dates.append((updated, dt_now))

        # The number of entries should remain the same
        assert len(fm.feed_entries()) == num_entries

        # Check that the element texts have been updated correctly
        for elements, dt in elements_dates:

            # Check that the correct elements were updated (different depending on
            # type of feed)
            if isinstance(fm, RSSFeedModifier):
                assert len(elements) == 1
                assert elements[0].tag.rpartition("}")[2] == "pubDate"
            else:
                assert len(elements) == 2
                assert {el.tag.rpartition("}")[2] for el in elements} == {
                    "published",
                    "updated",
                }

            # Check that the datetimes were set as expected
            for el in elements:
                assert el.text == fm.format_datetime(dt)


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
