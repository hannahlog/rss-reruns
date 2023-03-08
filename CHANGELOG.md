# Changelog

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
