"""Daily appointment reminders (email + optional SMS).

Runs from EventBridge Scheduler once a day (16:00 shop time) and reminds everyone who has a
confirmed appointment *tomorrow*. Lives in the always-on foundation stack, so reminders keep
working even while the dev API stack is torn down. Self-contained (boto3 only) so it can be
packaged as a plain zip.
"""

import datetime as dt
import logging
import os
from zoneinfo import ZoneInfo

import boto3
from boto3.dynamodb.conditions import Key

log = logging.getLogger()
log.setLevel(logging.INFO)


def _human_when(date_s: str, hhmm: str) -> str:
    d = dt.date.fromisoformat(date_s)
    h, m = (int(x) for x in hhmm.split(":"))
    t = dt.time(h, m)
    return f"{d.strftime('%A, %B')} {d.day} at {t.strftime('%I:%M %p').lstrip('0')}"


def handler(event, context, table=None, ses=None, sns=None, now=None):
    table = table or boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
    ses = ses or boto3.client("ses")
    sns = sns or boto3.client("sns")
    tz = ZoneInfo(os.environ.get("TIMEZONE", "America/New_York"))
    now = now or dt.datetime.now(tz)
    tomorrow = (now + dt.timedelta(days=1)).date().isoformat()

    sender = os.environ.get("SES_FROM", "")
    sms_on = os.environ.get("SMS_ENABLED", "false").lower() == "true"
    site = os.environ.get("FRONTEND_ORIGIN", "")

    resp = table.query(IndexName="gsi2", KeyConditionExpression=Key("gsi2pk").eq(f"DAY#{tomorrow}"))
    sent = 0
    for appt in resp["Items"]:
        if appt.get("status") != "confirmed" or appt.get("reminder_sent"):
            continue
        when = _human_when(appt["date"], appt["time"])
        try:
            if sender:
                ses.send_email(
                    Source=sender,
                    Destination={"ToAddresses": [appt["customer_email"]]},
                    Message={
                        "Subject": {"Data": "Reminder: your AfterHourzKutz appointment tomorrow"},
                        "Body": {
                            "Text": {
                                "Data": f"See you {when} for your {appt['service_name']}.\n"
                                f"Need to change plans? {site}/my-appointments"
                            }
                        },
                    },
                )
            if sms_on and appt.get("phone"):
                sns.publish(PhoneNumber=appt["phone"], Message=f"AfterHourzKutz reminder: {when}. See you then!")
            table.update_item(
                Key={"pk": appt["pk"], "sk": appt["sk"]},
                UpdateExpression="SET reminder_sent = :t",
                ExpressionAttributeValues={":t": True},
            )
            sent += 1
        except Exception:
            log.exception("reminder failed for %s", appt.get("id"))
    log.info("reminders sent for %s: %d", tomorrow, sent)
    return {"date": tomorrow, "sent": sent}
