"""Pydantic params models + SDL entity contracts for Oracle Cloud
Infrastructure Connector.

All params models are module-scope (V17 federal invariant, same rule as
AWS/Azure/GCP Connector's schemas.py).
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from imperal_sdk import sdl


class NoParams(BaseModel):
    """Explicit empty params model -- V17 disallows untyped handlers."""
    pass


# ──────────────────────────────────────────────────────────────────────────
# Connection
# ──────────────────────────────────────────────────────────────────────────


class ConnectOciParams(BaseModel):
    tenancy_ocid: str = Field(..., description="Your OCI tenancy OCID, e.g. ocid1.tenancy.oc1..aaaa...")
    user_ocid: str = Field(..., description="Your OCI user OCID, e.g. ocid1.user.oc1..aaaa...")
    fingerprint: str = Field(..., description="The fingerprint of your API signing key, e.g. aa:bb:cc:dd:...")
    private_key: str = Field(..., description="The PEM contents of your API signing key's private key.")
    region: str = Field(..., description="Your home region, e.g. us-ashburn-1.")
    compartment_ocid: str = Field("", description="Optional compartment to scope reads to; leave empty to use the tenancy root compartment.")
    label: str = Field("", description="Optional friendly name for this OCI tenancy connection.")


class ProviderConnection(sdl.Entity):
    id: str = ""
    title: str = ""
    connected: bool = False
    detail: str = ""
    tenancy_ocid: str = ""
    region: str = ""


class ProviderConnectionList(sdl.Entity):
    connections: list[ProviderConnection] = []


class DisconnectOciParams(BaseModel):
    connection_id: str = Field(..., description="The connection id to disconnect, from list_connections.")


class DeleteResult(sdl.Entity):
    deleted: bool = False
    id: str = ""


class ConnectionIdParams(BaseModel):
    connection_id: str = Field("", description="Which connected OCI tenancy to use; omit to use the only/most recent one.")


# ──────────────────────────────────────────────────────────────────────────
# Cloud Overview (Tier 3 value-add)
# ──────────────────────────────────────────────────────────────────────────


class GetCloudOverviewParams(ConnectionIdParams):
    pass


class CloudOverview(sdl.Entity):
    instances_running: int = 0
    instances_stopped: int = 0
    bucket_count: int = 0
    autonomous_db_count: int = 0
    month_to_date_cost: str = ""
    currency: str = "USD"


# ──────────────────────────────────────────────────────────────────────────
# Compute
# ──────────────────────────────────────────────────────────────────────────


class ComputeInstance(sdl.Entity):
    id: str = ""
    display_name: str = ""
    shape: str = ""
    lifecycle_state: str = ""
    availability_domain: str = ""
    time_created: str = ""


class ComputeInstanceList(sdl.Entity):
    instances: list[ComputeInstance] = []


class ListInstancesParams(ConnectionIdParams):
    pass


class InstanceResourceParams(ConnectionIdParams):
    instance_id: str = Field(..., description="The Compute instance's OCID.")


class InstanceActionResult(sdl.Entity):
    instance_id: str = ""
    action: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Object Storage
# ──────────────────────────────────────────────────────────────────────────


class StorageBucket(sdl.Entity):
    name: str = ""
    namespace: str = ""
    storage_tier: str = ""
    time_created: str = ""


class StorageBucketList(sdl.Entity):
    buckets: list[StorageBucket] = []


class ListBucketsParams(ConnectionIdParams):
    pass


class BucketResourceParams(ConnectionIdParams):
    bucket_name: str = Field(..., description="The Object Storage bucket's name.")


class StorageObject(sdl.Entity):
    name: str = ""
    size: int = 0
    time_modified: str = ""


class StorageObjectList(sdl.Entity):
    objects: list[StorageObject] = []


# ──────────────────────────────────────────────────────────────────────────
# Autonomous Database
# ──────────────────────────────────────────────────────────────────────────


class AutonomousDatabase(sdl.Entity):
    id: str = ""
    display_name: str = ""
    db_workload: str = ""
    lifecycle_state: str = ""
    cpu_core_count: int = 0


class AutonomousDatabaseList(sdl.Entity):
    databases: list[AutonomousDatabase] = []


class ListDatabasesParams(ConnectionIdParams):
    pass


# ──────────────────────────────────────────────────────────────────────────
# IAM (read-only)
# ──────────────────────────────────────────────────────────────────────────


class IamUser(sdl.Entity):
    id: str = ""
    name: str = ""
    description: str = ""
    time_created: str = ""


class IamUserList(sdl.Entity):
    users: list[IamUser] = []


class IamGroup(sdl.Entity):
    id: str = ""
    name: str = ""
    description: str = ""


class IamGroupList(sdl.Entity):
    groups: list[IamGroup] = []


class ListIamParams(ConnectionIdParams):
    pass


# ──────────────────────────────────────────────────────────────────────────
# Monitoring
# ──────────────────────────────────────────────────────────────────────────


class MonitoringAlarm(sdl.Entity):
    id: str = ""
    display_name: str = ""
    severity: str = ""
    is_enabled: bool = False


class MonitoringAlarmList(sdl.Entity):
    alarms: list[MonitoringAlarm] = []


class ListAlarmsParams(ConnectionIdParams):
    pass


# ──────────────────────────────────────────────────────────────────────────
# Usage / Cost
# ──────────────────────────────────────────────────────────────────────────


class GetUsageParams(ConnectionIdParams):
    time_start: str = Field(..., description="ISO 8601 start timestamp, e.g. 2026-08-01T00:00:00Z.")
    time_end: str = Field(..., description="ISO 8601 end timestamp, e.g. 2026-08-24T00:00:00Z.")


class UsageResult(sdl.Entity):
    time_start: str = ""
    time_end: str = ""
    items: list[dict] = []
