from jako.models.page import PageData
from jako.models.prompt import Prompt
from jako.preprocess_html import preprocess_html


def translate(data: PageData, keep_cite_ref_a: bool = False):
    html, restore_info = preprocess_html(data.page.text, data.page.title, keep_cite_ref_a=keep_cite_ref_a)

    glossary: list[tuple[str, str]] = []
    for langlink in data.page.langlinks:
        if langlink.lang == "ko":
            glossary.append((data.page.title, langlink.title))
    for link in data.links_langlinks:
        if link.langlinks:
            for langlink in link.langlinks:
                if langlink.lang == "ko":
                    glossary.append((link.title, langlink.title))

    system_prompt = "너는 번역기이다."\
        "漢字,히라가나,가타가나는 반드시 한글로 바꾼다.문장은 존댓말 대신 ~다로 끝낸다."\
        "HTML태그는 그대로 유지하고 특히 id 속성은 번역하지 않는다."\
        "번역을 계속할지 묻지 않는다.번역에 대한 설명을 하지 않는다."
    if glossary:
        system_prompt += "\n\n용어집:"
        for ja, ko in glossary:
            if ja == ko: continue

            # skip latin only
            if all(ord(c) <= 128 for c in ja):
                continue

            # skip dates
            digit_count = sum(1 for c in ja if c.isdigit())
            if digit_count / len(ja) > 0.5:
                continue

            system_prompt += f"\n{ja} = {ko}"
    
    return Prompt(
        system=system_prompt,
        user="다음 내용을 한국어로 번역하고 자연스러운 한국어로 수정하라.\n" + html,
        restore_info=restore_info,
    )
