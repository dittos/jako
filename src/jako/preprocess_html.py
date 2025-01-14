import re
from typing import Any, Iterable
import bs4
from pydantic import BaseModel


class CiteRefRestoreInfo(BaseModel):
    a_attrs: dict[str, str | Any] | None
    pre: str
    post: str


class RestoreInfo(BaseModel):
    metadata_tags: list[str]
    attrs: dict[int, dict[str, str | Any]]
    cite_refs: dict[str, CiteRefRestoreInfo]
    references: dict[str, str] = {}


HTML_FORMATTER = bs4.formatter.HTMLFormatter(
    entity_substitution=bs4.formatter.EntitySubstitution.substitute_xml,
    void_element_close_prefix=None,
    empty_attributes_are_booleans=True,
)


def parse_html(html: str) -> bs4.BeautifulSoup:
    return bs4.BeautifulSoup(html, "html.parser")


def to_html(doc: bs4.BeautifulSoup | bs4.Tag | bs4.NavigableString) -> str:
    if isinstance(doc, bs4.NavigableString):
        return str(doc)
    return doc.decode(formatter=HTML_FORMATTER)


def preprocess_html(html: str, title: str, keep_cite_ref_a: bool = False):
    doc = parse_html(html)

    if title:
        title_tag = doc.new_tag('title')
        title_tag.string = title
        doc.insert(0, title_tag)

    # extract metadata tags
    metadata_tags = []
    for node in doc.find_all(["link", "meta", "style"]):
        metadata_tags.append(to_html(node))
        node.extract()
    
    # remove all comments
    for comment in doc.find_all(string=lambda text: isinstance(text, bs4.Comment)):
        comment.extract()
    
    # remove unnecessary tags
    for node in doc.select(".mw-heading .indicator"):
        node.extract()
    for node in doc.select("h1 > span, h2 > span, h3 > span, h4 > span, h5 > span, h6 > span"):
        if not node.contents:
            node.extract()
    
    # simplify citations
    # <sup class="reference" id="cite_ref-2">
    #   <a href="#cite_note-2">
    #     <span class="cite-bracket">[</span>
    #     2
    #     <span class="cite-bracket">]</span>
    #   </a>
    # </sup>
    # --> <sup id="NODE_ID">2</sup>
    cite_refs = {}
    for cite in doc.find_all("sup", {"class": "reference"}):
        if len(cite.contents) == 1 and cite.contents[0].name == "a":
            a = cite.contents[0]
            if (
                a.contents[0].attrs.get("class") == ["cite-bracket"]
                and a.contents[-1].attrs.get("class", []) == ["cite-bracket"]
            ):
                pre = a.contents[0].extract()
                post = a.contents[-1].extract()
                if not keep_cite_ref_a:
                    a = a.unwrap()
                cite_refs[cite.attrs["id"]] = CiteRefRestoreInfo(
                    a_attrs=None if keep_cite_ref_a else a.attrs,
                    pre=to_html(pre),
                    post=to_html(post),
                )
    
    # simplify references
    # <ol class="references">
    #   <li id="cite_note-15">
    #       <!-- 1 citation case -->
    #       <b><a href="#cite_ref-15">^</a></b>
    #       <!-- 2+ citations case -->
    #       ^ <a href="#cite_ref-..."><sup><i><b>a</b></i></sup></a> <a href="#cite_ref-..."><sup><i><b>b</b></i></sup></a> ...
    #       <span class="reference-text">Reference Text</span>
    #   </li>
    # </ol>
    # -->
    # <ol class="references">
    #   <li id="cite_note-15">Reference Text</li>
    # </ol>
    references = {}
    for ref in doc.select("ol.references > li"):
        ref_id = ref.attrs.get("id")
        if not ref_id: print(ref); raise Exception("reference id not found")
        ref_text = ref.select_one(".reference-text")
        ref_text_contents = list(ref_text.contents)
        ref_text.clear()
        references[ref_id] = ref.decode_contents(formatter=HTML_FORMATTER)
        ref.clear()
        ref.extend(ref_text_contents)

    attrs = {}
    next_node_id = 0
    for node in doc.descendants:
        if not isinstance(node, bs4.Tag):
            continue
        if (
            not node.attrs
            # Gemini 1.5 Flash seems to introduce one-off error often 
            # if id attribute if <b>/<i> and <a id> are mixed, so force id attribute.
            and node.name not in ("b", "i")
        ):
            continue

        node_id = next_node_id
        next_node_id += 1
        attrs[node_id] = node.attrs.copy()
        attrs[node_id]["_tag"] = node.name
        node.attrs.clear()
        node.attrs["id"] = f"{node_id:x}"  # using hex seems to be more robust
    
    return to_html(doc).strip(), RestoreInfo(
        metadata_tags=metadata_tags,
        attrs=attrs,
        cite_refs=cite_refs,
        references=references,
    )


