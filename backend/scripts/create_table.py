"""Create the DynamoDB table in DynamoDB Local for development: python scripts/create_table.py"""

import os
import sys

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.schema import TABLE_DEFINITION  # noqa: E402

endpoint = os.environ.get("DYNAMODB_ENDPOINT_URL", "http://localhost:8001")
name = os.environ.get("TABLE_NAME", "afterhourz-local")
db = boto3.resource(
    "dynamodb",
    endpoint_url=endpoint,
    region_name=os.environ.get("AWS_REGION", "us-east-1"),
    aws_access_key_id="local",
    aws_secret_access_key="local",
)
if name in [t.name for t in db.tables.all()]:
    print(f"{name} already exists")
else:
    db.create_table(TableName=name, **TABLE_DEFINITION)
    print(f"created {name} at {endpoint}")
