import asyncio
import os
from pathlib import Path
from celery import Celery
import urllib

from jako.publish import indexnow_batch, publish_page, main as publish_main
from jako.scrape import batch_get_page_infos, download_page
from jako.translate import process as translate_file
import boto3

app = Celery('hello', broker=os.environ['CELERY_BROKER'], backend="db+sqlite:///data/worker/backend.sqlite3")
s3 = boto3.client("s3")


@app.task
def translate(title: str):
    infos = batch_get_page_infos([title])
    info = infos[title]
    download_page(title, info)
    
    filename = f"{title.replace('/', '__')}.json"
    input_path = Path("data/source") / filename
    asyncio.run(translate_file(input_path))

    translated_title, translated_redirect_title, redirect_titles = publish_page(filename)
    titles = [translated_title]
    if translated_redirect_title:
        titles.append(translated_redirect_title)
    titles.extend(redirect_titles)

    for t in titles:
        publish_path = Path("data/publish") / f"{t.replace('/', '__')}.json"
        s3.upload_file(str(publish_path), "jako-data-kr", publish_path.name)
        print(f"Uploaded to S3: {publish_path}")

    print("Calling IndexNow API...")
    indexnow_batch([f"https://jako.sapzil.org/wiki/{urllib.parse.quote(t)}" for t in titles])


@app.task
def publish_all():
    publish_main()
