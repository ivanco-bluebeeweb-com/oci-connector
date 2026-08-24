"""Oracle Cloud Infrastructure REST API client -- OCI Request Signing
(RSA-SHA256) over ctx.http, no token cache needed (see app.py).

WHY MANUAL SIGNING STRING CONSTRUCTION, UNLIKE AWS SIGV4'S CANONICAL
REQUEST OR GCP'S JWT.

OCI Request Signing signs a short, fixed set of HTTP headers per
request -- `(request-target)`, `date`, `host` for GET/DELETE/HEAD, plus
`content-length`, `content-type`, `x-content-sha256` for POST/PUT/PATCH.
Unlike AWS SigV4 there is no canonical query string encoding step;
unlike GCP JWT Bearer there is no token exchange at all -- every
request is signed fresh with the user's own RSA private key via
`cryptography` (already a portfolio dependency, see DocuSign/Redox/GCP
Connector's *_client.py).

See: docs.oracle.com/en-us/iaas/Content/API/Concepts/signingrequests.htm
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit


class ProviderError(Exception):
    """Raised for any OCI REST API call that fails, carrying a
    status_code and a human-readable detail so handlers can distinguish
    auth/signing failures from ordinary not-found/validation errors."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"OCI API error {status_code}: {detail}")


def _rfc7231_date() -> str:
    return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")


def _sign_string(private_key_pem: str, signing_string: str) -> str:
    """RSA-SHA256 sign the signing string, base64-encode the result.
    Requires the `cryptography` package (declared in requirements.txt)."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
    except ImportError as exc:
        raise ProviderError(0, f"Missing dependency: {exc}") from exc

    try:
        key = serialization.load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
    except Exception as exc:
        raise ProviderError(0, f"Could not load the private key -- check it's a valid PEM: {exc}") from exc

    try:
        signature = key.sign(signing_string.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    except Exception as exc:
        raise ProviderError(0, f"Signing failed: {exc}") from exc
    return base64.b64encode(signature).decode("ascii")


def _build_auth_header(
    creds: dict, method: str, url: str, date_str: str,
    content_length: str | None = None, content_type: str | None = None,
    x_content_sha256: str | None = None,
) -> str:
    parsed = urlsplit(url)
    host = parsed.netloc
    request_target = f"{method.lower()} {parsed.path}"
    if parsed.query:
        request_target += f"?{parsed.query}"

    if method.upper() in ("POST", "PUT", "PATCH"):
        headers_order = ["(request-target)", "date", "host", "content-length", "content-type", "x-content-sha256"]
        signing_parts = [
            f"(request-target): {request_target}",
            f"date: {date_str}",
            f"host: {host}",
            f"content-length: {content_length or '0'}",
            f"content-type: {content_type or 'application/json'}",
            f"x-content-sha256: {x_content_sha256 or ''}",
        ]
    else:
        headers_order = ["(request-target)", "date", "host"]
        signing_parts = [
            f"(request-target): {request_target}",
            f"date: {date_str}",
            f"host: {host}",
        ]

    signing_string = "\n".join(signing_parts)
    signature = _sign_string(creds["private_key"], signing_string)
    key_id = f"{creds['tenancy_ocid']}/{creds['user_ocid']}/{creds['fingerprint']}"
    headers_str = " ".join(headers_order)
    return (
        f'Signature version="1",keyId="{key_id}",algorithm="rsa-sha256",'
        f'headers="{headers_str}",signature="{signature}"'
    )


def _check_status(resp, action_label: str) -> dict:
    if resp.status_code >= 400:
        try:
            body = resp.json()
            detail = body.get("message", resp.text)
        except Exception:
            detail = resp.text
        raise ProviderError(resp.status_code, f"Could not {action_label}: {detail}")
    if not resp.text:
        return {}
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


async def _oci_request(ctx, method: str, url: str, creds: dict, action_label: str, body: dict | None = None) -> dict:
    date_str = _rfc7231_date()
    headers = {"date": date_str, "accept": "application/json"}
    content_length = None
    content_type = None
    x_content_sha256 = None
    body_bytes = b""
    if method.upper() in ("POST", "PUT", "PATCH"):
        body_bytes = json.dumps(body or {}).encode("utf-8")
        content_length = str(len(body_bytes))
        content_type = "application/json"
        x_content_sha256 = base64.b64encode(hashlib.sha256(body_bytes).digest()).decode("ascii")
        headers["content-length"] = content_length
        headers["content-type"] = content_type
        headers["x-content-sha256"] = x_content_sha256

    headers["authorization"] = _build_auth_header(
        creds, method, url, date_str,
        content_length=content_length, content_type=content_type, x_content_sha256=x_content_sha256,
    )

    resp = await ctx.http.request(method=method, url=url, headers=headers, content=body_bytes or None)
    return _check_status(resp, action_label)


def _region_host(service: str, region: str) -> str:
    return f"https://{service}.{region}.oraclecloud.com"


# ──────────────────────────────────────────────────────────────────────────
# Connection verification
# ──────────────────────────────────────────────────────────────────────────


async def check_connection(ctx, creds: dict) -> dict:
    """Lightest possible call to verify an API signing key is valid:
    read the connected user's own identity record (per IDEAL_ONBOARDING
    §2.3, mirroring AWS's GetCallerIdentity / Azure's subscription read
    / GCP's project read)."""
    host = _region_host("identity", creds["region"])
    url = f"{host}/20160918/users/{creds['user_ocid']}"
    body = await _oci_request(ctx, "GET", url, creds, "verify connection")
    return {
        "name": body.get("name", ""),
        "description": body.get("description", ""),
        "lifecycle_state": body.get("lifecycleState", ""),
    }


