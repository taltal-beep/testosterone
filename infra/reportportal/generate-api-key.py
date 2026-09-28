#!/usr/bin/env python3
"""Regenerate deterministic ReportPortal API key + SQL hash for local seed."""

from __future__ import annotations

import base64
import hashlib
import struct
import uuid

FIXED_UUID = uuid.UUID("11111111-1111-4111-8111-111111111111")
KEY_NAME = "testo-local-validation"


def _to_signed(value: int) -> int:
    if value >= 2**63:
        return value - 2**64
    return value


def _java_uuid_bytes(value: uuid.UUID) -> bytes:
    hi = _to_signed((value.int >> 64) & 0xFFFFFFFFFFFFFFFF)
    lo = _to_signed(value.int & 0xFFFFFFFFFFFFFFFF)
    return struct.pack(">qq", hi, lo)


def generate_api_key(*, name: str = KEY_NAME, salt: uuid.UUID = FIXED_UUID) -> tuple[str, str]:
    normalized = name.replace("_", "-").replace(" ", "-").replace(",", "")
    name_bytes = normalized.encode("utf-8")
    salt_bytes = _java_uuid_bytes(salt)
    full_hash = hashlib.sha3_256(name_bytes + salt_bytes).digest()
    payload = salt_bytes + full_hash
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    api_key = f"{normalized}_{encoded}"
    db_hash = hashlib.sha3_256(api_key.encode()).hexdigest().upper()
    return api_key, db_hash


def main() -> None:
    api_key, db_hash = generate_api_key()
    print(f"REPORTPORTAL_TOKEN={api_key}")
    print(f"DB_HASH={db_hash}")


if __name__ == "__main__":
    main()
