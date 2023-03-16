"""FeedModifier test cases (with PyTest)."""
from __future__ import annotations

from datetime import datetime, timezone
from math import gcd
from pathlib import Path
from time import sleep

import pytest
import requests
from dateutil import parser
from lxml import etree as ET

from rssreruns.feedmodifier import AtomFeedModifier, FeedModifier, RSSFeedModifier

tmp_dir = Path("test/tmp/")
tmp_dir.mkdir(exist_ok=True)
data_dir = Path("test/feedmodifier/")


def as_RSS(filename: str, **kwargs) -> RSSFeedModifier:
    """Initialize RSSFeedModifier with the given RSS feed."""
    return RSSFeedModifier(data_dir / filename, **kwargs)


def as_Atom(filename: str, **kwargs) -> AtomFeedModifier:
    """Initialize AtomFeedModifier with the given Atom feed."""
    return AtomFeedModifier(data_dir / filename, **kwargs)


@pytest.fixture
def simple_rss_fnames():
    """List of paths for simple RSS feeds."""
    return (
        "no_items.rss",
        "one_item.rss",
        "two_items.rss",
        "four_items.rss",
        "seven_items.rss",
    )


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


rss_url = "http://www.rss-specifications.com/blog-feed.xml"
tmp_path = tmp_dir / "my_filename.rss"


