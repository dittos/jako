from dataclasses import dataclass
import json
import os
from pathlib import Path

import subprocess
import urllib.parse

import boto3
import requests

from jako.models.page import PageData
from jako.preprocess_html import fix_cite_ref_a
from multiprocessing import Pool
import hashlib


publish_dir = Path("data/publish")
source_dir = Path("data/source")
result_dir = Path("data/result")

s3 = boto3.client("s3")


@dataclass
class PublishInfo:
    translated_title: str
    translated_redirect_title: str | None
    redirect_titles: list[str]

    @property
    def all_titles(self) -> list[str]:
        titles = [self.translated_title]
        if self.translated_redirect_title:
            titles.append(self.translated_redirect_title)
        titles.extend(self.redirect_titles)
        return titles


def safe_filename(title: str) -> str:
    return title.replace("/", "__") + ".json"


def page_url(title: str) -> str:
    return f"https://jako.sapzil.org/wiki/{urllib.parse.quote(title)}"


def is_outdated(f: Path, source_mtime: float | None) -> bool:
    if not f.exists() or source_mtime is None:
        return True
    target_mtime = f.stat().st_mtime
    return target_mtime < source_mtime


def publish_page(fname: str) -> PublishInfo:
    result_file = result_dir / fname
    mtime = result_file.stat().st_mtime

    result = json.loads(result_file.read_text())
    source = PageData.model_validate_json((source_dir / fname).read_text())
    translated_title = result["title"]
    original_title = source.page.title

    translated_redirect_title = None
    redirect_titles = []
    updated = False

    publish_path = publish_dir / safe_filename(translated_title)
    if is_outdated(publish_path, mtime):
        result["original_title"] = original_title
        result["last_rev_timestamp"] = source.last_rev_timestamp.isoformat()
        result["html"] = fix_cite_ref_a(result["html"])
        publish_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        updated = True
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
            updated = True
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
            updated = True
            print(f"Published: {redirect_publish_path} (redirect)")
        else:
            print(f"Up-to-date: {redirect_publish_path} (redirect)")
        redirect_titles.append(redirect.from_)
    
    if updated:
        (publish_dir / ".stamp").touch()

    return PublishInfo(
        translated_title=translated_title,
        translated_redirect_title=translated_redirect_title,
        redirect_titles=redirect_titles,
    )


def check_publish_status(fname: str) -> PublishInfo | None:
    result_file = result_dir / fname

    result = json.loads(result_file.read_text())
    source = PageData.model_validate_json((source_dir / fname).read_text())
    original_title = source.page.title

    translated_title = result["title"]
    translated_redirect_title = original_title if translated_title != original_title else None
    redirect_titles = [redirect.from_ for redirect in source.page.redirects]

    return PublishInfo(
        translated_title=translated_title,
        translated_redirect_title=translated_redirect_title,
        redirect_titles=redirect_titles,
    )


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


def publish_sitemap():
    mtime = None
    if (publish_dir / ".stamp").exists():
        mtime = (publish_dir / ".stamp").stat().st_mtime

    sitemap_path = publish_dir / "sitemap.xml"
    if not is_outdated(sitemap_path, mtime):
        print("Sitemap not updated (mtime)")
        return

    titles = []
    for fname in os.listdir(result_dir):
        if not fname.endswith(".json"):
            continue
        info = check_publish_status(fname)
        if info:
            titles.extend(info.all_titles)

    prev_checksum = None
    if sitemap_path.exists():
        with sitemap_path.open("rb") as f:
            prev_checksum = hashlib.file_digest(f, "sha1").hexdigest()

    write_sitemap(sitemap_path, titles)
    with sitemap_path.open("rb") as f:
        new_checksum = hashlib.file_digest(f, "sha1").hexdigest()
    
    print(f"Sitemap checksum: {prev_checksum=} {new_checksum=}")
    if prev_checksum != new_checksum:
        print("Sitemap updated")
        s3.upload_file(str(sitemap_path), "jako-data-kr", sitemap_path.name)
    else:
        print("Sitemap not updated (checksum)")


def write_sitemap(path: Path, titles: list[str]):
    with open(path, "w") as f:
        f.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        f.write("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n")
        for title in titles:
            f.write(f"<url><loc>{page_url(title)}</loc></url>\n")
        f.write("</urlset>\n")


def main():
    # import shutil; shutil.rmtree(publish_dir, ignore_errors=True)
    # publish_dir.mkdir(parents=True, exist_ok=True)

    titles = []
    canonical_count = 0
    translated_redirect_count = 0
    redirect_count = 0

    with Pool() as p:
        fnames = [fname for fname in os.listdir(result_dir) if fname.endswith(".json")]
        results = p.map(publish_page, fnames)

    for result in results:
        titles.extend(result.all_titles)

        canonical_count += 1
        if result.translated_redirect_title:
            translated_redirect_count += 1
        redirect_count += len(result.redirect_titles)

    write_sitemap(publish_dir / "sitemap.xml", titles)
    print("Published: sitemap.xml")

    subprocess.run(["aws", "s3", "sync", publish_dir, "s3://jako-data-kr/"], check=True)

    print("Calling IndexNow API...")
    urls = [page_url(title) for title in titles]
    indexnow_batch(urls)

    print("-" * 30)
    print(f"Stats: {canonical_count=} {translated_redirect_count=} {redirect_count=}")


if __name__ == "__main__":
    main()
