"""Helper class for working with lxml ETrees and Elements.

This is Reinventing The Wheel as a personal exercise -- if this were Real or Serious,
i.e. anyone else was ever going to work with it, I would have just used lxml.Objectify,
which is a robust, time-tested, much-better-designed take on an API for XML trees that
resembles normal Python objects.
(https://lxml.de/objectify.html)

(I thought "why can't I interact with the tree like indexing a dictionary / accessing an
attribute?", and then it turned out that lxml already had that, but I wanted to write my
own implementation anyway. Mostly so I had a chance to write more dunder methods than I
usually have reason to, haha.)
"""
from __future__ import annotations

import functools
import re
from typing import Optional

from lxml import etree as ET

# Underscores present because those are the class names in lxml.etree
Element = ET._Element
ElementTree = ET._ElementTree

# Regex matching names of the form
#   "{namespace}localname"
clark_notation = re.compile(r"\{\S*\}\S*")
# extract "namespace", "localname" as groups 1 and 2
clark_notation_groups = re.compile(r"\{(\S*)\}(\S*)")

# Sentinel indicating "use the ElementWrapper's prefix attribute"
_USE_WRAPPER_NAMESPACE = object()
# Alias for an empty string, which for ElementWrapper is the 'prefix' of a
# default namespace
_USE_DEFAULT_NAMESPACE = ""
# (lxml represents the prefix of a default namespace as None, but for the wrapper's
# purposes, being given a None prefix in a (None, "localname") tuple corresponds to
# No Namespace, while simply not being given a namespace ("localname") indicates
# "use the wrapper's namespace"
_USE_NO_NAMESPACE = None


def try_unpack(func):
    """Replace the original method's first argument with a different representation.

    This decorator is applied to methods whose first (non-self) argument is the name of
    a subelement to be accessed. This subelement name may be namespaced, but may or
    may not have been given with a particular namespace or namespace prefix. The
    original argument is replaced with a corresponding QName if needed.

    All other args and kwargs are passed along as given.

    The subelement name may have been given in the following forms:

    "localname"
        Single string with no namespace specified. The ElementWrapper's preferred
        namespace will be used with the given localname to create a qualified name
        (QName) corresponding to a subelement with that localname in that namespace.

    (None, "localname")
        A prefix of None indicates that no namespace should be used. This may have been
        passed explicitly because the ElementWrapper's prefix attribute specifies a
        namespace.

    ("prefix", "localname")
        Tuple of prefix and localname. These are unpacked and used to create a
        QName replacing the original argument.

    ("uri", "localname")
        Tuple of namespace and localname. Again, these are unpacked and turned into an
        equivalent QName.

    "prefix:localname"
        Single string with a prefix separating the namespace prefix and localname. The
        prefix and localname will are used to create a QName for the subelement.

    "{uri}localname"
        Single string with the namespace URI itself given in braces, i.e.  "Clark
        Notation." This form is unambiguous and may be used as-is.
    """

    @functools.wraps(func)
    def wrapper(self, subelement_name, *args, **kwargs):
        name = subelement_name
        # This would be more Pythonic as a try/except attempting to unpack
        #
        #   prefix, name = subelement_name
        #
        # and catching `ValueError: too many values to unpack (expected 2)` when
        # subelement_name is just a string, and not actually a tuple of (prefix, name).
        #
        # Unfortunately, this will unpack a string of length 2.
        # E.g. for subelement_name = 'ab', this would result in
        #
        #   prefix, name = 'a', 'b'
        #
        # instead of raising and then catching a ValueError like it would for a string
        # of any other length != 2.
        #
        # So, unfortunately, the more Pythonic Way has different behavior which is
        # undesirable here. :(
        if isinstance(subelement_name, tuple):
            # Unpack the name if it is a (prefix, localname), (uri, localname), or
            # (None, localname) pair
            prefix_or_uri, name = subelement_name
            name = self._QName(name, prefix_or_uri)
        elif clark_notation.fullmatch(name):
            # An expanded name given in Clark notation may be used as-is
            pass
        elif ":" in name:
            # If the given name is of the form "prefix:localname", obtain the
            # equivalent QName
            # (Namespace URIs may contain colons, but prefixes cannot, so names
            # of the form prefix:localname will contain only one colon)
            prefix, name = name.split(":", maxsplit=1)
            name = self._QName(name, prefix)
        else:
            # Otherwise, with no prefix specified, the ElementWrapper's own prefix
            # attribute will be used
            name = self._QName(name, _USE_WRAPPER_NAMESPACE)

        return func(self, name, *args, **kwargs)

    return wrapper


