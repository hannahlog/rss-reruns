"""FeedModifier test cases (with PyTest)."""

from datetime import datetime, timezone
from pathlib import Path
from time import sleep

import pytest
import requests
from dateutil import parser
from lxml import etree as ET

from feedmodifier import AtomFeedModifier, FeedModifier, RSSFeedModifier

tmp_dir = Path("test/tmp/")
tmp_dir.mkdir(exist_ok=True)
data_dir = Path("test/data/")


def as_RSS(filename: str, **kwargs) -> RSSFeedModifier:
    """Initialize RSSFeedModifier with the given RSS feed."""
    return RSSFeedModifier(data_dir / filename, **kwargs)


def as_Atom(filename: str, **kwargs) -> AtomFeedModifier:
    """Initialize AtomFeedModifier with the given Atom feed."""
    return AtomFeedModifier(data_dir / filename, **kwargs)


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
def simple_fnames(simple_atom_fnames, simple_rss_fnames):
    """List of paths for simple Atom feeds."""
    return (*simple_atom_fnames, *simple_rss_fnames)


@pytest.fixture
def simple_rss_fms(simple_rss_fnames):
    """List of RSSFeedModifiers for simple RSS feeds."""
    return (as_RSS(fname) for fname in simple_rss_fnames)


@pytest.fixture
def simple_atom_fms(simple_atom_fnames):
    """List of AtomFeedModifiers for simple Atom feeds."""
    return (as_Atom(fname) for fname in simple_atom_fnames)


@pytest.fixture
def simple_fms(simple_atom_fms, simple_rss_fms):
    """List of AtomFeedModifiers for simple Atom feeds."""
    return (*simple_atom_fms, *simple_rss_fms)


def test_RSSFeedModifier_init(simple_rss_fms):
    """Test initialization performs correctly for RSSFeedModifiers."""
    for rss_fm in simple_rss_fms:
        assert rss_fm._tree is not None
        assert rss_fm._root is not None
        assert rss_fm._channel is not None


def test_AtomFeedModifier_init(simple_atom_fms):
    """Test initialization performs correctly for AtomFeedModifiers."""
    for atom_fm in simple_atom_fms:
        assert atom_fm._tree is not None
        assert atom_fm._root is not None
        assert atom_fm._channel is not None


def test_from_file(simple_fnames):
    """Test factory method from_file for creating FeedModifiers."""
    for fname in simple_fnames:
        fm = FeedModifier.from_file(data_dir / fname)
        assert fm._tree is not None
        assert fm._root is not None
        assert fm._channel is not None


# TODO: better way to organize/write this? :(
@pytest.mark.parametrize(
    "args, expected_path",
    [
        # No path specified: expect default
        (
            (rss_url := "http://www.rss-specifications.com/blog-feed.xml", None),
            "downloads/feed.xml",
        ),
        # Path given as Path object
        ((rss_url, tmp_path := tmp_dir / "my_filename.rss"), tmp_path),
        # Same path but given as a string ("test/tmp/my-filename.rss")
        ((rss_url, str(tmp_path)), tmp_path),
    ],
)
def test_url_to_file(args, expected_path):
    """Test `url_to_file` with or without a path specified."""
    saved_path = FeedModifier.url_to_file(*args)
    assert saved_path == Path(expected_path)
    assert str(saved_path) == str(expected_path)
    assert saved_path.exists()
    assert saved_path.is_file()

    # Clean up downloaded file and the default /downloads/ directory if it exists
    saved_path.unlink()
    if Path("downloads").exists():
        Path("downloads").rmdir()


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


def test_write(simple_fnames, simple_fms):
    """Test writing the modified feed (and associated FeedModifier data) to XML."""
    for fname, fm in zip(simple_fnames, simple_fms):
        out_path = tmp_dir / fname
        fm.write(out_path)
        # TODO: actually write these tests, expected output files, etc.
        deserialized = fm.from_file(out_path)
        # assert fm._same_attributes(deserialized)
        pass


def test_same_attributes(simple_fms):
    """Test the `_same_attributes` method (used in testing [de]serialization)."""
    other_fm = as_Atom("two_items.atom")
    other_fm.entry_title_prefix = "56546576576576576"
    for fm in simple_fms:
        assert fm._same_attributes(fm)
        assert not fm._same_attributes(other_fm)


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


@pytest.mark.parametrize(
    "fm, expected_len", (*rss_len_examples(), *atom_len_examples())
)
def test_feed_entries_len(fm, expected_len):
    """Test feed_entries() for RSSFeedModifiers."""
    assert len(fm.feed_entries()) == expected_len


def test_set_subelement_text(simple_fms):
    """Test `set_subelement_text` for FeedModifiers."""
    for fm in simple_fms:
        num_entries = len(fm.feed_entries())
        contents = []
        for index, entry in enumerate(fm.feed_entries()):
            # print(ET.tostring(entry["content"]._element))
            # print(ET.tostring(entry["content"].text))
            new_content = f"The content is {index}"
            entry["content"].text = new_content
            print(ET.tostring(entry["content"]._element))
            # content_element = fm.lu.set_subelement_text(entry, "content", new_content)
            contents.append((entry["content"], new_content))

        # The number of entries should remain the same
        assert len(fm.feed_entries()) == num_entries

        # Check that the element texts have been updated correctly, and that updating
        # one entry's subelement did not affect a different entry's subelement.
        for entry, content in contents:
            assert entry.text == content
            assert entry._element.text == content


def test_update_entry_pubdate(simple_fms):
    """Test `update_entry_pubdate` for FeedModifiers."""
    for fm in simple_fms:
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
                print(el)
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


def w3c_feed_validator(path: Path | str) -> bool:
    """Validate an Atom/RSS feed through the W3C's public validation service."""
    base_uri = "http://validator.w3.org/feed/check.cgi"
    # At LEAST 1 second delay between requests is required
    sleep(2)

    with open(path, "r") as f:
        feed = f.read()

    response = requests.post(
        base_uri,
        params={"rawdata": feed, "output": "soap12"},
        headers={"Content-type": "application/xml"},
    )
    print(response)
    print(response.content)
    print("============================")
    response_file = "w3c_out.xml"
    with open(response_file, "wb") as f:
        f.write(response.content)
    tree = ET.parse(response_file)
    tree.write(response_file, pretty_print=True, xml_declaration=True, encoding="utf-8")
    return True


if False:
    w3c_feed_validator(data_dir / "namespaced_two_items.atom")
