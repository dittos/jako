from typing import Iterable
import bs4

from jako.models.prompt import CiteRefRestoreInfo, RestoreInfo

__all__ = ["preprocess_html", "restore_html"]

HTML_FORMATTER = bs4.formatter.HTMLFormatter(
    entity_substitution=bs4.formatter.EntitySubstitution.substitute_xml,
    void_element_close_prefix=None,
    empty_attributes_are_booleans=True,
)


def parse_html(html: str) -> bs4.BeautifulSoup:
    return bs4.BeautifulSoup(html, "html.parser")


def to_html(doc: bs4.BeautifulSoup | bs4.Tag) -> str:
    return doc.decode(formatter=HTML_FORMATTER)


def preprocess_html(html: str, title: str, keep_cite_ref_a: bool = False):
    doc = parse_html(html)

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

    attrs = {}
    next_node_id = 0
    for node in doc.descendants:
        if not isinstance(node, bs4.Tag) or not node.attrs:
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
    )


def restore_html(html: str, restore_info: RestoreInfo):
    doc = parse_html(html)

    title_tag = doc.title.extract()
    title = title_tag.string

    for node in doc.descendants:
        if not isinstance(node, bs4.Tag):
            continue

        node_id = node.attrs.get("id")
        if not node_id:
            continue

        int_node_id = int(node_id, 16)
        attrs = restore_info.attrs.get(int_node_id)
        tag = attrs.pop("_tag", None)
        if tag and node.name != tag:
            raise ValueError(f"tag mismatch; id={node_id}; expected {tag} but {node.name}")
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

    # restore metadata tags
    for tag in restore_info.metadata_tags:
        doc.append(parse_html(tag))
    
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
