"""Rebroadcast old RSS/Atom items to a new feed, in shuffled or chronological order."""
# For the sake of Python versions < 3.10 (for stdlib generics and | for type unions)
from __future__ import annotations

from .feedmodifier import FeedModifier

__all__ = ["FeedModifier"]
