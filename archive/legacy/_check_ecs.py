import boto3
ecs = boto3.client("ecs", region_name="us-east-1")
logs = boto3.client("logs", region_name="us-east-1")

svc = ecs.describe_services(cluster="authrex", services=["authrex-backend"])["services"][0]
for d in svc["deployments"]:
    print(f"deployment status={d['status']} taskDef={d['taskDefinition'].split('/')[-1]} "
          f"running={d['runningCount']} desired={d['desiredCount']} "
          f"createdAt={d['createdAt'].strftime('%H:%M:%S')}")

streams = logs.describe_log_streams(
    logGroupName="/ecs/authrex-backend",
    orderBy="LastEventTime",
    descending=True,
    limit=2,
)["logStreams"]
for s in streams[:1]:
    print(f"\n=== {s['logStreamName']} ===")
    events = logs.get_log_events(
        logGroupName="/ecs/authrex-backend",
        logStreamName=s["logStreamName"],
        limit=25,
        startFromHead=False,
    )["events"]
    for e in events[-25:]:
        print(e["message"][:250])
