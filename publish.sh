#!/bin/sh
set -e

python src/jako/publish.py
aws s3 sync data/publish/ s3://jako-data-kr/
