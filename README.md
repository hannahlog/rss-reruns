# RSS-Reruns

Rebroadcast old RSS/Atom feed items to a new feed, in shuffled or chronological order.

## Installation and example usage

To install the latest version from PyPi:
```
pip install rssreruns==0.0.11
```
Example usage to create a feed of reruns, from an existing feed's filepath or URL:
```
from rssreruns.feedmodifier import FeedModifier as FM
# Initialize from file...
fm = FM.from_file("in/some_old_feed.xml")
# ...or from a URL
fm = FM.from_url("example.org/feed.xml")
# Add prefixes and/or suffixes to the feed's title
fm.set_feed_title(prefix="[RERUNS:]", suffix="(this is a reruns feed)")
# Add prefixes and/or suffixes to entry titles;
# can include date formatting for the entry's original pubdate
fm.set_entry_titles(prefix="[From %b %d %Y:]")
# Rebroadcast some entries! Their publication dates will be set to the current datetime
fm.rebroadcast(3)
# Write out the resulting feed to file 
fm.write(path="out/my_output_feed.xml")
# ...or as a string (Not Recommended)
big_output_string = fm.write(path=None, pretty_print=False)
```
The FeedModifier's own settings—the prefixes and suffixes, shuffled vs. chronological order, etc.—are stored in the XML itself, under a separate namespace, for easy reserialization:
```
fm = FM.from_file(path="out/my_output_feed.xml")
fm.rebroadcast(1)
fm.write(path="out/my_output_feed.xml")
```
(Hosting the generated feed is up to you.)

## Disclaimer

This is a personal project intended for my own use and edification: it is open source and published to PyPi mostly for my own experience with Python's building/packaging ecosystem (and my own convenience). For example, it internally makes use of a class for interacting with lxml elements that I knowingly wrote as a personal exercise of Reinventing The Wheel (instead of just using lxml's own `objectify`). It's not really intended for other people's usage, and *definitely* not for production. See `LICENSE.txt` for the more formal disclaimers.