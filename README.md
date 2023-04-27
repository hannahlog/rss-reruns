# RSS-Reruns

Rebroadcast old RSS/Atom feed items to a new feed, in shuffled or chronological order.

Example screenshot of rebroadcasted entries appearing alongside actual updates from blogs I follow, as seen in my own feed reader:

![Screenshot from Feedly](https://github.com/hannahlog/rss-reruns/blob/main/screenshots/as_seen_in_feedly.png?raw=True)

## Installation and example usage

To install the latest version from PyPi:
```
pip install rssreruns==0.0.11
```
Example usage to create a feed of reruns, from an existing feed's filepath or URL:
```python
from rssreruns.feedmodifier import FeedModifier as FM
# Initialize from file...
fm = FM.from_file("in/some_old_feed.xml")
# ...or from a URL
fm = FM.from_url("example.org/some_old_feed.xml")
# Add prefixes and/or suffixes to the feed's title
fm.set_feed_title(prefix="[RERUNS:]", suffix="(this is a reruns feed)")
# Add prefixes and/or suffixes to entry titles;
# these can include date formatting for the entry's original pubdate
fm.set_entry_titles(prefix="[From %b %d %Y:]")
# Rebroadcast some entries! Their publication dates will be set to the current datetime
fm.rebroadcast(3)
# Write out the resulting feed to file 
fm.write(path="out/my_output_feed.xml")
# ...or as a string (Not Recommended)
big_output_string = fm.write(path=None, pretty_print=False)
```
The FeedModifier's own settings—the prefixes and suffixes, shuffled vs. chronological order, etc.—are stored in the XML itself, under a separate `reruns` namespace (allowed by both the RSS and Atom standards) for easy serialization and deserialization:
```python
fm = FM.from_file(path="out/my_output_feed.xml")
fm.rebroadcast(1)
fm.write(path="out/my_output_feed.xml")
```
(Hosting the generated feed is up to you. [I ended up hosting them on S3, and added a little Django frontend.](https://github.com/hannahlog/reruns-django-site))

## About & Motivation

This is a personal project mainly intended for my own use. I've been using a feed reader for a few years, and have gradually come to follow a number of active blogs related to programming, software development, computer science, math, machine learning, and statistics. 

As well as active blogs, however, I've also found blogs and site archives with many old entries of interest to me, but which are no longer (or very rarely) updated. Blogs which are still active often have archives of material I haven't read, in some cases going back a long time before I followed them. For a few examples: [Lambda the Ultimate](http://lambda-the-ultimate.org/), [Matt Might's blog](https://matt.might.net/articles/), [Hillel Wayne's excellent and very-much active blog](https://www.hillelwayne.com/post/), and `[insert whatever blog you'd personally consider to show Good Taste :)]` 

I wanted a way to have those old blog posts and essays occasionally show up in my feed reader, sprinkled in with actual updates from the active blogs I follow. This way, **slowly reading through those old entries is folded into my routine of checking for new articles to read.**

As well as changing the publication date to make an old entry appear newly updated, I ultimately wanted more bells and whistles for Quality Of Life reasons, like being able to show the original publication date in the republished entry titles; specifying random vs. chronological order; toggling whether to keep rebroadcasting entries forever, or stop once every entry has been rebroadcasted; etc.

## Limitations

Some sites' feeds contain all entries ever published, while some only keep the most recent entries: among the feeds of interest to me, it's been about half and half each. For the incomplete feeds, I've just scraped the site with `BeautifulSoup`, generated a complete feed with [`feedgen`](https://github.com/lkiesow/python-feedgen), and then used _that_ as input to `rss-reruns`. Good enough for my purposes.

## Disclaimer

`rssreruns` has been made available on PyPi mostly for my own experience with Python's building and packaging ecosystem, as well as for ease of installation on AWS.

Because it's a personal project, a few decisions were made for learning purposes that I would *not* make for professional work. In particular, `FeedModifier` internally makes use of a wrapper class for interacting with lxml elements, a class I wrote as a personal exercise of Reinventing The Wheel (instead of just using lxml's own `objectify`).

In short, this is a fun little project, not made for Production. See `LICENSE.txt` for the more formal disclaimers.