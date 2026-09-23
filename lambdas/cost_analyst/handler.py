"""Daily AI cost analyst (advisory only).

Pulls the last 14 days of spend from Cost Explorer, asks an Amazon Bedrock model to explain
what changed and what to do about it, and emails the result via SNS.

It has NO destructive permissions and its output is never executed. Destruction is handled
by the deterministic reaper Lambda / nightly Terraform destroy. An LLM explains; guardrails act.
"""

import datetime as dt
import json
import logging
import os
import re
from collections import defaultdict

import boto3

log = logging.getLogger()
log.setLevel(logging.INFO)

SYSTEM = (
    "You are a FinOps analyst for a tiny AWS workload: a barbershop booking website. "
    "Given daily cost by service, explain concisely what is driving spend, flag anything unusual "
    "versus the prior days, and recommend specific, low-risk actions. Be plain and short. "
    "Respond with ONLY a JSON object: "
    '{"severity": "ok|watch|critical", "summary": "<2 sentences>", '
    '"top_drivers": ["..."], "recommended_actions": ["..."]}'
)


def collect(ce, today: dt.date, days: int = 14) -> dict[str, dict[str, float]]:
    """{service: {date: cost}} for the trailing window (Cost Explorer end date is exclusive)."""
    start = today - dt.timedelta(days=days)
    out: dict[str, dict[str, float]] = defaultdict(dict)
    token = None
    while True:
        kwargs = {
            "TimePeriod": {"Start": start.isoformat(), "End": today.isoformat()},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost"],
            "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
        }
        if token:
            kwargs["NextPageToken"] = token
        resp = ce.get_cost_and_usage(**kwargs)
        for day in resp["ResultsByTime"]:
            d = day["TimePeriod"]["Start"]
            for g in day["Groups"]:
                out[g["Keys"][0]][d] = out[g["Keys"][0]].get(d, 0.0) + float(g["Metrics"]["UnblendedCost"]["Amount"])
        token = resp.get("NextPageToken")
        if not token:
            return dict(out)


def flag_spikes(data: dict[str, dict[str, float]], min_dollars: float = 0.5, ratio: float = 2.0) -> list[str]:
    """Deterministic spike detection, so the email is useful even if Bedrock is unavailable."""
    flags = []
    for svc, series in data.items():
        days = sorted(series)
        if len(days) < 3:
            continue
        latest, prior = series[days[-1]], [series[d] for d in days[:-1]]
        avg = sum(prior) / len(prior)
        if latest >= min_dollars and latest > ratio * max(avg, 0.01):
            flags.append(f"{svc}: ${latest:.2f} yesterday vs ${avg:.2f} daily average")
    return flags


def render_table(data: dict[str, dict[str, float]]) -> str:
    dates = sorted({d for s in data.values() for d in s})
    lines = ["service," + ",".join(dates)]
    for svc, series in sorted(data.items(), key=lambda kv: -sum(kv[1].values())):
        lines.append(svc + "," + ",".join(f"{series.get(d, 0):.2f}" for d in dates))
    return "\n".join(lines)


def ask_model(bedrock, model_id: str, table: str, spikes: list[str], budget: str) -> dict:
    prompt = (
        f"Monthly budget: ${budget}.\nDaily cost by service (USD, oldest to newest):\n{table}\n\n"
        f"Pre-computed spikes: {spikes or 'none'}"
    )
    resp = bedrock.converse(
        modelId=model_id,
        system=[{"text": SYSTEM}],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 700, "temperature": 0.2},
    )
    text = resp["output"]["message"]["content"][0]["text"]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(match.group(0)) if match else {"summary": text[:500]}


def handler(event, context, ce=None, bedrock=None, sns=None, today=None):
    ce = ce or boto3.client("ce", region_name="us-east-1")  # Cost Explorer only lives in us-east-1
    bedrock = bedrock or boto3.client("bedrock-runtime")
    sns = sns or boto3.client("sns")
    today = today or dt.date.today()
    env = os.environ.get("ENVIRONMENT", "dev")
    budget = os.environ.get("MONTHLY_BUDGET_USD", "?")

    data = collect(ce, today)
    total_yesterday = sum(s.get(max(s), 0) for s in data.values()) if data else 0.0
    spikes = flag_spikes(data)

    analysis: dict = {}
    try:
        analysis = ask_model(bedrock, os.environ["BEDROCK_MODEL_ID"], render_table(data), spikes, budget)
    except Exception:
        log.exception("bedrock analysis failed; sending numbers only")
        analysis = {"summary": "AI analysis unavailable today; see the raw numbers below."}

    severity = str(analysis.get("severity", "watch" if spikes else "ok")).lower()
    lines = [
        f"AfterHourzKutz {env} cost report for {today - dt.timedelta(days=1)}",
        f"Latest day total: ${total_yesterday:.2f}   Monthly budget: ${budget}",
        "",
        analysis.get("summary", ""),
        "",
        "Top drivers:",
        *[f"  - {x}" for x in analysis.get("top_drivers", [])],
        "Recommended actions:",
        *[f"  - {x}" for x in analysis.get("recommended_actions", [])],
    ]
    if spikes:
        lines += ["", "Spikes detected (rule-based):", *[f"  - {s}" for s in spikes]]
    lines += ["", "AI-generated advice. No automatic action was taken.", "", "Raw data:", render_table(data)]

    topic = os.environ.get("ALERT_TOPIC_ARN")
    if topic:
        sns.publish(
            TopicArn=topic,
            Subject=f"[afterhourz-{env}] daily cost: ${total_yesterday:.2f} ({severity})",
            Message="\n".join(lines),
        )
    return {"severity": severity, "yesterday_usd": round(total_yesterday, 2), "spikes": spikes}
