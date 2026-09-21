"""Configuration loading.

Locally: values come from .env.
On AWS: APP_SECRET_ID names a Secrets Manager secret holding a JSON object; its
keys become environment variables. The instance role grants access, so no
credentials are stored anywhere.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)


def load_config() -> None:
    """Load .env, then overlay the AWS secret if APP_SECRET_ID is set.

    Call this before importing modules that read settings at import time.
    """
    from dotenv import load_dotenv

    load_dotenv()

    secret_id = os.getenv("APP_SECRET_ID")
    if not secret_id:
        return

    import boto3

    client = boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION", "ap-southeast-2"))
    payload = client.get_secret_value(SecretId=secret_id)["SecretString"]
    for key, value in json.loads(payload).items():
        os.environ[key] = str(value)
    logger.info("Loaded %d settings from secret %s", len(json.loads(payload)), secret_id)