class ElementWrapper:
    """TODO."""

    def __init__(self, element: Element, with_prefix):
        """Initialization."""
        self.__dict__["_element"] = element
        if with_prefix is None and None in element.nsmap:
            # If None is in the element's nsmap, the None indicates a default namespace
            self.__dict__["_with_prefix"] = _USE_DEFAULT_NAMESPACE
        elif with_prefix is None and None not in element.nsmap:
            # Otherwise, None indicates using no namespace
            self.__dict__["_with_prefix"] = _USE_NO_NAMESPACE
        else:
            self.__dict__["_with_prefix"] = with_prefix

    @try_unpack
    def __getitem__(self, subelement_name: str | ET.QName) -> "ElementWrapper":
        """Index into a given subelement."""
        found = self._get_or_create_subelement(self._element, subelement_name)
        return ElementWrapper(found, found.prefix)

    @try_unpack
    def __setitem__(self, subelement_name, value):
        """Set the (text) value of a given subelement."""
        self._set_subelement_text(self._element, subelement_name, str(value))
        pass

    @try_unpack
    def __delitem__(self, subelement_name: str | ET.QName) -> None:
        """Remove a given subelement."""
        found = self._maybe_get_subelement(self._element, subelement_name)
        if found is not None:
            self._element.remove(found)
        pass

    @try_unpack
    def iterfind(self, subelement_name: str | ET.QName) -> list["ElementWrapper"]:
        """Find subelements matching a given name."""
        results = self._element.iterfind(subelement_name)
        return [ElementWrapper(found, found.prefix) for found in results]

    @try_unpack
    def iterdescendants(
        self, subelement_name: str | ET.QName
    ) -> list["ElementWrapper"]:
        """Find descendants matching a given name."""
        results = self._element.iterdescendants(subelement_name)
        return [ElementWrapper(found, found.prefix) for found in results]

    @try_unpack
    def create_subelement(self, subelement_name: str | ET.QName) -> "ElementWrapper":
        """Create a new subelement with the given name, even if others already exist."""
        created = ET.SubElement(self._element, subelement_name)
        return ElementWrapper(created, created.prefix)

    @try_unpack
    def __contains__(self, subelement_name) -> bool:
        """Return if there is a subelement with the given name (i.e. `name in self`)."""
        return self._maybe_get_subelement(self._element, subelement_name) is not None

    def __getattr__(self, attr):
        """Retrieve attributes of the underlying Element object.

        If the Element object has no such attribute, try to access the value of
        the XML element for the given attribute name, i.e. `my_elementwrapper.attrib`
        evaluates to "Value" for an element <tagname attrib="Value"/>.
        """
        try:
            return self._element.__getattribute__(attr)
        except AttributeError:
            return self._element.get(key=attr)

    def __setattr__(self, attr, value):
        """Set attribute of the underlying Element object.

        If the Element object has no such attribute, set the value of
        the XML element for the given attribute name, i.e.
        `my_elementwrapper.attrib = value` sets <tagname attrib="value"/>.
        """
        if attr in self._element or attr == "text":
            self._element.__setattr__(attr, value)
        else:
            self._element.set(key=attr, value=str(value))

    def remove_attribute(self, attr):
        """Remove attribute from the element if present."""
        if attr in self._element.attrib:
            self._element.attrib.pop(attr)
        pass

    def _get_subelement(self, element, subelement_name: ET.QName | str) -> Element:
        """Get the wrapped element's subelement.

        Args:
            subelement_name (ET.QName | str):
                Name of the subelement to find.

        Returns:
            Element: the found subelement.

        Raises:
            ValueError: If the subelement is not found.
        """
        found = element.find(str(subelement_name), self._nsmap())
        if found is None:
            raise ValueError(
                f"Could not find required subelement: {str(subelement_name)}."
            )
        return found

    def _set_subelement_text(
        self, element: Element, subelement_name: str | ET.QName, text: str
    ) -> Element:
        """Update the text of a specified entry's subelement.

        If no subelement with the specified name is found, add the subelement before
        setting its text.

        Args:
            entry (Element):
                Parent XML element whose subelement is to be updated.
            subelement_name (str | ET.QName):
                Name of the subelement to update.
            text (str):
                Text to be enclosed by the specified subelement.

        Returns:
            Element: the modified (possibly newly created) subelement.
        """
        subelement = self._get_or_create_subelement(element, subelement_name)
        # if subelement is None:
        #     subelement = ET.SubElement(element, subelement_name)

        subelement.text = text
        return subelement

    def _maybe_get_subelement(
        self, element: Element, subelement_name: ET.QName | str
    ) -> Optional[Element]:
        """Get a specified element's subelement.

        The only reason this one-line method exists is to avoid the visual noise of
        repeatedly providing `self._nsmap` as an argument to Element's `find`.
        Otherwise, `find` would be used directly each time, instead of calling this.

        Args:
            entry (Element):
                Parent XML element whose subelement is to be found.
            subelement_name (ET.QName | str):
                Name of the subelement to find.

        Returns:
            Optional[Element]: the found subelement, or None if not found.
        """
        return element.find(str(subelement_name), self._nsmap())

    def _default_subelement_text(
        self, element: Element, subelement_name: str | ET.QName, text: str
    ) -> Element:
        """Set the text of a specified entry's subelement only if no text is present."""
        subelement = self._get_or_create_subelement(element, subelement_name)
        subelement.text = subelement.text or text
        return subelement

    def _get_or_create_subelement(
        self, element: Element, subelement_name: ET.QName | str
    ) -> Element:
        """Get a specified element's subelement, or add it if not found.

        Args:
            entry (Element):
                Parent XML element whose subelement is to be found.
            subelement_name (ET.QName | str):
                Name of the subelement to find.

        Returns:
           Element: the found or created subelement.
        """
        subelement = self._maybe_get_subelement(element, subelement_name)
        if subelement is not None:
            return subelement
        else:
            # Create missing subelement
            return ET.SubElement(element, subelement_name)

    def _QName(self, name: str, prefix_or_uri=_USE_WRAPPER_NAMESPACE) -> ET.QName | str:
        """Creates qualified name of a given tag in the `reruns` namespace."""
        if prefix_or_uri is _USE_WRAPPER_NAMESPACE:
            # Use the wrapper's namespace setting, possibly No Namespace
            prefix_or_uri = self._with_prefix
        if prefix_or_uri is _USE_NO_NAMESPACE:
            # Return the unqualified name
            return name
        if prefix_or_uri in self._nsmap():
            # Convert the prefix to a URI before using
            return ET.QName(self._nsmap()[prefix_or_uri], name)
        elif prefix_or_uri in self._nsmap().values():
            # Given a namespace URI
            return ET.QName(prefix_or_uri, name)
        else:
            raise ValueError(
                "Argument `prefix_or_uri` could not be determined to be a namespace "
                f"prefix or URI: '{prefix_or_uri}' not found in keys or values of "
                f"namespace map {self._nsmap()}."
            )

    def _nsmap(self) -> dict[str, str]:
        """Get dictionary of XML namespaces to use with `find()`, `findall()`, etc.

        The 'cleaning' is due to the representation of a Default Namespace
        in the `element.nsmap` dictionary -- if there is a default namespace, its
        key is `None` rather than an empty string.

        This makes Mypy find its keys to have type `Optional[str]` instead of `str`,
        which unfortunately makes it believe the dictionary is incompatible with the
        type signature of the Element methods `find()`, `findall()`, etc.

        For the purposes of `ElementWrapper`, a namespace prefix of None indicates
        'use the ElementWrapper's preferred prefix', not 'use the xml element's Default
        Namespace'.
        """
        return self._clean_nsmap(self._element.nsmap)

    def _clean_nsmap(self, nsmap: dict[Optional[str], str]) -> dict[str, str]:
        """Replace a `None` key an with empty string if encountered."""
        return {(k or _USE_DEFAULT_NAMESPACE): v for k, v in nsmap.items()}

    def clear_xml_base(self) -> None:
        """Reset xml:base to an empty string if a base URI is declared or inherited."""
        if self._element.base:
            self._element.base = ""
        pass


class ElementWrapperFactory:
    """Create ElementWrappers with a given preferred prefix."""

    def __init__(self, with_prefix):
        """Initialization."""
        self._with_prefix = with_prefix

    def __call__(self, element: Element | ElementWrapper) -> ElementWrapper:
        """Return an ElementWrapper with the factory's preferred prefix."""
        if isinstance(element, ElementWrapper):
            return ElementWrapper(element._element, self._with_prefix)
        return ElementWrapper(element, self._with_prefix)
