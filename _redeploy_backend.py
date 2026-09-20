"""Rebuild + push backend Docker image, force ECS redeploy."""
import subprocess
import sys
import time
import boto3

REGION = "us-east-1"
sts = boto3.client("sts")
ACCOUNT = sts.get_caller_identity()["Account"]
ECR_URI = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/authrex-backend"
TAG = f"v{int(time.time())}"

print(f"Account: {ACCOUNT}")
print(f"ECR: {ECR_URI}")
print(f"Tag: {TAG}")


def run(cmd, capture=False):
    print(f"\n$ {cmd}")
    if capture:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    subprocess.check_call(cmd, shell=True)


# 1. ECR login
ecr = boto3.client("ecr", region_name=REGION)
auth = ecr.get_authorization_token()["authorizationData"][0]
import base64
user, pwd = base64.b64decode(auth["authorizationToken"]).decode().split(":", 1)
endpoint = auth["proxyEndpoint"]
run(f'docker login -u {user} -p "{pwd}" {endpoint}')

# 2. Build the image (force amd64 since ECS Fargate is x86_64; --no-cache to bust COPY cache)
run(f'docker build --no-cache --platform linux/amd64 -t authrex-backend:{TAG} "D:/xzashr.ai Files/clincase-workspace/ClinCase/backend"')

# 3. Tag
run(f'docker tag authrex-backend:{TAG} {ECR_URI}:{TAG}')
run(f'docker tag authrex-backend:{TAG} {ECR_URI}:latest')

# 4. Push
run(f'docker push {ECR_URI}:{TAG}')
run(f'docker push {ECR_URI}:latest')

# 5. Force ECS redeployment
ecs = boto3.client("ecs", region_name=REGION)
print("\nForcing ECS new deployment...")
resp = ecs.update_service(
    cluster="clincase",
    service="clincase-backend",
    forceNewDeployment=True,
)
print(f"Service rolled — desired={resp['service']['desiredCount']}, running={resp['service']['runningCount']}")

print(f"\nDone. Wait ~60s for the new task to come up, then re-test.")
print(f"Image: {ECR_URI}:{TAG}")