class TagMismatchError(ValueError):
    def __init__(self, node: bs4.Tag, expected_tag: str):
        self.node = node
        self.node_id = node.attrs["id"]
        self.expected_tag = expected_tag
        super().__init__(f"tag mismatch; id={self.node_id}; expected {expected_tag} but {node.name}")


def restore_html(html: str, restore_info: RestoreInfo):
    doc = parse_html(html)

    title_tag = doc.title
    if title_tag:
        title_tag.extract()
        title = title_tag.string
    else:
        title = ""

    for node in doc.descendants:
        if not isinstance(node, bs4.Tag):
            continue

        node_id = node.attrs.get("id")
        if not node_id:
            continue

        int_node_id = int(node_id, 16)
        attrs = restore_info.attrs.get(int_node_id)
        expected_tag = attrs.pop("_tag", None)
        if expected_tag and node.name != expected_tag:
            if node.name == "td":
                first_child = next(node.children, None)
                if first_child is not None and first_child.name == expected_tag and first_child.attrs.get("id") == node_id:
                    continue
            raise TagMismatchError(node, expected_tag=expected_tag)
        node.attrs = attrs
    
    # restore citations
    cite_refs = restore_info.cite_refs
    for cite in doc.find_all("sup", {"class": "reference"}):
        ref_id = cite.attrs.get("id")
        if not ref_id: continue
        ref = cite_refs.get(ref_id)

        if ref.a_attrs is None: # keep_cite_ref_a was True
            a = cite.a
            a.insert(0, parse_html(ref.pre))
            a.append(parse_html(ref.post))
        else:
            new_content = list(cite.contents)
            cite.clear()
            a = doc.new_tag("a", attrs=ref.a_attrs)
            a.append(parse_html(ref.pre))
            a.extend(new_content)
            a.append(parse_html(ref.post))
            cite.append(a)
    
    # restore references
    references = restore_info.references
    for ref in doc.select("ol.references > li"):
        ref_id = ref.attrs.get("id")
        if not ref_id: continue
        placeholder_html = references.get(ref_id)
        if not placeholder_html:
            raise Exception("reference not found: id={ref_id}")
        placeholder = parse_html(placeholder_html)
        ref_text_contents = list(ref.contents)
        ref.clear()
        placeholder.select_one(".reference-text").extend(ref_text_contents)
        ref.extend(placeholder.contents)

    # restore metadata tags
    for expected_tag in restore_info.metadata_tags:
        doc.append(parse_html(expected_tag))
    
    return to_html(doc), title


def split_html_chunks(html: str, chunk_size: int) -> Iterable[str]:
    offset = 0
    while True:
        chunk = html[offset:offset + chunk_size]
        if not chunk: break

        tag_close_idx = chunk.rfind(">")
        tag_open_idx = chunk.rfind("<")
        if tag_close_idx != -1:
            chunk = chunk[:tag_close_idx + 1]
        elif tag_open_idx != -1:
            chunk = chunk[:tag_open_idx]

        assert len(chunk) > 0
        offset += len(chunk)
        yield chunk


def validate_html(html: str, restore_info: RestoreInfo) -> bool:
    doc = parse_html(html)
    
    for node in doc.descendants:
        if not isinstance(node, bs4.Tag):
            continue

        node_id = node.attrs.get("id")
        if not node_id:
            continue

        int_node_id = int(node_id, 16)
        attrs = restore_info.attrs.get(int_node_id)
        tag = attrs.get("_tag", None)
        if tag and node.name != tag:
            print(f"tag mismatch; id={node_id}; expected {tag} but {node.name}")
            return False
    
    return True


def strip_broken_tag(html: str):
    open_idx = html.rfind('<')
    if open_idx == -1:
        return html
    
    close_idx = html.rfind('>')
    if close_idx == -1 or close_idx < open_idx:
        return html[:open_idx]

    return html


