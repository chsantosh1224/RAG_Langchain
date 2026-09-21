"""Lambda handler: SQS message -> S3 object -> chunks in pgvector.

S3 sends an event to SQS on upload; Lambda receives it in batches. Anything
created outside the handler is reused by later invocations on the same
container, which matters here because the database pool is expensive to build.
"""
import json
import logging
import os
import urllib.parse

import boto3

from app.config import load_config

load_config()

from app.embeddings import TEIEmbeddings
from app.ingest_service import ingest_file
from app.vectorstore import ensure_table, get_engine, get_vectorstore
from core.ingest_lib import is_supported

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "/tmp")  # /tmp is the only writable path in Lambda
_store = None


def get_store():
    global _store
    if _store is None:
        engine = get_engine()
        ensure_table(engine)
        _store = get_vectorstore(engine, TEIEmbeddings())
    return _store


def handle_s3_object(bucket: str, key: str) -> None:
    if not is_supported(key):
        logger.info("Skipping unsupported file %s", key)
        return

    download_path = os.path.join(DOWNLOAD_DIR, os.path.basename(key))
    s3.download_file(bucket, key, download_path)
    try:
        count = ingest_file(get_store(), download_path, source=key)
        logger.info("Ingested %s: %d chunks", key, count)
    finally:
        os.remove(download_path)


def handler(event, context):
    """Returns the IDs of failed messages so SQS retries only those."""
    failures = []

    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            if body.get("Event") == "s3:TestEvent":  # sent once when the notification is set up
                continue
            for s3_record in body.get("Records", []):
                bucket = s3_record["s3"]["bucket"]["name"]
                key = urllib.parse.unquote_plus(s3_record["s3"]["object"]["key"])
                handle_s3_object(bucket, key)
        except Exception:
            logger.exception("Failed message %s", record.get("messageId"))
            failures.append({"itemIdentifier": record["messageId"]})

    return {"batchItemFailures": failures}
