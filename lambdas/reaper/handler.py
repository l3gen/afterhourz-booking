"""Cost reaper: the deterministic 'kill switch'. No AI in this path, on purpose.

Triggered by (a) AWS Budgets via SNS when spend crosses a threshold, and (b) a nightly
EventBridge schedule as a safety net in case the GitHub Actions nightly destroy failed.

Scope is deliberately narrow. It only touches resources carrying ALL of these tags:
    Project=afterhourz   Env=<this function's ENVIRONMENT>   Ephemeral=true
and only knows how to do two things: scale ECS services to zero and delete ALBs.
Everything it does is reported to the alerts SNS topic.

REAPER_MODE=destroy  (dev)  -> act
REAPER_MODE=notify   (prod) -> report what it WOULD do; never take production down on its own
"""

import logging
import os

import boto3

log = logging.getLogger()
log.setLevel(logging.INFO)


def _matching_arns(tagging, env: str) -> list[str]:
    arns, token = [], ""
    while True:
        kwargs = {
            "TagFilters": [
                {"Key": "Project", "Values": ["afterhourz"]},
                {"Key": "Env", "Values": [env]},
                {"Key": "Ephemeral", "Values": ["true"]},
            ],
            "ResourceTypeFilters": ["ecs:service", "elasticloadbalancing:loadbalancer"],
            "PaginationToken": token,
        }
        resp = tagging.get_resources(**kwargs)
        arns += [m["ResourceARN"] for m in resp["ResourceTagMappingList"]]
        token = resp.get("PaginationToken", "")
        if not token:
            return arns


def handler(event, context, tagging=None, ecs=None, elb=None, sns=None):
    env = os.environ["ENVIRONMENT"]
    mode = os.environ.get("REAPER_MODE", "notify")
    dry_run = mode != "destroy" or bool(isinstance(event, dict) and event.get("dry_run"))
    tagging = tagging or boto3.client("resourcegroupstaggingapi")
    ecs = ecs or boto3.client("ecs")
    elb = elb or boto3.client("elbv2")
    sns = sns or boto3.client("sns")

    actions = []
    for arn in _matching_arns(tagging, env):
        try:
            if ":service/" in arn and arn.startswith("arn:aws:ecs:"):
                # service ARN: arn:aws:ecs:region:acct:service/<cluster>/<service>
                cluster, service = arn.split(":service/")[1].split("/")
                actions.append(f"scale to 0: ecs service {cluster}/{service}")
                if not dry_run:
                    ecs.update_service(cluster=cluster, service=service, desiredCount=0)
            elif ":loadbalancer/" in arn:
                actions.append(f"delete: load balancer {arn.split('loadbalancer/')[1]}")
                if not dry_run:
                    elb.delete_load_balancer(LoadBalancerArn=arn)
        except Exception as e:  # keep going; report the failure
            log.exception("reaper failed on %s", arn)
            actions.append(f"FAILED on {arn}: {e}")

    trigger = "budget alert" if _is_sns(event) else "scheduled sweep"
    verb = "WOULD take" if dry_run else "TOOK"
    body = f"Cost reaper ({env}, trigger: {trigger}) {verb} {len(actions)} action(s).\n" + "\n".join(
        f"- {a}" for a in actions
    )
    log.info(body)
    topic = os.environ.get("ALERT_TOPIC_ARN")
    # Stay quiet on routine nightly sweeps that found nothing; always speak up if a budget fired.
    if topic and (actions or _is_sns(event)):
        sns.publish(TopicArn=topic, Subject=f"[afterhourz-{env}] cost reaper: {len(actions)} action(s)", Message=body)
    return {"dry_run": dry_run, "actions": actions}


def _is_sns(event) -> bool:
    records = event.get("Records") if isinstance(event, dict) else None
    return bool(records) and records[0].get("EventSource") == "aws:sns"