def split_mediawiki_html_sections(html: str) -> list[str]:
    doc = parse_html(html)

    # MediaWiki HTML has the following format:
    #
    # <div class="mw-content-ltr mw-parser-output" lang="ja" dir="ltr">
    #   <section class="mf-section-0" id="mf-section-0">...</section>
    #
    #   <div class="mw-heading mw-heading2 section-heading" onclick="mfTempOpenSection(1)">...</div>
    #   <section class="mf-section-1 collapsible-block" id="mf-section-1">...</section>
    #
    #   <div class="mw-heading mw-heading2 section-heading" onclick="mfTempOpenSection(2)">...</div>
    #   <section class="mf-section-2 collapsible-block" id="mf-section-2">...</section>
    #
    #   ...
    # </div>

    roots = list(iterate_effective_children(doc))
    assert len(roots) == 1
    root = roots[0]
    assert root.name == "div" and "mw-parser-output" in root.attrs["class"]

    iterator = iterate_effective_children(root)

    def read_section():
        section = next(iterator, None)
        if section is None: return None
        assert section.name == "section"
        return section

    def read_heading():
        heading = next(iterator, None)
        if heading is None: return None
        assert heading.name == "div" and "section-heading" in heading.attrs["class"]
        return heading
    
    sections = []
    sections.append(to_html(read_section()))

    while True:
        heading = read_heading()
        if heading is None: break
        section = read_section()
        assert section
        sections.append(to_html(heading) + to_html(section))
    
    return sections


def iterate_effective_children(doc: bs4.BeautifulSoup):
    return filter_effective_children(doc.children)


def filter_effective_children(children: Iterable[bs4.PageElement]):
    for child in children:
        if isinstance(child, bs4.NavigableString):
            if not any(string.strip() for string in child.strings):
                continue
        if isinstance(child, bs4.Comment):
            continue
        
        yield child


def preprocess_split_html(html: str, title: str, size: int, keep_cite_ref_a: bool = False) -> tuple[list[str], RestoreInfo]:
    html, restore_info = preprocess_html(html, title=title, keep_cite_ref_a=keep_cite_ref_a)
    doc = parse_html(html)
    can_split_div_classes = {"section-heading", "toc", "reflist", "thumb", "thumbinner", "mw-parser-output", "NavFrame", "NavContent"}

    def _can_split(node: bs4.Tag):
        if node.name in ("section", "dl", "ul", "ol", "table", "tbody"):
            return True
        if node.name == "li":
            if node.select_one("ul, ol"):
                return True
        if node.name == "div":
            node_id = node.attrs.get("id")
            if not node_id:
                return False
            
            int_node_id = int(node_id, 16)
            attrs = restore_info.attrs.get(int_node_id)

            if "class" in attrs:
                if any(cls in can_split_div_classes for cls in attrs["class"]):
                    return True
        return False

    def _split_html(children: list[bs4.PageElement]):
        for child in filter_effective_children(children):
            if isinstance(child, bs4.Tag) and _can_split(child):
                children = list(child.children)
                child = child.unwrap()
                start, end = to_html(child).split("</")
                yield start
                yield from _split_html(children)
                if end:
                    yield f"</{end}\n"
            else:
                yield to_html(child)

    chunks = []
    buf = ""
    for part in _split_html(list(doc.children)):
        part_len = len(part)
        if buf and len(buf) + part_len > size:
            chunks.append(buf)
            buf = ""
        buf += part
    if buf:
        chunks.append(buf)
    
    return chunks, restore_info


START_TAGS_PATTERN = re.compile(r'^(\s*<[a-z]+>)+')
END_TAGS_PATTERN = re.compile(r'(</[a-z]+>\s*)+$')


def recover_start_end_tags(original: str, response: str) -> str:
    response = response.replace("```html", "").replace("```", "")
    
    original_end_tags = END_TAGS_PATTERN.search(original)
    if original_end_tags:
        original_end_tags = original_end_tags.group()
    else:
        original_end_tags = ""
    
    original_start_tags = START_TAGS_PATTERN.search(original)
    if original_start_tags:
        original_start_tags = original_start_tags.group()
    else:
        original_start_tags = ""
    
    response_start_tags = START_TAGS_PATTERN.search(response)
    start_pos = response_start_tags.end() if response_start_tags else 0

    response_end_tags = END_TAGS_PATTERN.search(response)
    end_pos = response_end_tags.start() if response_end_tags else len(response)

    return original_start_tags + response[start_pos:end_pos] + original_end_tags
