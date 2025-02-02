import asyncio
import os
from pathlib import Path
from celery import Celery
from celery.schedules import crontab

from jako.publish import indexnow_batch, page_url, publish_page, publish_sitemap as do_publish_sitemap
from jako.scrape import batch_get_page_infos, download_page, get_category_members
from jako.translate import process as translate_file
import boto3

app = Celery('jako.worker', broker=os.environ['CELERY_BROKER'], backend="db+sqlite:///data/worker/backend.sqlite3")
app.conf.beat_schedule = {
    'publish sitemap if changed': {
        'task': 'jako.worker.publish_sitemap',
        'schedule': crontab(minute=0),  # hourly
        'args': (),
    },
}

s3 = boto3.client("s3")


@app.task
def translate(title: str):
    infos = batch_get_page_infos([title])
    info = infos[title]
    download_page(title, info)
    
    filename = f"{title.replace('/', '__')}.json"
    input_path = Path("data/source") / filename
    asyncio.run(translate_file(input_path))

    result = publish_page(filename)
    titles = [result.translated_title]
    if result.translated_redirect_title:
        titles.append(result.translated_redirect_title)
    titles.extend(result.redirect_titles)

    for t in titles:
        publish_path = Path("data/publish") / f"{t.replace('/', '__')}.json"
        s3.upload_file(str(publish_path), "jako-data-kr", publish_path.name)
        print(f"Uploaded to S3: {publish_path}")

    print("Calling IndexNow API...")
    indexnow_batch([page_url(t) for t in titles])


@app.task
def translate_category(category: str):
    for page in get_category_members(category):
        # TODO: batching?
        translate.delay(page["title"])


@app.task
def publish_sitemap():
    do_publish_sitemap()
