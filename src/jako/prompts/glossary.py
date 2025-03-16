from jako.models.page import PageData


GLOSSARY_BLOCKLIST = {
    "ヒーロー", "ヒロイン", "主人公", "敵",
    "日本", "日本語", "漫画", "日本の漫画", "中国", "映画", "アニメーション",
}


def glossary(html: str, data: PageData) -> str:
    glossary: list[tuple[str, str]] = []
    for langlink in data.page.langlinks:
        if langlink.lang == "ko":
            glossary.append((data.page.title, langlink.title))
    for link in data.links_langlinks:
        if link.langlinks:
            for langlink in link.langlinks:
                if langlink.lang == "ko":
                    glossary.append((link.title, langlink.title))
    
    if not glossary:
        return ""

    system_prompt = ""
    for ja, ko in glossary:
        if ja == ko: continue

        if ja in GLOSSARY_BLOCKLIST:
            continue

        # skip latin only
        if all(ord(c) <= 128 for c in ja):
            continue

        # skip dates
        digit_count = sum(1 for c in ja if c.isdigit())
        if digit_count / len(ja) > 0.5:
            continue

        # skip if not in content
        if ja not in html:
            continue

        system_prompt += f"\n{ja} -> {ko}"

    if not system_prompt:
        return ""

    return f"Glossary:{system_prompt}"
