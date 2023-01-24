"""ElementWrapper test cases (with PyTest)."""
from __future__ import annotations

from pathlib import Path

from lxml import etree as ET

from rssreruns.elementwrapper import ElementWrapper, ElementWrapperFactory

tmp_dir = Path("test/tmp/")
tmp_dir.mkdir(exist_ok=True)
data_dir = Path("test/elementwrapper/")

parser = ET.XMLParser(remove_blank_text=True)


def test_elementwrapper_getitem_existing_subelements():
    """Basic functionality of __getitem__ to access existing subelements."""
    html = "<html><head/><body><h1>Heading</h1><p>Hello!</p><hr/></body></html>"
    html_root = ET.XML(html)
    html_tree = html_root.getroottree()

    wrapped_root = ElementWrapper(html_root, None)
    assert wrapped_root._element.tag == "html"
    assert wrapped_root._element.text is None

    wrapped_body = wrapped_root["body"]
    assert wrapped_body._element.tag == "body"
    assert wrapped_body._element.text is None

    wrapped_p = wrapped_root["body"]["p"]
    also_wrapped_p = wrapped_body["p"]
    assert wrapped_p._element.tag == "p"
    assert also_wrapped_p._element.tag == "p"
    assert wrapped_p._element.text == "Hello!"

    # Sanity check that __getitem__ has not *modified* the tree.
    html_after = ET.tounicode(html_tree)
    assert html == html_after


def test_elementwrapper_getitem_default_namespace():
    """Functionality of __getitem__ to access default-namespaced subelements."""
    tree = ET.parse(data_dir / "default_namespace.xml", parser=parser)
    root = tree.getroot()
    xml_before = ET.tounicode(tree)

    # From <book xmlns='urn:loc.gov:books' xmlns:isbn='urn:ISBN:0-395-36341-6'>:
    # Default namespace
    default_prefix = ""
    default_uri = "urn:loc.gov:books"
    # Other namespace
    isbn_prefix = "isbn"
    isbn_uri = "urn:ISBN:0-395-36341-6"

    # Factory for ElementWrappers in the default namespace
    default_EWF = ElementWrapperFactory(default_prefix)

    # Subelement access will use the default namespace, unless another namespace prefix
    # or URI is given explicitly
    wrapped_root_default = default_EWF(root)
    assert wrapped_root_default._with_prefix == ""

    # Subelements in the default namespace should be accessible with or without the
    # prefix (or URI) given explicitly
    for arg in [
        "title",
        ("", "title"),
        f"{{{default_uri}}}title",
        (default_uri, "title"),
    ]:
        assert wrapped_root_default[arg].text == "Cheaper by the Dozen"

    # Subelements in the `isbn` namespace should still be accessible by explicitly
    # giving that prefix or URI
    for arg in [("isbn", "number"), f"{{{isbn_uri}}}number", (isbn_uri, "number")]:
        assert wrapped_root_default[arg].text == "1568491379"

    # Returned ElementWrappers for subelements in a different namespace should be
    # initialized in that other namespace
    wrapped_number: ElementWrapper = wrapped_root_default["isbn", "number"]
    assert wrapped_number._with_prefix == "isbn"

    # Factory for ElementWrappers in the other namespace
    isbn_EWF = ElementWrapperFactory(isbn_prefix)

    # The wrapped element (the root) is in the default namespace, but its methods
    # accessing subelements will use the `isbn` namespace, unless another namespace
    # prefix is explicitly given
    wrapped_root_isbn = isbn_EWF(root)
    assert wrapped_root_isbn._with_prefix == "isbn"

    # Its subelement in the isbn namespace, "isbn:number", can be accessed by
    # giving "number" alone, though supplying the prefix or URI explicitly is still fine
    for arg in ["number", ("isbn", "number"), "isbn:number", f"{{{isbn_uri}}}number"]:
        assert wrapped_root_isbn[arg].text == "1568491379"

    # Subelements in other namespaces can only be accessed by explicitly providing
    # a prefix or URI
    for arg in [("", "title"), f"{{{default_uri}}}title", (default_uri, "title")]:
        assert wrapped_root_isbn[arg].text == "Cheaper by the Dozen"

    # Returned ElementWrappers are initialized with the correct prefixes
    assert wrapped_root_isbn["", "title"]._with_prefix == ""

    # Sanity check that the tree has not been modified by __getitem__
    xml_after = ET.tounicode(tree)
    assert xml_before == xml_after