# TODO: better way to organize/write this? :(
@pytest.mark.parametrize(
    "args, expected_path",
    [
        # No path specified: expect default
        (
            (rss_url, None),
            "downloads/feed.xml",
        ),
        # Path given as Path object
        ((rss_url, tmp_path), tmp_path),
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


@pytest.mark.parametrize(
    "url",
    [rss_url],
)
def test_from_url(url):
    """Test `from_url` with real feed URLs. (Warning: `sleep` used for politeness)."""
    sleep(3)
    fm_via_string = FeedModifier.from_url(url)
    fm_via_file = FeedModifier.from_url(url, path=tmp_dir / "blog-feed.xml")
    assert _same_attributes(fm_via_string, fm_via_file)


def test_from_string(simple_fnames):
    """Test initialization from string rather than url or filepath."""
    for fname in simple_fnames:
        with open(data_dir / fname, "rb") as f:
            contents = f.read()
            # print(type(contents))
            fm = FeedModifier.from_string(contents)

            # Write to file, load from file, and compare
            out_path = tmp_dir / fname
            fm.write(out_path)
            deserialized = FeedModifier.from_file(out_path)
            assert _same_attributes(fm, deserialized)

            # Output as string, load from string, and compare
            out_string = fm.write(out_path)
            deserialized = FeedModifier.from_string(out_string)
            assert _same_attributes(fm, deserialized)


def test_write(simple_fnames, simple_fms):
    """Test writing the modified feed (and associated FeedModifier data) to XML."""
    for fname, fm in zip(simple_fnames, simple_fms):
        out_path = tmp_dir / fname
        fm.write(out_path)
        # TODO: actually write these tests, expected output files, etc.
        deserialized = FeedModifier.from_file(out_path)
        assert _same_attributes(fm, deserialized)
        pass


def _same_attributes(this, other):
    """Pseudo-equality comparison, intended only for testing."""
    # TODO: This is a temporary kludge that only exists for sanity checking. It does
    # not properly show equality, which is why it is not an `__eq__` method.
    # Remove this once better test cases for [de]serialization are in place.
    def _attrs(obj):
        attrs = {
            k: v
            for k, v in vars(obj).items()
            if (k in {"_nsmap"} or not k.startswith("_")) and k not in {"path"}
        }
        from_meta_channel = {
            subelement: obj._meta_channel[subelement].text
            for subelement in (
                "original_title",
                "title_prefix",
                "entry_title_prefix",
                "entry_title_suffix",
                "run_forever",
                "order",
            )
        }
        from_channel = {"title": obj._channel["title"].text}

        # Rewritten without `|` so tox can run tests for Python 3.7
        # return attrs | from_meta_channel | from_channel
        return {**attrs, **from_meta_channel, **from_channel}

    this_attrs = _attrs(this)
    other_attrs = _attrs(other)

    this_nsmap = (
        {(k, v) for k, v in this_attrs["_nsmap"].items()}
        if "_nsmap" in this_attrs
        else set()
    )
    other_nsmap = (
        {(k, v) for k, v in other_attrs["_nsmap"].items()}
        if "_nsmap" in other_attrs
        else set()
    )
    nsmaps_diff = this_nsmap ^ other_nsmap

    this_everything_else = {(k, v) for k, v in this_attrs.items() if k != "_nsmap"}
    other_everything_else = {(k, v) for k, v in other_attrs.items() if k != "_nsmap"}

    diff = this_everything_else ^ other_everything_else
    return len(nsmaps_diff | diff) == 0


def test_same_attributes(simple_fms):
    """Test the `_same_attributes` method (used in testing [de]serialization)."""
    other_fm = as_Atom("two_items.atom")
    other_fm["entry_title_prefix"] = "VERY DIFFERENT PREFIX!"
    for fm in simple_fms:
        assert _same_attributes(fm, fm)
        assert not _same_attributes(fm, other_fm)


def rss_len_examples() -> tuple[RSSFeedModifier, int]:
    """Test cases for RSSFeedModifier's expected number of entries."""
    return [
        (as_RSS("no_items.rss"), 0),
        (as_RSS("one_item.rss"), 1),
        (as_RSS("two_items.rss"), 2),
        (as_RSS("four_items.rss"), 4),
        (as_RSS("seven_items.rss"), 7),
    ]


def atom_len_examples() -> tuple[AtomFeedModifier, int]:
    """Test cases for AtomFeedModifier's expected number of entries."""
    return [
        (as_Atom("no_items.atom"), 0),
        (as_Atom("one_item.atom"), 1),
        (as_Atom("two_items.atom"), 2),
        (as_Atom("namespaced_two_items.atom"), 2),
    ]


@pytest.mark.parametrize(
    "fm, expected_len", (*rss_len_examples(), *atom_len_examples())
)
def test_feed_entries_len(fm, expected_len):
    """Test feed_entries() for FeedModifiers."""
    assert len(fm.feed_entries()) == expected_len


@pytest.mark.parametrize(
    "fm, expected_len", (*rss_len_examples(), *atom_len_examples())
)
def test_feed_meta_entries_len(fm, expected_len):
    """Test _feed_meta_entries() for FeedModifiers."""
    assert len(fm._feed_meta_entries()) == expected_len


@pytest.mark.parametrize(
    "fm, expected_len", (*rss_len_examples(), *atom_len_examples())
)
def test_entries_to_rerun(fm, expected_len):
    """_entries_to_rerun() should initially return all entries."""
    assert len(fm._entries_to_rerun()) == expected_len


@pytest.mark.parametrize(
    "fm, expected_len",
    (
        (fm, length)
        for (fm, length) in (*rss_len_examples(), *atom_len_examples())
        if length > 0
    ),
)
def test_entries_to_rerun_single_rebroadcasts(fm, expected_len):
    """_entries_to_rerun() decreases by one each time rebroadcast(1) is called."""
    assert len(fm._entries_to_rerun()) == expected_len

    # (Go through and rebroadcast all of the entries a few times over.)
    for i in range(7):
        # Rebroadcast entries until there is only 1 that has not been rebroadcasted
        remaining = len(fm._entries_to_rerun())
        while remaining > 1:
            fm.rebroadcast(1)
            assert len(fm._entries_to_rerun()) == remaining - 1
            remaining -= 1

        # Rebroadcast the last remaining entry that has not yet been rebroadcast.
        fm.rebroadcast(1)
        # 0 should not be returned: when rebroadcast(1) would rebroacast the last
        # remaining entry, all entries should be marked as <reran>False</reran>, so
        # the number of remaining entries will again be the total number of entries.
        assert len(fm._entries_to_rerun()) == expected_len


@pytest.mark.parametrize(
    "fm, expected_len, num",
    (
        (fm, length, num)
        for (fm, length) in (*rss_len_examples(), *atom_len_examples())
        for num in range(1, length)
        if length > 0
    ),
)
def test_entries_to_rerun_multiple_rebroadcasts(fm, expected_len, num):
    """Decrease remaining by num (mod len) after calling rebroadcast(num)."""
    assert len(fm._entries_to_rerun()) == expected_len

    # Rewritten with `gcd` because Python 3.7 lacks `math.lcm` (but has `gcd`)
    #   lcm = math.lcm(expected_len, num)
    lcm = abs(expected_len * num) // gcd(expected_len, num)

    calls_to_reach_exactly_zero = lcm // num
    # print(f"Expected_len: {expected_len}, num: {num}")
    # print(f"LCM: {lcm}")
    # print(f"(lcm // num): {(lcm // num)}")
    # print(f"(lcm // num) - 1: {(lcm // num) - 1}")

    # (Go through and rebroadcast all of the entries a few times over.)
    for i in range(7):
        remaining = expected_len
        # print(f"{remaining} (mod {expected_len})")
        for calls_to_rebroadcast in range(calls_to_reach_exactly_zero - 1):
            fm.rebroadcast(num)
            now_remaining = (remaining - num) % expected_len
            assert len(fm._entries_to_rerun()) % expected_len == now_remaining
            remaining = now_remaining
            # print(f"{remaining} (mod {expected_len})")

        # After (lcm // num) - 1 rebroadcasts of num entries, there should be exactly
        # `num` entries left to rebroadcast
        assert remaining == num

        # Rebroadcast the last `num` remaining entries
        fm.rebroadcast(num)
        # 0 should not be returned: when rebroadcast(num) would rebroacast the last
        # remaining entries, all entries should be marked as <reran>False</reran>, so
        # the number of remaining entries will again be the total number of entries.
        assert len(fm._entries_to_rerun()) == expected_len


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


def test_source_url_simple(simple_rss_fms, simple_atom_fms):
    """Test source_url() returns the correct source url.

    For RSS feeds, the feed channel has a single link element.

    For Atom feeds, the feed may have multiple link elements, but should have one
    with rel="self" (which will be returned if present.)
    """
    for fm in simple_rss_fms:
        assert fm.source_url() == "http://example.com/notarealblogurl.htm"

    for fm in simple_atom_fms:
        assert fm.source_url() == "https://example.org/feed.atom"


def test_source_url_xml_base():
    """Test source_url() resolves URIs relative to xml:base correctly when needed.

    See:
        https://www.w3.org/TR/xmlbase/
        https://feedparser.readthedocs.io/en/latest/resolving-relative-links.html
    """
    # Base URI https://www.example.org/ declared in the root
    fm = as_Atom("namespaced_xml_base_in_root.atom")
    assert fm.source_url() == "https://www.example.org/blog/news/feed.atom"

    # Same base URI declared in the root, and "blog/news/" declared in the <link/>
    # itself
    fm = as_Atom("namespaced_xml_base_in_root_and_link.atom")
    assert fm.source_url() == "https://www.example.org/blog/news/feed.atom"


def test_feed_type(simple_rss_fms, simple_atom_fms):
    """Test feed_type() returns "RSS" or "Atom" as expected."""
    # Base URI https://www.example.org/ declared in the root
    for fm in simple_rss_fms:
        assert fm.feed_type() == "RSS"

    for fm in simple_atom_fms:
        assert fm.feed_type() == "Atom"


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
