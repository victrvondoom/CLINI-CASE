"""ClinCase on AWS — Lambda + Bedrock proof-of-concept.

Deployed to Lambda with a public Function URL (CORS open) so judges can
curl the endpoint and see a live Bedrock invoke from a fully AWS-resident
runtime — Lambda → bedrock-runtime → us.anthropic.claude-haiku-4-5.

This deliberately mirrors the BedrockClient path in app/llm/bedrock.py
that the production backend uses, just trimmed to one stateless function.
"""
import json
import os

import boto3

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

_bedrock = boto3.client("bedrock-runtime", region_name=REGION)

_CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "content-type",
    "Access-Control-Allow-Methods": "POST,GET,OPTIONS",
    "Content-Type": "application/json",
}


def handler(event, _context):
    method = (
        event.get("requestContext", {}).get("http", {}).get("method") or "POST"
    ).upper()

    if method == "OPTIONS":
        return {"statusCode": 204, "headers": _CORS, "body": ""}

    if method == "GET":
        return {
            "statusCode": 200,
            "headers": _CORS,
            "body": json.dumps(
                {
                    "service": "ClinCase Bedrock Proof",
                    "model": MODEL_ID,
                    "region": REGION,
                    "usage": "POST {\"prompt\": \"...\"}",
                    "team": "AeroFyta",
                }
            ),
        }

    raw = event.get("body") or "{}"
    try:
        payload = json.loads(raw)
    except Exception:
        payload = {}

    prompt = (payload.get("prompt") or "Reply with exactly: HELLO FROM CLINCASE").strip()[
        :2000
    ]

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt}],
    }

    response = _bedrock.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    out = json.loads(response["body"].read())
    text = "".join(
        block.get("text", "")
        for block in out.get("content", [])
        if block.get("type") == "text"
    )

    return {
        "statusCode": 200,
        "headers": _CORS,
        "body": json.dumps(
            {
                "model": out.get("model"),
                "text": text,
                "usage": out.get("usage"),
                "note": "Live AWS Bedrock invoke from ClinCase Lambda Function URL",
            }
        ),
    }
