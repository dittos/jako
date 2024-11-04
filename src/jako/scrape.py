from collections import defaultdict
from datetime import datetime
from typing import Iterable
import requests

from jako.models.page import Page, PageLanglinks, PageData

API_URL = "https://ja.wikipedia.org/w/api.php"
SESSION = requests.Session()
SESSION.headers["user-agent"] = f"Jako/0.1 (github.com/dittos) {SESSION.headers['user-agent']}"


def call_api(params: dict):
    response = SESSION.get(API_URL, params=params)
    if not response:
        print(f"error response: {response.text}")
        response.raise_for_status()
    return response.json()


def parse_page(page: str) -> Page:
    # https://www.mediawiki.org/wiki/API:Parsing_wikitext
    data = call_api({
        "action": "parse",
        "page": page,
        "formatversion": "2",
        "format": "json",
        # "parsoid": "true",
        "mobileformat": "true",
        "disableeditsection": "true",
        "redirects": "true",
    })
    return Page.model_validate(data["parse"])


def batch_get_page_langlinks(titles: list[str], lang: str) -> list[PageLanglinks]:
    # https://www.mediawiki.org/wiki/API:Query
    params = {
        "action": "query",
        "titles": "|".join(titles),
        "formatversion": "2",
        "format": "json",
        "prop": "langlinks",
        "lllang": lang,
    }
    result = defaultdict(dict)
    while True:
        data = call_api(params)
        for page in data["query"]["pages"]:
            result[page["title"]].update(page)

        cont = data.get("continue")
        if cont:
            params.update(cont)
        else:
            break
    
    models = []
    for p in result.values():
        model = PageLanglinks.model_validate(p)
        models.append(model)
    return models


def batch_get_page_infos(titles: list[str]):
    # https://www.mediawiki.org/wiki/API:Query
    params = {
        "action": "query",
        "titles": "|".join(titles),
        "formatversion": "2",
        "format": "json",
        "prop": "info",
    }
    result = defaultdict(dict)
    while True:
        data = call_api(params)
        for page in data["query"]["pages"]:
            result[page["title"]].update(page)

        cont = data.get("continue")
        if cont:
            params.update(cont)
        else:
            break
    return dict(result)


def get_category_members(category: str):
    if not category.startswith("Category:"):
        category = f"Category:{category}"
    
    params = {
        "action": "query",
        "format": "json",
        "list": "categorymembers",
        "cmtitle": category,
        "cmtype": "page",  # exclude subcategories (TODO: recursive)
        "cmlimit": 100,
    }
    
    while True:
        data = call_api(params)
        for member in data["query"]["categorymembers"]:
            yield member
        
        cont = data.get("continue")
        if cont:
            params.update(cont)
        else:
            break


def download_pages(titles: Iterable[str]):
    from pathlib import Path
    from itertools import batched

    for batch in batched(titles, 20):
        print(f"\nfetching info: batch size = {len(batch)}, first = {batch[0]}, last = {batch[-1]}")
        infos = batch_get_page_infos(batch)

        for title in batch:
            info = infos[title]
            last_rev_timestamp = datetime.fromisoformat(info["touched"])

            save_path = Path("data/source") / f"{title.replace('/', '__')}.json"
            if save_path.exists():
                data = PageData.model_validate_json(save_path.read_text())
                age = (last_rev_timestamp - data.last_rev_timestamp).days
                print(f"skipping page: {title} (age={age}d)")
                continue
            
            print(f"fetching page: {title}")
            page = parse_page(title)
            langlinks = []
            for links_batch in batched((link.title for link in page.links if link.exists), 20):
                langlinks.extend(batch_get_page_langlinks(links_batch, "ko"))
            
            data = PageData(
                page=page,
                links_langlinks=langlinks,
                last_rev_timestamp=last_rev_timestamp,
            )
            save_path.write_text(data.model_dump_json(indent=2))


if __name__ == "__main__":
    download_pages((page["title"] for page in get_category_members("Category:2024年のテレビアニメ")))
