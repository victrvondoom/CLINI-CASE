"""End-to-end ECS Fargate deploy for the ClinCase backend.

Idempotent — re-running picks up existing resources by name and reconciles.
Run once, get an ALB URL, and the backend is live on AWS.

Resources created (named with the `clincase-` prefix):
  - IAM: clincase-task-execution-role  (ECR pull + CloudWatch Logs)
  - IAM: clincase-task-role             (S3 + Bedrock from inside the container)
  - SG:  clincase-alb-sg                (port 80 from internet)
  - SG:  clincase-task-sg               (port 8000 from ALB SG)
  - ALB: clincase-alb                   (public, in default-VPC subnets)
  - TG:  clincase-tg                    (target type ip, port 8000, /api/v1/healthz)
  - LSN: HTTP :80 -> TG
  - LOG: /ecs/clincase-backend          (14-day retention)
  - ECS: clincase                       (cluster)
  - ECS: clincase-backend-task          (task definition family)
  - ECS: clincase-backend               (service, 1 task)
"""
from __future__ import annotations

import json
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv("../.env")

# Load .env before importing AWS/deploy helpers so they observe its settings.
import boto3  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402

from _ecs_task_env import (  # noqa: E402
    build_task_env_and_secrets,
    execution_role_secret_policy,
    secret_arns,
)

REGION = "us-east-1"
ACCOUNT = boto3.client("sts").get_caller_identity()["Account"]
IMAGE_URI = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/clincase-backend:latest"
S3_POLICIES_BUCKET = "clincase-demo-26697"

ec2 = boto3.client("ec2", region_name=REGION)
iam = boto3.client("iam", region_name=REGION)
ecs = boto3.client("ecs", region_name=REGION)
elb = boto3.client("elbv2", region_name=REGION)
logs = boto3.client("logs", region_name=REGION)


def step(msg: str) -> None:
    print(f"\n{'=' * 4}  {msg}  {'=' * 4}", flush=True)


def info(msg: str) -> None:
    print(f"  {msg}", flush=True)


# ---------------------------------------------------------------------------
# 1. Networking — default VPC + 3 subnets
# ---------------------------------------------------------------------------
def get_network() -> tuple[str, list[str]]:
    step("Network")
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])["Vpcs"]
    if not vpcs:
        raise RuntimeError("No default VPC in this account")
    vpc_id = vpcs[0]["VpcId"]
    subs = ec2.describe_subnets(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "default-for-az", "Values": ["true"]},
        ],
    )["Subnets"]
    subnet_ids = [s["SubnetId"] for s in subs[:3]]  # 3 AZs is enough
    info(f"VPC      = {vpc_id}")
    info(f"subnets  = {subnet_ids}")
    return vpc_id, subnet_ids


def find_or_create_sg(name: str, desc: str, vpc_id: str) -> str:
    sgs = ec2.describe_security_groups(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "group-name", "Values": [name]},
        ],
    )["SecurityGroups"]
    if sgs:
        return sgs[0]["GroupId"]
    r = ec2.create_security_group(GroupName=name, Description=desc, VpcId=vpc_id)
    return r["GroupId"]


def authorize_safe(sg_id: str, **kwargs) -> None:
    try:
        ec2.authorize_security_group_ingress(GroupId=sg_id, **kwargs)
    except ClientError as e:
        if e.response["Error"]["Code"] != "InvalidPermission.Duplicate":
            raise


def setup_security_groups(vpc_id: str) -> tuple[str, str]:
    step("Security groups")
    alb_sg = find_or_create_sg("clincase-alb-sg", "ALB ingress (HTTP)", vpc_id)
    task_sg = find_or_create_sg("clincase-task-sg", "ECS tasks ingress (8000 from ALB)", vpc_id)

    # ALB SG: allow 80 from anywhere
    authorize_safe(
        alb_sg,
        IpPermissions=[{
            "IpProtocol": "tcp", "FromPort": 80, "ToPort": 80,
            "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "public-http"}],
        }],
    )
    # Task SG: allow 8000 from ALB SG only
    authorize_safe(
        task_sg,
        IpPermissions=[{
            "IpProtocol": "tcp", "FromPort": 8000, "ToPort": 8000,
            "UserIdGroupPairs": [{"GroupId": alb_sg, "Description": "from-alb"}],
        }],
    )
    info(f"ALB SG  = {alb_sg}")
    info(f"task SG = {task_sg}")
    return alb_sg, task_sg


# ---------------------------------------------------------------------------
# 2. IAM roles
# ---------------------------------------------------------------------------
ECS_TASKS_TRUST = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "ecs-tasks.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }],
})


