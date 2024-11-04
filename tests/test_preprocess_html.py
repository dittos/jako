import pytest
from bs4 import BeautifulSoup
from jako.preprocess_html import preprocess_html, restore_html, split_html_chunks


def test_split_html_chunks():
    assert list(split_html_chunks("1234<br>4567", 5)) == ["1234", "<br>", "4567"]
    assert list(split_html_chunks("1234<br>4567", 10)) == ["1234<br>", "4567"]


@pytest.mark.parametrize("keep_cite_ref_a", [True, False])
def test_preprocess_html_simplify_cite_ref(keep_cite_ref_a: bool):
    source = "<sup id=\"cite_ref-3\" class=\"reference\"><a href=\"#cite_note-3\"><span class=\"cite-bracket\">[</span>3<span class=\"cite-bracket\">]</span></a></sup>"
    html, restore_info = preprocess_html(source, "title", keep_cite_ref_a=keep_cite_ref_a)
    html, _title = restore_html(html, restore_info)
    assert BeautifulSoup(html, "html.parser") == BeautifulSoup(source, "html.parser")