# ──────────────────────────────────────────────────────────────────────────
# Compute
# ──────────────────────────────────────────────────────────────────────────


async def list_instances(ctx, creds: dict) -> list[dict]:
    host = _region_host("iaas", creds["region"])
    compartment = creds.get("compartment_ocid") or creds["tenancy_ocid"]
    url = f"{host}/20160918/instances?compartmentId={compartment}"
    body = await _oci_request(ctx, "GET", url, creds, "list Compute instances")
    return body if isinstance(body, list) else body.get("items", [])


async def get_instance(ctx, creds: dict, instance_id: str) -> dict:
    host = _region_host("iaas", creds["region"])
    url = f"{host}/20160918/instances/{instance_id}"
    return await _oci_request(ctx, "GET", url, creds, "read Compute instance")


async def instance_action(ctx, creds: dict, instance_id: str, action: str) -> dict:
    """action: one of START, STOP, SOFTRESET, RESET, SOFTSTOP."""
    host = _region_host("iaas", creds["region"])
    url = f"{host}/20160918/instances/{instance_id}?action={action}"
    return await _oci_request(ctx, "POST", url, creds, f"{action.lower()} Compute instance")


# ──────────────────────────────────────────────────────────────────────────
# Object Storage
# ──────────────────────────────────────────────────────────────────────────


async def get_namespace(ctx, creds: dict) -> str:
    host = _region_host("objectstorage", creds["region"])
    url = f"{host}/n/"
    body = await _oci_request(ctx, "GET", url, creds, "read Object Storage namespace")
    return body if isinstance(body, str) else body.get("raw", "").strip('"')


async def list_buckets(ctx, creds: dict, namespace: str) -> list[dict]:
    host = _region_host("objectstorage", creds["region"])
    compartment = creds.get("compartment_ocid") or creds["tenancy_ocid"]
    url = f"{host}/n/{namespace}/b/?compartmentId={compartment}"
    body = await _oci_request(ctx, "GET", url, creds, "list Object Storage buckets")
    return body if isinstance(body, list) else body.get("items", [])


async def get_bucket(ctx, creds: dict, namespace: str, bucket_name: str) -> dict:
    host = _region_host("objectstorage", creds["region"])
    url = f"{host}/n/{namespace}/b/{bucket_name}/"
    return await _oci_request(ctx, "GET", url, creds, "read Object Storage bucket")


async def list_objects(ctx, creds: dict, namespace: str, bucket_name: str) -> list[dict]:
    host = _region_host("objectstorage", creds["region"])
    url = f"{host}/n/{namespace}/b/{bucket_name}/o/"
    body = await _oci_request(ctx, "GET", url, creds, "list Object Storage objects")
    return body.get("objects", []) if isinstance(body, dict) else []


# ──────────────────────────────────────────────────────────────────────────
# Database (Autonomous Database)
# ──────────────────────────────────────────────────────────────────────────


async def list_autonomous_databases(ctx, creds: dict) -> list[dict]:
    host = _region_host("database", creds["region"])
    compartment = creds.get("compartment_ocid") or creds["tenancy_ocid"]
    url = f"{host}/20160918/autonomousDatabases?compartmentId={compartment}"
    body = await _oci_request(ctx, "GET", url, creds, "list Autonomous Database systems")
    return body if isinstance(body, list) else body.get("items", [])


# ──────────────────────────────────────────────────────────────────────────
# IAM (read-only)
# ──────────────────────────────────────────────────────────────────────────


async def list_users(ctx, creds: dict) -> list[dict]:
    host = _region_host("identity", creds["region"])
    url = f"{host}/20160918/users?compartmentId={creds['tenancy_ocid']}"
    body = await _oci_request(ctx, "GET", url, creds, "list IAM users")
    return body if isinstance(body, list) else body.get("items", [])


async def list_groups(ctx, creds: dict) -> list[dict]:
    host = _region_host("identity", creds["region"])
    url = f"{host}/20160918/groups?compartmentId={creds['tenancy_ocid']}"
    body = await _oci_request(ctx, "GET", url, creds, "list IAM groups")
    return body if isinstance(body, list) else body.get("items", [])


# ──────────────────────────────────────────────────────────────────────────
# Monitoring
# ──────────────────────────────────────────────────────────────────────────


async def list_alarms(ctx, creds: dict) -> list[dict]:
    host = _region_host("monitoring", creds["region"])
    compartment = creds.get("compartment_ocid") or creds["tenancy_ocid"]
    url = f"{host}/20180401/alarms?compartmentId={compartment}"
    body = await _oci_request(ctx, "GET", url, creds, "list Monitoring alarms")
    return body if isinstance(body, list) else body.get("items", [])


# ──────────────────────────────────────────────────────────────────────────
# Usage / Cost
# ──────────────────────────────────────────────────────────────────────────


async def request_usage_summary(ctx, creds: dict, time_start: str, time_end: str) -> dict:
    host = _region_host("usageapi", creds["region"])
    url = f"{host}/20200107/usage"
    payload = {
        "tenantId": creds["tenancy_ocid"],
        "timeUsageStarted": time_start,
        "timeUsageEnded": time_end,
        "granularity": "MONTHLY",
        "groupBy": ["service"],
    }
    return await _oci_request(ctx, "POST", url, creds, "read Usage/Cost report", body=payload)
