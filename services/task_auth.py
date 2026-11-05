"""Authenticate local task dispatch independently of reverse-proxy routing."""
import hashlib
import hmac
import json
import os
import time

from fastapi import HTTPException


def _key():
    secret = os.getenv("SECRET_KEY", "")
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="Internal task signing is not configured.")
    return hmac.new(secret.encode(), b"smarthr-local-task-v1", hashlib.sha256).digest()


def encode(payload):
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    timestamp = str(int(time.time()))
    signature = hmac.new(_key(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return body, {"Content-Type": "application/json", "X-Task-Timestamp": timestamp, "X-Task-Signature": signature}


def verify(body, headers):
    timestamp = headers.get("x-task-timestamp", "")
    try:
        age = time.time() - int(timestamp)
        if not -30 <= age <= 300:
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid internal task authorization.")
    expected = hmac.new(_key(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(headers.get("x-task-signature", ""), expected):
        raise HTTPException(status_code=401, detail="Invalid internal task authorization.")