def test_elementwrapper_getitem_default_namespace_redeclared():
    """Functionality of __getitem__ when a subtree declares a new default namespace."""
    parser = ET.XMLParser(remove_blank_text=True)
    tree = ET.parse(data_dir / "default_namespace.xml", parser=parser)
    root = tree.getroot()
    xml_before = ET.tounicode(tree)

    # Factory for ElementWrappers in the original default namespace
    default_EWF = ElementWrapperFactory("")
    wrapped_notes_default = default_EWF(root)["notes"]

    # The <{urn:loc.gov:books}notes> element has a subtree with a new default namespace:
    #   <p xmlns='http://www.w3.org/1999/xhtml'>Book is <i>funny!</i></p>
    # The paragraph may be accessed by explicitly giving the expanded name in Clark
    # Notation: "{http://www.w3.org/1999/xhtml}p"
    p_default_uri = "http://www.w3.org/1999/xhtml"
    wrapped_p_new_default = wrapped_notes_default[f"{{{p_default_uri}}}p"]
    assert wrapped_p_new_default.text == "Book is "
    assert wrapped_p_new_default._with_prefix == ""

    # Its subelement <i> is in the new default namespace. Since the ElementWrapper
    # for <p> will use <p>'s nsmap, its subelement can be accessed without providing
    # the new default namespace explicitly
    for arg in ["i", ("", "i"), (p_default_uri, "i"), f"{{{p_default_uri}}}i"]:
        wrapped_i_new_default = wrapped_p_new_default["i"]
        assert wrapped_i_new_default.text == "funny!"
        assert wrapped_i_new_default._with_prefix == ""

    # Sanity check that __getitem__ has not modified the tree
    xml_after = ET.tounicode(tree)
    assert xml_before == xml_after


def test_elementwrapper_delitem_default_namespace():
    """Functionality of __deltem__ to delete default-namespaced subelements."""
    tree = ET.parse(data_dir / "default_namespace.xml", parser=parser)
    root = tree.getroot()

    # Default namespace prefix
    default_prefix = ""

    # ElementWrapper for the root, with the default namespace preferred
    default_EWF = ElementWrapperFactory(default_prefix)
    root_default = default_EWF(root)

    # Delete <isbn:number>
    del root_default["isbn", "number"]

    # Delete <p xmlns='http://www.w3.org/1999/xhtml'>Book is <i>funny!</i></p>
    del root_default["notes"]["{http://www.w3.org/1999/xhtml}p"]

    # Delete the <div>
    del root_default["notes"]["p"]["div"]

    # Compare with expected XML file
    expected_tree = ET.parse(
        data_dir / "default_namespace_after_deletions.xml", parser=parser
    )
    assert ET.tounicode(tree) == ET.tounicode(expected_tree)


def test_elementwrapper_setitem_existing_subelements():
    """Basic functionality of __setitem__ to modify text of existing subelements."""
    html = "<html><head/><body><h1>Heading</h1><p>Hello!</p><hr/></body></html>"
    html_root = ET.XML(html)
    html_tree = html_root.getroottree()

    wrapped_root = ElementWrapper(html_root, None)

    wrapped_body = wrapped_root["body"]
    wrapped_p = wrapped_body["p"]
    wrapped_body["p"] = "Goodbye!"
    assert wrapped_body["p"].text == "Goodbye!"
    assert wrapped_p._element.text == "Goodbye!"

    edited_html = ET.tounicode(html_tree)
    assert (
        edited_html
        == "<html><head/><body><h1>Heading</h1><p>Goodbye!</p><hr/></body></html>"
    )


def test_elementwrapper_setitem_missing_subelements():
    """Using __setitem__ to create a subelement with given text."""
    html = "<html><head/><body><h1>Heading</h1><p></p><hr/></body></html>"
    html_root = ET.XML(html)
    html_tree = html_root.getroottree()

    wrapped_root = ElementWrapper(html_root, None)

    # `<p></p>` has no text or subelement at this point
    wrapped_p = wrapped_root["body"]["p"]

    # Inserts a subelement `<b>Bold text!</b>`
    wrapped_p["b"] = "Bold text!"
    assert wrapped_p["b"].text == "Bold text!"
    wrapped_b = wrapped_p["b"]
    assert wrapped_b.text == "Bold text!"
    assert wrapped_b._element.text == "Bold text!"

    # Confirm the tree as a whole has the expected change from <p/> to
    #   <p><b>Bold text!</b></p>
    # and only that change
    edited_html = ET.tounicode(html_tree)
    expected_html = (
        "<html><head/><body><h1>Heading</h1>"
        "<p><b>Bold text!</b></p>"
        "<hr/></body></html>"
    )
    assert edited_html == expected_html


def test_getattr():
    """Use __getattr__ to access an attribute of the underlying Element."""
    html = (
        "<html><head/><body>"
        '<a href="example.org">'
        '<img src="example.gif" alt="Alt text"/>'
        "</a></body></html>"
    )
    html_root = ET.XML(html)
    html_tree = html_root.getroottree()

    wrapped_root = ElementWrapper(html_root, None)
    wrapped_a = wrapped_root["body"]["a"]

    # An ElementWrapper has no method `values()` but its Element does
    a_values = list(wrapped_a.values())
    assert a_values == ["example.org"]
    also_a_values = list(wrapped_a._element.values())
    assert also_a_values == ["example.org"]

    # Similarly, call the `img` Element's method
    #   get(self, key, default=None)
    # for the keys 'src' and 'alt'
    src = wrapped_a["img"].get("src")
    assert src == "example.gif"
    alt_text = wrapped_a["img"].get("alt")
    assert alt_text == "Alt text"

    # Sanity check that this has not modified the tree
    html_out = ET.tounicode(html_tree)
    assert html == html_out
