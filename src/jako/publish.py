import json
import os
from pathlib import Path
import shutil

import urllib.parse

from jako.models.page import PageData


def safe_filename(title: str) -> str:
    return title.replace("/", "__") + ".json"


def main():
    publish_dir = Path("data/publish")
    shutil.rmtree(publish_dir, ignore_errors=True)
    publish_dir.mkdir(parents=True, exist_ok=True)

    titles = []

    source_dir = Path("data/source")
    result_dir = Path("data/result")
    for file in os.listdir(result_dir):
        result = json.loads((result_dir / file).read_text())
        source = PageData.model_validate_json((source_dir / file).read_text())
        translated_title = result["title"]
        original_title = source.page.title

        publish_path = publish_dir / safe_filename(translated_title)
        result["original_title"] = original_title
        result["last_rev_timestamp"] = source.last_rev_timestamp.isoformat()
        publish_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"Published: {publish_path}")
        titles.append(translated_title)

        if translated_title != original_title:
            redirect_publish_path = publish_dir / safe_filename(original_title)
            redirect_publish_path.write_text(json.dumps({
                "redirect": {
                    "to": translated_title
                }
            }, ensure_ascii=False, indent=2))
            print(f"Published: {redirect_publish_path} (redirect)")
            titles.append(original_title)

        for redirect in source.page.redirects:
            redirect_publish_path = publish_dir / safe_filename(redirect.from_)
            redirect_publish_path.write_text(json.dumps({
                "redirect": {
                    "to": translated_title if redirect.to == original_title else redirect.to,
                    "tofragment": redirect.tofragment
                }
            }, ensure_ascii=False, indent=2))
            print(f"Published: {redirect_publish_path} (redirect)")
            titles.append(redirect.from_)
    
    with open(publish_dir / "sitemap.xml", "w") as f:
        f.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        f.write("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n")
        for title in titles:
            url = f"https://jako.sapzil.org/wiki/{urllib.parse.quote(title)}"
            f.write(f"<url><loc>{url}</loc></url>\n")
        f.write("</urlset>\n")
    print("Published: sitemap.xml")


if __name__ == "__main__":
    main()
