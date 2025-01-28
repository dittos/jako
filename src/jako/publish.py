import json
import os
from pathlib import Path

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


def is_outdated(f: Path, source_mtime: float) -> bool:
    if not f.exists():
        return True
    target_mtime = f.stat().st_mtime
    return target_mtime < source_mtime


def publish_page(fname: str) -> tuple[str, str | None, list[str]]:
    result_file = result_dir / fname
    mtime = result_file.stat().st_mtime

    result = json.loads(result_file.read_text())
    source = PageData.model_validate_json((source_dir / fname).read_text())
    translated_title = result["title"]
    original_title = source.page.title

    translated_redirect_title = None
    redirect_titles = []

    publish_path = publish_dir / safe_filename(translated_title)
    if is_outdated(publish_path, mtime):
        result["original_title"] = original_title
        result["last_rev_timestamp"] = source.last_rev_timestamp.isoformat()
        result["html"] = fix_cite_ref_a(result["html"])
        publish_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"Published: {publish_path}")
    else:
        print(f"Up-to-date: {publish_path}")

    if translated_title != original_title:
        redirect_publish_path = publish_dir / safe_filename(original_title)
        if is_outdated(redirect_publish_path, mtime):
            redirect_publish_path.write_text(json.dumps({
                "redirect": {
                    "to": translated_title
                }
            }, ensure_ascii=False, indent=2))
            print(f"Published: {redirect_publish_path} (redirect)")
        else:
            print(f"Up-to-date: {redirect_publish_path} (redirect)")
        translated_redirect_title = original_title

    for redirect in source.page.redirects:
        redirect_publish_path = publish_dir / safe_filename(redirect.from_)
        if is_outdated(redirect_publish_path, mtime):
            redirect_publish_path.write_text(json.dumps({
                "redirect": {
                    "to": translated_title if redirect.to == original_title else redirect.to,
                    "tofragment": redirect.tofragment
                }
            }, ensure_ascii=False, indent=2))
            print(f"Published: {redirect_publish_path} (redirect)")
        else:
            print(f"Up-to-date: {redirect_publish_path} (redirect)")
        redirect_titles.append(redirect.from_)

    return translated_title, translated_redirect_title, redirect_titles


def indexnow_batch(urls: list[str]):
    resp = requests.post("https://api.indexnow.org/indexnow", json={
        "host": "jako.sapzil.org",
        "key": "198c6938537a4c3185af9ff04fa38082",
        "keyLocation": "https://jako.sapzil.org/indexnowkey",
        "urlList": urls,
    })
    if not resp.ok:
        print(resp.content)
        resp.raise_for_status()


def main():
    # import shutil; shutil.rmtree(publish_dir, ignore_errors=True)
    # publish_dir.mkdir(parents=True, exist_ok=True)

    titles = []
    canonical_count = 0
    translated_redirect_count = 0
    redirect_count = 0

    with Pool() as p:
        results = p.map(publish_page, os.listdir(result_dir))

    for t, trt, rts in results:
        titles.append(t)
        canonical_count += 1
        if trt:
            titles.append(trt)
            translated_redirect_count += 1
        titles.extend(rts)
        redirect_count += len(rts)

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
    indexnow_batch(urls)

    print("-" * 30)
    print(f"Stats: {canonical_count=} {translated_redirect_count=} {redirect_count=}")


if __name__ == "__main__":
    main()
