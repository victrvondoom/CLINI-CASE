"""Force ECS to use the new tagged image by registering a new task def revision."""
import boto3
import json

REGION = "us-east-1"
ecs = boto3.client("ecs", region_name=REGION)

# Find latest tag from ECR
ecr = boto3.client("ecr", region_name=REGION)
images = ecr.describe_images(
    repositoryName="authrex-backend",
    filter={"tagStatus": "TAGGED"},
)["imageDetails"]
images.sort(key=lambda i: i["imagePushedAt"], reverse=True)
latest_tagged = next(
    (t for t in images[0]["imageTags"] if t.startswith("v")),
    "latest",
)
print(f"Latest version tag: {latest_tagged}")

# Get current task def
td = ecs.describe_task_definition(taskDefinition="authrex-backend-task")["taskDefinition"]

# Replace image with explicit tag
new_containers = []
for c in td["containerDefinitions"]:
    nc = dict(c)
    if c["name"] == "backend":
        nc["image"] = f"023902411996.dkr.ecr.us-east-1.amazonaws.com/authrex-backend:{latest_tagged}"
    new_containers.append(nc)

# Re-register
new_td = ecs.register_task_definition(
    family=td["family"],
    networkMode=td["networkMode"],
    requiresCompatibilities=td["requiresCompatibilities"],
    cpu=td["cpu"],
    memory=td["memory"],
    executionRoleArn=td["executionRoleArn"],
    taskRoleArn=td["taskRoleArn"],
    containerDefinitions=new_containers,
)["taskDefinition"]
new_arn = new_td["taskDefinitionArn"]
print(f"New task def: {new_arn.split('/')[-1]}")

# Update service to new revision
ecs.update_service(
    cluster="authrex",
    service="authrex-backend",
    taskDefinition=new_arn,
    forceNewDeployment=True,
)
print(f"Service updated to use new task def revision.")
