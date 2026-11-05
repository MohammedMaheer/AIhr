"""Authenticated encryption for provider tokens, bound to their owner and use."""
import base64
import hashlib
import hmac
import json
import os

from cryptography.fernet import Fernet, InvalidToken


PREFIX = "enc:v1:"


def _cipher():
    secret = os.getenv("SECRET_KEY", "")
    if len(secret) < 32:
        raise ValueError("A stable SECRET_KEY is required to protect provider tokens.")
    key = hmac.new(secret.encode(), b"smarthr-oauth-token-encryption-v1", hashlib.sha256).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def seal(value, *, user_id, provider, field):
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("Invalid provider token.")
    data = {"value": value, "user": str(user_id), "provider": provider, "field": field}
    return PREFIX + _cipher().encrypt(json.dumps(data, separators=(",", ":")).encode()).decode()


def open_token(value, *, user_id, provider, field):
    if value is None:
        return None
    # Existing installations may have plaintext rows; encrypt on the next save.
    if not value.startswith(PREFIX):
        return value
    try:
        data = json.loads(_cipher().decrypt(value[len(PREFIX):].encode()))
        if (data.get("user") != str(user_id) or data.get("provider") != provider
                or data.get("field") != field or not isinstance(data.get("value"), str)):
            raise ValueError("Provider token binding mismatch.")
        return data["value"]
    except (InvalidToken, TypeError, KeyError, UnicodeError, ValueError) as exc:
        raise ValueError("Stored provider credentials could not be verified. Reconnect the account.") from exc
