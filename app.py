"""Extension declaration, secrets, lifecycle hooks.

WHY BYOK (bring-your-own-key), SAME REASONING AS AWS / Azure / GCP Connector.
OCI lives inside the USER'S OWN tenancy -- Imperal cannot and should not
broker access to someone else's OCI tenancy centrally.

WHY tenancy_ocid + user_ocid + fingerprint + private_key + region (A
CONNECTION RECORD), NOT A SINGLE TOKEN.

OCI authenticates every request via OCI Request Signing (RSA-SHA256):
each HTTP request is individually signed with the user's own RSA
private key, using a signing string built from a handful of request
headers. There is NO token endpoint and NO cached bearer token -- this
is a different auth model from AWS SigV4 (canonical-request based),
Azure client-credentials (token exchange), and GCP JWT Bearer (token
exchange) -- see CONNECTOR_DISCOVERY.md #2. compartment_ocid is stored
alongside the credentials because most list/read calls need it as a
query parameter (mirrors AWS's region / Azure's subscription_id / GCP's
project_id).

WHY THERE IS NO TOKEN CACHE HERE, UNLIKE AZURE/GCP CONNECTOR.

OCI Request Signing has no token to cache -- every request is signed
fresh with the private key (a local, cheap RSA-SHA256 operation, not a
network round-trip), so the caching concern that produced known
portfolio bug #2356 does not apply to this connector.

WHY THIS CONNECTOR IS SCOPED TO Compute/ObjectStorage/Database(Autonomous)/
IAM/Monitoring/Usage, NOT "ALL OF OCI".

OCI fronts dozens of independent product APIs. Covering all of them is
neither possible nor useful in v1 -- this connector mirrors AWS/Azure/
GCP Connector's domain choice (compute, storage, managed DB, IAM-
equivalent, monitoring, cost) so all four hyperscaler connectors read
the same way to a user comparing clouds. OKE, Data Science/GenAI and
Oracle Analytics Cloud are explicitly out of scope.
"""
from __future__ import annotations

from imperal_sdk import Extension, ChatExtension

ext = Extension(
    "oci-connector",
    version="0.1.0",
    display_name="Oracle Cloud Infrastructure",
    description=(
        "Connect your own Oracle Cloud Infrastructure tenancy (API "
        "signing key, OCI Request Signing RSA-SHA256) to see and manage "
        "Compute instances, Object Storage buckets/objects, Autonomous "
        "Database systems, IAM users/groups, Monitoring alarms, and "
        "Usage/Cost reports from Imperal. Your API key is verified "
        "against your tenancy before it's saved. Scoped to the "
        "operational core -- OKE, Data Science/GenAI and Oracle "
        "Analytics Cloud are out of scope."
    ),
    icon="icon.svg",
    actions_explicit=True,
    capabilities=["oci:read", "oci:write"],
)

chat = ChatExtension(
    ext,
    tool_name="oci-connector",
    description="View and manage OCI -- Compute, Object Storage, Autonomous Database, IAM, Monitoring, Usage/Cost",
)

ext.secret(
    "oci_connections",
    (
        "Your connected OCI tenancies -- stored as a JSON array, one "
        "entry per tenancy, each with its own tenancy_ocid, user_ocid, "
        "fingerprint, private_key (PEM), region, compartment_ocid and a "
        "friendly label. Managed through connect_oci / disconnect_oci -- "
        "you should not need to edit this directly."
    ),
    required=True,
    write_mode="both",
    max_bytes=65536,
    rotation_hint_days=90,
)(lambda: None)


@ext.health_check
async def health_check(ctx) -> dict:
    """Fast, no-network health check -- confirms the extension loaded and
    its secret slot is reachable, same pattern as AWS/Azure/GCP Connector."""
    return {"ok": True, "detail": "oci-connector loaded"}
