"""FeedModifier test cases (with PyTest)."""

import itertools
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import requests
from dateutil import parser

from feedmodifier import AtomFeedModifier, FeedModifier, RSSFeedModifier

tmp_dir = "test/tmp/"
Path(tmp_dir).mkdir(exist_ok=True)


def fname_to_tmp_path(fname: str) -> str:
    """Prepend the tmp directory to a given filename."""
    return "".join([tmp_dir, fname])


def fname_to_path(fname: str) -> str:
    """Prepend the test data directory to a given filename."""
    return "".join(["test/data/", fname])


def as_RSS(filename: str, **kwargs) -> RSSFeedModifier:
    """Initialize RSSFeedModifier with the given RSS feed."""
    return RSSFeedModifier(Path(fname_to_path(filename)), **kwargs)


def as_Atom(filename: str, **kwargs) -> AtomFeedModifier:
    """Initialize AtomFeedModifier with the given Atom feed."""
    return AtomFeedModifier(Path(fname_to_path(filename)), **kwargs)


@pytest.fixture
def simple_rss_fnames():
    """List of paths for simple RSS feeds."""
    return ("no_items.rss", "one_item.rss", "two_items.rss")


@pytest.fixture
def simple_atom_fnames():
    """List of paths for simple Atom feeds."""
    return (
        "no_items.atom",
        "one_item.atom",
        "two_items.atom",
        "namespaced_two_items.atom",
    )


@pytest.fixture
def simple_rss_fms(simple_rss_fnames):
    """List of RSSFeedModifiers for simple RSS feeds."""
    return (as_RSS(fname) for fname in simple_rss_fnames)


@pytest.fixture
def simple_atom_fms(simple_atom_fnames):
    """List of AtomFeedModifiers for simple Atom feeds."""
    return (as_Atom(fname) for fname in simple_atom_fnames)


def test_RSSFeedModifier_init(simple_rss_fms):
    """Test initialization performs correctly for RSSFeedModifiers."""
    for rss_fm in simple_rss_fms:
        assert rss_fm.tree is not None
        assert rss_fm.root is not None
        assert rss_fm.channel is not None


def test_AtomFeedModifier_init(simple_atom_fms):
    """Test initialization performs correctly for AtomFeedModifiers."""
    for atom_fm in simple_atom_fms:
        assert atom_fm.tree is not None
        assert atom_fm.root is not None
        assert atom_fm.channel is not None


def test_from_file(simple_rss_fnames, simple_atom_fnames):
    """Test factory method from_file for creating FeedModifiers."""
    for fname in (*simple_rss_fnames, *simple_atom_fnames):
        fm = FeedModifier.from_file(fname_to_path(fname))
        assert fm.tree is not None
        assert fm.root is not None
        assert fm.channel is not None


# TODO: better way to organize/write this? :(
@pytest.mark.parametrize(
    "args, expected_path",
    [
        # No path specified: expect default
        (
            (rss_url := "http://www.rss-specifications.com/blog-feed.xml", None),
            "feed.xml",
        ),
        # Path specified as "test/tmp/my-filename.rss" string
        ((rss_url, tmp_path := tmp_dir + "my-filename.rss"), tmp_path),
        # Same path but given as a Path object
        ((rss_url, Path(tmp_path)), tmp_path),
    ],
)
def test_url_to_file(args, expected_path):
    """Test `url_to_file` with or without a path specified."""
    saved_path = FeedModifier.url_to_file(*args)
    assert saved_path == expected_path
    file = Path(saved_path)
    assert file.exists()
    assert file.is_file()
    file.unlink()


# TODO: this is effectively a test for `requests.get`: consider removal?
@pytest.mark.parametrize(
    "bad_url, expected_exception",
    [
        ("just some words", requests.exceptions.MissingSchema),
        ("https://", requests.exceptions.InvalidURL),
    ],
)
def test_url_to_file_invalid_url(bad_url, expected_exception):
    """Test `url_to_file` with an invalid URL argument."""
    with pytest.raises(expected_exception) as exc_info:
        FeedModifier.url_to_file(bad_url)
    assert "Invalid URL" in exc_info.value.args[0]