def create_or_get_role(name: str, trust_doc: str, attach_managed: list[str], inline: dict | None = None) -> str:
    try:
        r = iam.get_role(RoleName=name)
        arn = r["Role"]["Arn"]
        info(f"role exists: {name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise
        r = iam.create_role(RoleName=name, AssumeRolePolicyDocument=trust_doc)
        arn = r["Role"]["Arn"]
        info(f"role created: {name}")

    for policy_arn in attach_managed:
        try:
            iam.attach_role_policy(RoleName=name, PolicyArn=policy_arn)
        except ClientError as e:
            if e.response["Error"]["Code"] not in ("EntityAlreadyExists", "LimitExceeded"):
                raise

    if inline:
        for pname, doc in inline.items():
            iam.put_role_policy(RoleName=name, PolicyName=pname, PolicyDocument=json.dumps(doc))
    return arn


def setup_iam_roles() -> tuple[str, str]:
    step("IAM roles")
    exec_arn = create_or_get_role(
        "clincase-task-execution-role",
        ECS_TASKS_TRUST,
        attach_managed=[
            "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
        ],
        inline=(
            {"clincase-read-task-secrets": pol}
            if (pol := execution_role_secret_policy(
                secret_arns(os.environ), os.environ.get("SECRETS_KMS_KEY_ARN")
            ))
            else None
        ),
    )
    info(f"exec role = {exec_arn}")

    task_arn = create_or_get_role(
        "clincase-task-role",
        ECS_TASKS_TRUST,
        attach_managed=[],
        inline={
            "clincase-app-permissions": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "PoliciesS3Bucket",
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject", "s3:PutObject", "s3:DeleteObject",
                            "s3:ListBucket", "s3:CopyObject",
                        ],
                        "Resource": [
                            f"arn:aws:s3:::{S3_POLICIES_BUCKET}",
                            f"arn:aws:s3:::{S3_POLICIES_BUCKET}/*",
                        ],
                    },
                    {
                        "Sid": "BedrockInvoke",
                        "Effect": "Allow",
                        "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                        "Resource": "*",
                    },
                    {
                        "Sid": "BedrockKB",
                        "Effect": "Allow",
                        "Action": [
                            "bedrock:Retrieve", "bedrock:RetrieveAndGenerate",
                            "bedrock-agent:StartIngestionJob", "bedrock-agent:GetIngestionJob",
                            "bedrock-agent:ListKnowledgeBases", "bedrock-agent:ListDataSources",
                        ],
                        "Resource": "*",
                    },
                    {
                        "Sid": "Textract",
                        "Effect": "Allow",
                        "Action": ["textract:AnalyzeDocument", "textract:DetectDocumentText"],
                        "Resource": "*",
                    },
                ],
            },
        },
    )
    info(f"task role = {task_arn}")
    # Newly created roles take a few seconds to be usable
    time.sleep(8)
    return exec_arn, task_arn


