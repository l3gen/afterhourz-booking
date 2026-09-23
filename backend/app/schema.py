"""DynamoDB table definition, shared by tests and the local-dev script.

Terraform (infra/modules/data) is the source of truth in AWS and must match this.

Single-table layout
  APPT#<id>   | META     appointment record
                          gsi1: USER#<email> / <date>T<time>   -> "my appointments"
                          gsi2: DAY#<date>   / <time>#<id>     -> admin day view, reminders
  SLOTS#<date>| <HH:MM>  one item per 30-min block; conditional writes on this item are
                          what make double-booking impossible
  CONFIG      | SHOP     opening hours + closed dates
"""

TABLE_DEFINITION = {
    "KeySchema": [
        {"AttributeName": "pk", "KeyType": "HASH"},
        {"AttributeName": "sk", "KeyType": "RANGE"},
    ],
    "AttributeDefinitions": [
        {"AttributeName": "pk", "AttributeType": "S"},
        {"AttributeName": "sk", "AttributeType": "S"},
        {"AttributeName": "gsi1pk", "AttributeType": "S"},
        {"AttributeName": "gsi1sk", "AttributeType": "S"},
        {"AttributeName": "gsi2pk", "AttributeType": "S"},
        {"AttributeName": "gsi2sk", "AttributeType": "S"},
    ],
    "GlobalSecondaryIndexes": [
        {
            "IndexName": "gsi1",
            "KeySchema": [
                {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
        {
            "IndexName": "gsi2",
            "KeySchema": [
                {"AttributeName": "gsi2pk", "KeyType": "HASH"},
                {"AttributeName": "gsi2sk", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
    ],
    "BillingMode": "PAY_PER_REQUEST",
}