@pytest.mark.parametrize(
    "url_404",
    [
        "https://example.com/this-will-404-not-a-real-url-34454127.xml",
    ],
)
def test_url_to_file_404(url_404):
    """Test `url_to_file` with a valid URL that will return 404 Not Found."""
    with pytest.raises(ValueError) as exc_info:
        FeedModifier.url_to_file(url_404)
    assert (
        exc_info.value.args[0] == f"Requested url {url_404} returned status code: 404"
    )


def test_serialize(simple_atom_fms, simple_rss_fms):
    """Test serialization method serialize() (writes to json file)."""
    for fm in (*simple_atom_fms, *simple_rss_fms):
        meta_path = fname_to_tmp_path("out.json")
        fm.serialize(meta_path)
        # TODO: actually write these tests, expected output files, etc.
        pass


def test_deserialize(simple_atom_fms, simple_rss_fms):
    """Test deserialization classmethod deserialize() (from json file)."""
    # TODO: actually write these tests
    pass


@pytest.mark.parametrize("fms", ["simple_atom_fms", "simple_rss_fms"])
def test_set_title_too_many_kwargs(fms, request):
    """Confirm `set_title` raises error if given too many kwargs."""
    fms = request.getfixturevalue(fms)

    all_kwargs = {
        "title": "My New Title",
        "prefix": "New Title's Prefix: ",
        "func": str.upper,
    }

    # List of all length-2 combinations, e.g.
    #   {"title": "My New Title", "func": str.upper}
    choose_two_kwargs: list[dict[str:Any]] = [
        {k: v for k, v in i} for i in itertools.combinations(all_kwargs.items(), 2)
    ]

    # For already-initialized FeedModifiers:
    for fm in fms:
        for two_kwargs in choose_two_kwargs:
            # Giving exactly two keyword arguments:
            with pytest.raises(ValueError) as exc_info:
                fm.set_feed_title(**two_kwargs)
            assert exc_info.value.args[0] == "Expected exactly one kwarg, found: 2"

        # Giving all three keyword arguments:
        with pytest.raises(ValueError) as exc_info:
            fm.set_feed_title(**all_kwargs)
        assert exc_info.value.args[0] == "Expected exactly one kwarg, found: 3"


@pytest.mark.parametrize("fms", ["simple_atom_fms", "simple_rss_fms"])
def test_set_title_no_kwargs(fms, request):
    """Confirm `set_title` raises error if given too few (i.e. zero) kwargs."""
    fms = request.getfixturevalue(fms)
    # For already-initialized FeedModifiers:
    for fm in fms:
        with pytest.raises(ValueError) as exc_info:
            fm.set_feed_title()
        assert exc_info.value.args[0] == "Expected exactly one kwarg, found: 0"


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


@pytest.mark.parametrize("fms", ["simple_atom_fms", "simple_rss_fms"])
def test_set_subelement_text(fms, request):
    """Test `set_subelement_text` for FeedModifiers."""
    fms = request.getfixturevalue(fms)
    # (Skip FeedModifiers with 0 entries)
    fms = [fm for fm in fms if len(fm.feed_entries()) > 0]

    for fm in fms:
        num_entries = len(fm.feed_entries())
        contents = []
        for index, entry in enumerate(fm.feed_entries()):
            new_content = f"The content is {index}"
            content_element = fm.set_subelement_text(entry, "content", new_content)
            contents.append((content_element, new_content))

        # The number of entries should remain the same
        assert len(fm.feed_entries()) == num_entries

        # Check that the element texts have been updated correctly, and that updating
        # one entry's subelement did not affect a different entry's subelement.
        for element, content in contents:
            assert element.text == content


def test_update_entry_pubdate(simple_atom_fms, simple_rss_fms):
    """Test `update_entry_pubdate` for FeedModifiers."""
    for fm in [*simple_atom_fms, *simple_rss_fms]:
        num_entries = len(fm.feed_entries())
        elements_dates = []
        for entry in fm.feed_entries():
            dt_now = datetime.now(timezone.utc)
            updated = fm.update_entry_pubdate(entry, dt_now)
            elements_dates.append((updated, dt_now))

        # The number of entries should remain the same
        assert len(fm.feed_entries()) == num_entries

        for elements, dt in elements_dates:
            # Check that the correct elements were updated (different depending on
            # type of feed)
            if isinstance(fm, RSSFeedModifier):
                # An RSSFeedModifier only updates `pubDate`
                assert len(elements) == 1
                assert elements[0].tag.rpartition("}")[2] == "pubDate"
            else:
                # An AtomFeedModifier should update both `published` and `updated`
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
