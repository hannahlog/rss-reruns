# Changelog

## [0.0.14] - 2023-04-27

### Changed

- Expanded README exposition and added a screenshot of generated feeds as they appear in Feedly.

## [0.0.13] - 2023-04-19

### Fixed

- Fixed error introduced in version 0.0.12 causing `reruns` namespace elements to not be removed when appropriate in `write()`

## [0.0.12] - 2023-04-19

### Changed

- Calling `write()` with `with_reruns_data=False` now strips entries that have not yet been rebroadcasted. (Previously, this setting only stripped elements in the `reruns` namespace)

## [0.0.11] - 2023-03-24

### Fixed

- Fixed erroneous creation of non-Atom `guid` elements when updating Atom entry `id` subelements

## [0.0.10] - 2023-03-22

### Added

- Added initialization options to overwrite all of the original entry pubdates (even before doing any rebroadcasting), and also to add the rebroadcasted feed's url as an `<atom:link rel="self">` element. (These are further attempts to convince feedly to poll the rebroadcast feed more often)

## [0.0.9] - 2023-03-21

### Added

- Added generation of new id/guid when an entry is rebroadcasted (attempt to solve issue of feedly not recognizing feed updates that show up successfully in other feed readers, apparently related to feedly's caching strategy)

## [0.0.8] - 2023-03-16

### Fixed

- Fixed `feed_type()` and test cases

## [0.0.7] - 2023-03-16

### Added

- Added `source_url()` method to get the feed source url (handling base URIs for Atom feeds properly when needed), along with test cases
- Added `feed_type()` convenience method to return the type of feed as a string, "RSS" or "Atom", along with test cases

## [0.0.6] - 2023-03-08

### Added

- Added optional `pretty_print` keyword argument to `FeedModifier.write()`, with default value `True`

### Changed

- Feed and entry title prefixes/suffixes now treat empty strings the same way they treat `None`: neither are used in the actual generated titles. Prefixes and suffixes set to `""` will now result in the same titles as if they had been set to `None`

## [0.0.5] - 2023-03-08

### Changed

- Changed behavior of `FeedModifier.__getitem__` to raise a `KeyError` when no subelement of the given name exists, instead of creating and returning the subelement 
- Changed default values of `title_prefix` and `entry_title_[prefix/suffix]` from the prior arbitrary defaults to `None`

## [0.0.4] - 2023-03-03

### Added

- Added `num_remaining` method to FeedModifier instances.

## [0.0.3] - 2023-02-28

### Added

- Added support for downloading, parsing, and outputting feeds as strings (without needing to read from / write to file)

## [0.0.2] - 2023-01-25

### Fixed

- Fixed compatibility for Python 3.7-3.9

### Added

- Added Tox for running tests with Python 3.7-3.11
- Added changelog

## [0.0.1] - 2023-01-21

- First release of `rssreruns`