# ---------------------------------------------------------------------------
# 3. ALB + Target group + listener
# ---------------------------------------------------------------------------
def setup_alb(vpc_id: str, subnet_ids: list[str], alb_sg: str) -> tuple[str, str]:
    step("ALB + target group")
    # ALB
    try:
        r = elb.create_load_balancer(
            Name="clincase-alb",
            Subnets=subnet_ids,
            SecurityGroups=[alb_sg],
            Scheme="internet-facing",
            Type="application",
            IpAddressType="ipv4",
        )
        alb = r["LoadBalancers"][0]
        info(f"ALB created: {alb['DNSName']}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "DuplicateLoadBalancerName":
            raise
        alb = elb.describe_load_balancers(Names=["clincase-alb"])["LoadBalancers"][0]
        info(f"ALB exists:  {alb['DNSName']}")
    alb_arn = alb["LoadBalancerArn"]
    alb_dns = alb["DNSName"]

    # Target group (ip target type for Fargate awsvpc networking)
    try:
        r = elb.create_target_group(
            Name="clincase-tg",
            Protocol="HTTP",
            Port=8000,
            VpcId=vpc_id,
            TargetType="ip",
            HealthCheckProtocol="HTTP",
            HealthCheckPath="/api/v1/healthz",
            HealthCheckIntervalSeconds=30,
            HealthCheckTimeoutSeconds=10,
            HealthyThresholdCount=2,
            UnhealthyThresholdCount=5,
            Matcher={"HttpCode": "200"},
        )
        tg = r["TargetGroups"][0]
        info(f"TG created: {tg['TargetGroupArn']}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "DuplicateTargetGroupName":
            raise
        tg = elb.describe_target_groups(Names=["clincase-tg"])["TargetGroups"][0]
        info(f"TG exists:  {tg['TargetGroupArn']}")
    tg_arn = tg["TargetGroupArn"]

    # Listener — HTTP :80 -> TG
    listeners = elb.describe_listeners(LoadBalancerArn=alb_arn)["Listeners"]
    if not any(listener["Port"] == 80 for listener in listeners):
        elb.create_listener(
            LoadBalancerArn=alb_arn,
            Protocol="HTTP",
            Port=80,
            DefaultActions=[{"Type": "forward", "TargetGroupArn": tg_arn}],
        )
        info("listener :80 created")
    else:
        info("listener :80 exists")
    return alb_dns, tg_arn


# ---------------------------------------------------------------------------
# 4. CloudWatch Logs
# ---------------------------------------------------------------------------
def setup_logs() -> str:
    step("CloudWatch log group")
    name = "/ecs/clincase-backend"
    try:
        logs.create_log_group(logGroupName=name)
        logs.put_retention_policy(logGroupName=name, retentionInDays=14)
        info(f"created  {name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceAlreadyExistsException":
            raise
        info(f"exists   {name}")
    return name


# ---------------------------------------------------------------------------
# 5. ECS cluster + task definition + service
# ---------------------------------------------------------------------------
CORS_ORIGINS = (
    "http://clincase-demo-26697.s3-website-us-east-1.amazonaws.com,"
    "http://localhost:5173"
)


def env_for_task() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """(environment, secrets) for the container definition.

    AWS_* are never passed: Fargate provides credentials through the task role. ENVIRONMENT is always
    explicit (DEPLOY_ENVIRONMENT, default "staging"), and outside dev every credential must be a Secrets
    Manager ARN (`<NAME>_SECRET_ARN`) — see `_ecs_task_env.py`."""
    return build_task_env_and_secrets(os.environ, region=REGION, cors_origins=CORS_ORIGINS)


def setup_cluster_and_service(
    *, exec_arn: str, task_arn: str, log_group: str,
    subnet_ids: list[str], task_sg: str, tg_arn: str,
) -> str:
    step("ECS cluster + task definition + service")
    try:
        ecs.create_cluster(clusterName="clincase")
        info("cluster clincase created")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ClusterContainsContainerInstancesException":
            # Idempotent — describe to check it exists, otherwise rethrow
            existing = ecs.describe_clusters(clusters=["clincase"])["clusters"]
            if not existing or existing[0]["status"] == "INACTIVE":
                raise
        info("cluster clincase exists")

    # Register task definition
    task_env, task_secrets = env_for_task()
    td = ecs.register_task_definition(
        family="clincase-backend-task",
        networkMode="awsvpc",
        requiresCompatibilities=["FARGATE"],
        cpu="1024",       # 1 vCPU
        memory="2048",    # 2 GB
        executionRoleArn=exec_arn,
        taskRoleArn=task_arn,
        containerDefinitions=[{
            "name": "backend",
            "image": IMAGE_URI,
            "essential": True,
            "portMappings": [{"containerPort": 8000, "protocol": "tcp"}],
            "environment": task_env,
            "secrets": task_secrets,
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": log_group,
                    "awslogs-region": REGION,
                    "awslogs-stream-prefix": "ecs",
                },
            },
            "healthCheck": {
                "command": ["CMD-SHELL", "curl -fs http://localhost:8000/api/v1/healthz || exit 1"],
                "interval": 30,
                "timeout": 5,
                "retries": 3,
                "startPeriod": 60,
            },
        }],
    )
    td_arn = td["taskDefinition"]["taskDefinitionArn"]
    info(f"task def: {td_arn.split('/')[-1]}")

    # Create or update service
    services = ecs.describe_services(cluster="clincase", services=["clincase-backend"])["services"]
    active = [s for s in services if s.get("status") == "ACTIVE"]
    if active:
        ecs.update_service(
            cluster="clincase",
            service="clincase-backend",
            taskDefinition=td_arn,
            forceNewDeployment=True,
        )
        info("service updated (force redeploy)")
    else:
        ecs.create_service(
            cluster="clincase",
            serviceName="clincase-backend",
            taskDefinition=td_arn,
            launchType="FARGATE",
            desiredCount=1,
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": subnet_ids,
                    "securityGroups": [task_sg],
                    "assignPublicIp": "ENABLED",  # default-VPC public subnets, needed for ECR pull
                },
            },
            loadBalancers=[{
                "targetGroupArn": tg_arn,
                "containerName": "backend",
                "containerPort": 8000,
            }],
            healthCheckGracePeriodSeconds=120,
        )
        info("service created")
    return td_arn


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def main() -> int:
    print(f"AWS account : {ACCOUNT}")
    print(f"region      : {REGION}")
    print(f"image       : {IMAGE_URI}")
    print(f"S3 bucket   : {S3_POLICIES_BUCKET}")

    env_for_task()  # fail fast on unsafe/missing configuration, before any AWS resource is created
    vpc_id, subnet_ids = get_network()
    alb_sg, task_sg = setup_security_groups(vpc_id)
    exec_arn, task_arn = setup_iam_roles()
    log_group = setup_logs()
    alb_dns, tg_arn = setup_alb(vpc_id, subnet_ids, alb_sg)
    setup_cluster_and_service(
        exec_arn=exec_arn, task_arn=task_arn, log_group=log_group,
        subnet_ids=subnet_ids, task_sg=task_sg, tg_arn=tg_arn,
    )

    print()
    print("=" * 60)
    print(f"  ALB URL: http://{alb_dns}")
    print(f"  health : http://{alb_dns}/api/v1/healthz")
    print("=" * 60)
    print("Backend tasks take 2-5 min to become healthy. Wait, then:")
    print(f"  curl http://{alb_dns}/api/v1/healthz")
    return 0


if __name__ == "__main__":
    sys.exit(main())
