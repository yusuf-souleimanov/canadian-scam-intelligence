"""Thin wrapper around Claude on Amazon Bedrock (uses your normal AWS credentials)."""
import json
import os
import re
import time

import boto3

MODEL_ID = os.environ.get("INTEL_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

_client = None


def _bedrock():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=REGION)
    return _client


def chat(prompt: str, system: str = "", max_tokens: int = 2000, temperature: float = 0.0) -> str:
    kwargs = {
        "modelId": MODEL_ID,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
    }
    if system:
        kwargs["system"] = [{"text": system}]
    for attempt in range(4):
        try:
            resp = _bedrock().converse(**kwargs)
            return resp["output"]["message"]["content"][0]["text"]
        except _bedrock().exceptions.ThrottlingException:
            time.sleep(2 ** attempt * 5)
    raise RuntimeError("Bedrock kept throttling; try again later")


def chat_json(prompt: str, system: str = "", max_tokens: int = 2000):
    """Ask for JSON and parse the first JSON object/array in the reply."""
    text = chat(prompt, system=system, max_tokens=max_tokens)
    match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
    if not match:
        raise ValueError(f"No JSON in model reply: {text[:200]}")
    return json.loads(match.group(1))
