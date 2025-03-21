from pathlib import Path
import pytest
from bs4 import BeautifulSoup
from jako.preprocess_html import preprocess_html, recover_start_end_tags, restore_html, split_html_chunks, split_mediawiki_html_sections, strip_broken_tag


def test_split_html_chunks():
    assert list(split_html_chunks("1234<br>4567", 5)) == ["1234", "<br>", "4567"]
    assert list(split_html_chunks("1234<br>4567", 10)) == ["1234<br>", "4567"]


@pytest.mark.parametrize("keep_cite_ref_a", [True, False])
def test_preprocess_html_simplify_cite_ref(keep_cite_ref_a: bool):
    source = "<sup id=\"cite_ref-3\" class=\"reference\"><a href=\"#cite_note-3\"><span class=\"cite-bracket\">[</span>3<span class=\"cite-bracket\">]</span></a></sup>"
    html, restore_info = preprocess_html(source, "title", keep_cite_ref_a=keep_cite_ref_a)
    html, _title = restore_html(html, restore_info)
    assert BeautifulSoup(html, "html.parser") == BeautifulSoup(source, "html.parser")


def test_preprocess_html_simplify_references():
    source = """<ol class="references"><li id="cite_note-15"><b><a href="#cite_ref-15">^</a></b> <span class="reference-text">Reference Text</span></li></ol>"""
    html, restore_info = preprocess_html(source, "title")
    assert restore_info.references["cite_note-15"] == '<b><a href="#cite_ref-15">^</a></b> <span class="reference-text"></span>'
    html, _title = restore_html(html, restore_info)
    assert BeautifulSoup(html, "html.parser") == BeautifulSoup(source, "html.parser")

    source = """<ol class="references"><li id="cite_note-15">^ <a href="#cite_ref-..."><sup><i><b>a</b></i></sup></a> <a href="#cite_ref-..."><sup><i><b>b</b></i></sup></a> <span class="reference-text">Reference Text</span></li></ol>"""
    html, restore_info = preprocess_html(source, "title")
    assert restore_info.references["cite_note-15"] == '^ <a href="#cite_ref-..."><sup><i><b>a</b></i></sup></a> <a href="#cite_ref-..."><sup><i><b>b</b></i></sup></a> <span class="reference-text"></span>'
    html, _title = restore_html(html, restore_info)
    assert BeautifulSoup(html, "html.parser") == BeautifulSoup(source, "html.parser")


def test_strip_broken_tag():
    assert strip_broken_tag('pre') == 'pre'
    assert strip_broken_tag('pre<a href="hi"') == 'pre'
    assert strip_broken_tag('pre<a href="hi">') == 'pre<a href="hi">'
    assert strip_broken_tag('pre<a href="hi">li') == 'pre<a href="hi">li'
    assert strip_broken_tag('pre<a href="hi">link') == 'pre<a href="hi">link'
    assert strip_broken_tag('pre<a href="hi">link<') == 'pre<a href="hi">link'
    assert strip_broken_tag('pre<a href="hi">link</') == 'pre<a href="hi">link'
    assert strip_broken_tag('pre<a href="hi">link</a') == 'pre<a href="hi">link'
    assert strip_broken_tag('pre<a href="hi">link</a>') == 'pre<a href="hi">link</a>'


def test_split_mediawiki_html_sections():
    sample_path = Path(__file__).parent / "resources" / "mediawiki_sample.html"
    sections = split_mediawiki_html_sections(sample_path.read_text())
    assert len(sections) == 7


def test_recover_start_end_tags():
    assert recover_start_end_tags("hi", "hi") == "hi"
    assert recover_start_end_tags("<section>hi", "<section>hi") == "<section>hi"
    assert recover_start_end_tags("<section>hi", "<section>hi</section>") == "<section>hi"
    assert recover_start_end_tags("<tr>\n<td>hi</td>\n</tr>", "<table><tr><td>hi</td></tr></table>") == "<tr>\n<td>hi</td>\n</tr>"
    assert recover_start_end_tags("<title>title</title>hi", "<!DOCTYPE html>\n<html>\n<head>\n<title>title</title>\n</head>\n<body>\nhi</body></html>") == "<title>title</title>hi"
