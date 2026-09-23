#!/usr/bin/env bash
# Post-teardown billing check.
#
# Run after `terraform destroy` to prove nothing billable survived. Terraform only
# removes what it created and tracks in state; this checks AWS directly and does not
# trust state at all.
#
# Exits non-zero if anything that costs money is still there, so the nightly destroy
# job fails loudly instead of quietly leaking a few dollars a month.
#
#   ./verify-teardown.sh dev
#
# Needs: aws CLI v2, jq. Uses AWS_REGION from the environment.

set -uo pipefail

ENVIRONMENT="${1:-dev}"
PROJECT="${PROJECT_TAG:-afterhourz}"
REGION="${AWS_REGION:-us-east-1}"

FOUND=0
SKIPPED=0

red()   { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
dim()   { printf '\033[2m%s\033[0m\n' "$*"; }

# Run an aws query. An AccessDenied is reported as a skip, not a pass, so a missing
# IAM permission can never look like a clean result.
q() {
  local out
  if ! out="$(aws --region "$REGION" "$@" 2>&1)"; then
    if grep -qi 'AccessDenied\|UnauthorizedOperation\|not authorized' <<<"$out"; then
      return 2
    fi
    echo "$out" >&2
    return 3
  fi
  printf '%s' "$out"
}

check() {
  local label="$1"; shift
  local result rc
  result="$("$@")"; rc=$?

  if [ "$rc" -eq 2 ]; then
    dim "  SKIP  $label (no permission to check)"
    SKIPPED=$((SKIPPED + 1))
  elif [ "$rc" -ne 0 ]; then
    dim "  SKIP  $label (check errored)"
    SKIPPED=$((SKIPPED + 1))
  elif [ -n "$result" ] && [ "$result" != "None" ]; then
    red   "  BILLING  $label"
    sed 's/^/           /' <<<"$result"
    FOUND=$((FOUND + 1))
  else
    green "  clear    $label"
  fi
}

# --- the checks ---------------------------------------------------------------

# Elastic IPs are account-wide and bill whether or not they are attached to anything.
# This is the classic ECS/EKS leak, so it is checked first and across the whole account.
elastic_ips() {
  q ec2 describe-addresses \
    --query 'Addresses[].{ip:PublicIp,assoc:AssociationId,alloc:AllocationId}' \
    --output text
}

# An EKS LoadBalancer Service or a console-created ELB is invisible to Terraform.
load_balancers() {
  q elbv2 describe-load-balancers \
    --query "LoadBalancers[?contains(LoadBalancerName, \`${PROJECT}\`)].{name:LoadBalancerName,state:State.Code}" \
    --output text
}

classic_load_balancers() {
  q elb describe-load-balancers \
    --query "LoadBalancerDescriptions[?contains(LoadBalancerName, \`${PROJECT}\`)].LoadBalancerName" \
    --output text
}

# ~$32/month each. This project never creates one; if one exists, something is wrong.
nat_gateways() {
  q ec2 describe-nat-gateways \
    --filter "Name=state,Values=pending,available" \
    --query 'NatGateways[].{id:NatGatewayId,state:State}' \
    --output text
}

running_tasks() {
  q ecs list-tasks --cluster "${PROJECT}-${ENVIRONMENT}" --desired-status RUNNING \
    --query 'taskArns' --output text
}

ecs_services() {
  q ecs describe-services --cluster "${PROJECT}-${ENVIRONMENT}" --services api \
    --query 'services[?desiredCount>`0`].{name:serviceName,desired:desiredCount}' \
    --output text
}

ec2_instances() {
  q ec2 describe-instances \
    --filters "Name=tag:Project,Values=${PROJECT}" \
              "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query 'Reservations[].Instances[].{id:InstanceId,state:State.Name}' \
    --output text
}

# Detached volumes keep billing after the instance is gone.
orphan_volumes() {
  q ec2 describe-volumes --filters "Name=status,Values=available" \
    --query 'Volumes[].{id:VolumeId,gb:Size}' --output text
}

# Not billable on their own, but an orphaned ENI blocks VPC deletion, which is how a
# "successful" destroy leaves a half-torn-down environment behind.
orphan_enis() {
  q ec2 describe-network-interfaces --filters "Name=status,Values=available" \
    --query 'NetworkInterfaces[].{id:NetworkInterfaceId,desc:Description}' --output text
}

project_vpcs() {
  q ec2 describe-vpcs --filters "Name=tag:Project,Values=${PROJECT}" \
    --query 'Vpcs[].{id:VpcId,cidr:CidrBlock}' --output text
}

# --- run ----------------------------------------------------------------------

echo "Post-teardown billing check: project=${PROJECT} env=${ENVIRONMENT} region=${REGION}"
echo

check "Elastic IPs (account-wide)"        elastic_ips
check "Application/Network load balancers" load_balancers
check "Classic load balancers"             classic_load_balancers
check "NAT gateways"                       nat_gateways
check "Running ECS tasks"                  running_tasks
check "ECS services with desiredCount > 0" ecs_services
check "EC2 instances"                      ec2_instances
check "Unattached EBS volumes"             orphan_volumes
check "Orphaned network interfaces"        orphan_enis
check "Project VPCs"                       project_vpcs

echo
if [ "$FOUND" -gt 0 ]; then
  red "$FOUND check(s) found resources that are still billing. Teardown is NOT clean."
  exit 1
fi

if [ "$SKIPPED" -gt 0 ]; then
  echo "Teardown clear on every check that ran, but $SKIPPED could not be checked."
  echo "Grant the deploy role the matching Describe permissions, or verify those by hand."
  exit 0
fi

green "Teardown is clean. Nothing in this environment is billing."
