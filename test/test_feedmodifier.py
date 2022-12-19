"""FeedModifier test cases (with PyTest)."""

from pathlib import Path

import pytest

from feedmodifier import AtomFeedModifier, RSSFeedModifier


@pytest.fixture
def rss_single_item():
    """Return RSSFeedModifier for an RSS feed with only one item."""
    return RSSFeedModifier(Path("test/data/rss_single_item.xml"))


@pytest.fixture
def rss_two_items():
    """Return RSSFeedModifier for an RSS feed with two items."""
    return RSSFeedModifier(Path("test/data/rss_two_items.xml"))


@pytest.fixture
def rss_simple_examples(rss_one_item, rss_two_items):
    """List of RSSFeedModifiers for simple RSS feeds."""
    return [rss_one_item, rss_two_items]


@pytest.fixture
def atom_single_item():
    """Return RSSFeedModifier for an Atom feed with only one item."""
    return AtomFeedModifier(Path("test/data/atom_single_item.xml"))


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
