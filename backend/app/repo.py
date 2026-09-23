"""DynamoDB access. All booking-integrity guarantees live here.

Double-booking protection: every appointment occupies one SLOTS#<date>/<HH:MM> item per
30-minute block. Creating an appointment is a single TransactWriteItems that puts the
appointment AND all its slot items, each with a condition that the slot is free. If any
slot is taken the whole transaction is rejected, so two clients can never hold the same
time even under concurrent requests.

Unpaid holds carry `expires_at`; a slot whose hold has expired can be overwritten by a
new booking (DynamoDB's own TTL deletion is far too lazy to rely on).
"""

import datetime as dt
import json
from decimal import Decimal

from botocore.exceptions import ClientError

from app.availability import DEFAULT_HOURS
from app.timeutil import slots_for

GSI_KEYS = ("pk", "sk", "gsi1pk", "gsi1sk", "gsi2pk", "gsi2sk")


class SlotTaken(Exception):
    pass


class NotFound(Exception):
    pass


class ConfirmFailed(Exception):
    """The hold was lost (cancelled, or the slot went to someone else)."""


def _plain(v):
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    return v


def _code(e: ClientError) -> str:
    return e.response.get("Error", {}).get("Code", "")


class Repo:
    def __init__(self, resource, table_name: str):
        self.client = resource.meta.client
        self.table = resource.Table(table_name)
        self.name = table_name

    # ------------------------------------------------------------------ config
    def get_config(self) -> dict:
        item = self.table.get_item(Key={"pk": "CONFIG", "sk": "SHOP"}).get("Item")
        if not item:
            return {"hours": DEFAULT_HOURS, "closed_dates": []}
        return {
            "hours": json.loads(item["hours_json"]),
            "closed_dates": sorted(item.get("closed_dates", [])),
        }

    def put_config(self, hours: dict, closed_dates: list[str]) -> None:
        self.table.put_item(
            Item={
                "pk": "CONFIG",
                "sk": "SHOP",
                "hours_json": json.dumps(hours),
                "closed_dates": sorted(set(closed_dates)),
            }
        )

    # ------------------------------------------------------------------- slots
    def taken_slots(self, date: str, now_epoch: int) -> set[str]:
        taken = set()
        for item in self._query(pk=f"SLOTS#{date}"):
            exp = item.get("expires_at")
            if exp is not None and int(exp) < now_epoch:
                continue  # expired unpaid hold
            taken.add(item["sk"])
        return taken

    # ------------------------------------------------------------ appointments
    def create(self, appt: dict, now_epoch: int) -> None:
        item = {
            **appt,
            "pk": f"APPT#{appt['id']}",
            "sk": "META",
            "gsi1pk": f"USER#{appt['customer_email']}",
            "gsi1sk": f"{appt['date']}T{appt['time']}",
            "gsi2pk": f"DAY#{appt['date']}",
            "gsi2sk": f"{appt['time']}#{appt['id']}",
        }
        tx = [
            {
                "Put": {
                    "TableName": self.name,
                    "Item": item,
                    "ConditionExpression": "attribute_not_exists(pk)",
                }
            }
        ]
        for slot in slots_for(appt["time"], appt["duration_min"]):
            slot_item = {"pk": f"SLOTS#{appt['date']}", "sk": slot, "appt_id": appt["id"]}
            if appt.get("hold_expires_at"):
                slot_item["expires_at"] = appt["hold_expires_at"]
            tx.append(
                {
                    "Put": {
                        "TableName": self.name,
                        "Item": slot_item,
                        # free, or held by an unpaid booking whose hold has lapsed
                        "ConditionExpression": "attribute_not_exists(pk) OR expires_at < :now",
                        "ExpressionAttributeValues": {":now": now_epoch},
                    }
                }
            )
        try:
            self.client.transact_write_items(TransactItems=tx)
        except ClientError as e:
            if _code(e) == "TransactionCanceledException":
                raise SlotTaken from e
            raise

    def get(self, appt_id: str, now_epoch: int | None = None) -> dict | None:
        item = self.table.get_item(Key={"pk": f"APPT#{appt_id}", "sk": "META"}).get("Item")
        return self._present(item, now_epoch) if item else None

    def confirm(self, appt_id: str, payment_intent_id: str | None, now_iso: str) -> dict:
        """Pending -> confirmed after a successful payment. Idempotent."""
        appt = self.get(appt_id)
        if not appt:
            raise NotFound(appt_id)
        if appt["status"] == "confirmed":
            return appt
        if appt["status"] != "pending_payment":
            raise ConfirmFailed(f"status is {appt['status']}")
        tx = [
            {
                "Update": {
                    "TableName": self.name,
                    "Key": {"pk": f"APPT#{appt_id}", "sk": "META"},
                    "UpdateExpression": "SET #s = :c, payment_intent_id = :pi, paid_at = :t REMOVE hold_expires_at",
                    "ConditionExpression": "#s = :p",
                    "ExpressionAttributeNames": {"#s": "status"},
                    "ExpressionAttributeValues": {
                        ":c": "confirmed",
                        ":p": "pending_payment",
                        ":pi": payment_intent_id or "",
                        ":t": now_iso,
                    },
                }
            }
        ]
        for slot in slots_for(appt["time"], appt["duration_min"]):
            tx.append(
                {
                    "Update": {
                        "TableName": self.name,
                        "Key": {"pk": f"SLOTS#{appt['date']}", "sk": slot},
                        "UpdateExpression": "REMOVE expires_at",
                        "ConditionExpression": "appt_id = :id",
                        "ExpressionAttributeValues": {":id": appt_id},
                    }
                }
            )
        try:
            self.client.transact_write_items(TransactItems=tx)
        except ClientError as e:
            if _code(e) == "TransactionCanceledException":
                raise ConfirmFailed("slot no longer held") from e
            raise
        return self.get(appt_id)

    def cancel(self, appt_id: str, by: str, now_iso: str) -> dict:
        appt = self.get(appt_id)
        if not appt:
            raise NotFound(appt_id)
        if appt["status"] == "cancelled":
            return appt
        self.table.update_item(
            Key={"pk": f"APPT#{appt_id}", "sk": "META"},
            UpdateExpression="SET #s = :c, cancelled_by = :by, cancelled_at = :t REMOVE hold_expires_at",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":c": "cancelled", ":by": by, ":t": now_iso},
        )
        for slot in slots_for(appt["time"], appt["duration_min"]):
            try:  # only delete slots that still belong to this appointment
                self.table.delete_item(
                    Key={"pk": f"SLOTS#{appt['date']}", "sk": slot},
                    ConditionExpression="appt_id = :id",
                    ExpressionAttributeValues={":id": appt_id},
                )
            except ClientError as e:
                if _code(e) != "ConditionalCheckFailedException":
                    raise
        return self.get(appt_id)

    def set_fields(self, appt_id: str, **fields) -> None:
        names = {f"#{k}": k for k in fields}
        values = {f":{k}": v for k, v in fields.items()}
        expr = "SET " + ", ".join(f"#{k} = :{k}" for k in fields)
        self.table.update_item(
            Key={"pk": f"APPT#{appt_id}", "sk": "META"},
            UpdateExpression=expr,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )

    def list_for_user(self, email: str, now_epoch: int) -> list[dict]:
        items = self._query(index="gsi1", key="gsi1pk", pk=f"USER#{email}", forward=False)
        out = [self._present(i, now_epoch) for i in items]
        return [a for a in out if a["status"] != "expired"]

    def list_for_day(self, date: str, now_epoch: int) -> list[dict]:
        items = self._query(index="gsi2", key="gsi2pk", pk=f"DAY#{date}")
        out = [self._present(i, now_epoch) for i in items]
        return [a for a in out if a["status"] != "expired"]

    def list_range(self, start: str, end: str, now_epoch: int) -> list[dict]:
        d, last = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
        if (last - d).days > 31:
            raise ValueError("range too large")
        out = []
        while d <= last:
            out.extend(self.list_for_day(d.isoformat(), now_epoch))
            d += dt.timedelta(days=1)
        return out

    # ---------------------------------------------------------------- internals
    def _query(self, pk: str, index: str | None = None, key: str = "pk", forward: bool = True):
        kwargs = {
            "KeyConditionExpression": "#k = :v",
            "ExpressionAttributeNames": {"#k": key},
            "ExpressionAttributeValues": {":v": pk},
            "ScanIndexForward": forward,
        }
        if index:
            kwargs["IndexName"] = index
        items = []
        while True:
            resp = self.table.query(**kwargs)
            items.extend(resp["Items"])
            if "LastEvaluatedKey" not in resp:
                return items
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    @staticmethod
    def _present(item: dict, now_epoch: int | None = None) -> dict:
        appt = _plain({k: v for k, v in item.items() if k not in GSI_KEYS})
        exp = appt.get("hold_expires_at")
        if appt.get("status") == "pending_payment" and exp is not None and now_epoch is not None:
            if exp < now_epoch:
                appt["status"] = "expired"
        return appt
