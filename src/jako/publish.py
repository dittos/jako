import json
import os
from pathlib import Path
import shutil

import subprocess
import urllib.parse

import requests

from jako.models.page import PageData
from jako.preprocess_html import fix_cite_ref_a
from multiprocessing import Pool


publish_dir = Path("data/publish")
source_dir = Path("data/source")
result_dir = Path("data/result")


def safe_filename(title: str) -> str:
    return title.replace("/", "__") + ".json"


def _process_file(fname):
    result = json.loads((result_dir / fname).read_text())
    source = PageData.model_validate_json((source_dir / fname).read_text())
    translated_title = result["title"]
    original_title = source.page.title

    local_titles = []
    local_canonical_count = 0
    local_translated_redirect_count = 0
    local_redirect_count = 0

    publish_path = publish_dir / safe_filename(translated_title)
    result["original_title"] = original_title
    result["last_rev_timestamp"] = source.last_rev_timestamp.isoformat()
    result["html"] = fix_cite_ref_a(result["html"])
    publish_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    local_titles.append(translated_title)
    local_canonical_count += 1
    print(f"Published: {publish_path}")

    if translated_title != original_title:
        redirect_publish_path = publish_dir / safe_filename(original_title)
        redirect_publish_path.write_text(json.dumps({
            "redirect": {
                "to": translated_title
            }
        }, ensure_ascii=False, indent=2))
        print(f"Published: {redirect_publish_path} (redirect)")
        local_titles.append(original_title)
        local_translated_redirect_count += 1

    for redirect in source.page.redirects:
        redirect_publish_path = publish_dir / safe_filename(redirect.from_)
        redirect_publish_path.write_text(json.dumps({
            "redirect": {
                "to": translated_title if redirect.to == original_title else redirect.to,
                "tofragment": redirect.tofragment
            }
        }, ensure_ascii=False, indent=2))
        print(f"Published: {redirect_publish_path} (redirect)")
        local_titles.append(redirect.from_)
        local_redirect_count += 1

    return local_titles, local_canonical_count, local_translated_redirect_count, local_redirect_count


def main():
    shutil.rmtree(publish_dir, ignore_errors=True)
    publish_dir.mkdir(parents=True, exist_ok=True)

    titles = []
    canonical_count = 0
    translated_redirect_count = 0
    redirect_count = 0

    with Pool() as p:
        results = p.map(_process_file, os.listdir(result_dir))

    for t, c, trc, rc in results:
        titles.extend(t)
        canonical_count += c
        translated_redirect_count += trc
        redirect_count += rc

    urls = []
    with open(publish_dir / "sitemap.xml", "w") as f:
        f.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        f.write("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n")
        for title in titles:
            url = f"https://jako.sapzil.org/wiki/{urllib.parse.quote(title)}"
            urls.append(url)
            f.write(f"<url><loc>{url}</loc></url>\n")
        f.write("</urlset>\n")
    print("Published: sitemap.xml")

    subprocess.run(["aws", "s3", "sync", publish_dir, "s3://jako-data-kr/"], check=True)

    print("Calling IndexNow API...")
    resp = requests.post("https://api.indexnow.org/indexnow", json={
        "host": "jako.sapzil.org",
        "key": "198c6938537a4c3185af9ff04fa38082",
        "keyLocation": "https://jako.sapzil.org/indexnowkey",
        "urlList": urls,
    })
    if not resp.ok:
        print(resp.content)
        resp.raise_for_status()

    print("-" * 30)
    print(f"Stats: {canonical_count=} {translated_redirect_count=} {redirect_count=}")


if __name__ == "__main__":
    main()
