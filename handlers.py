"""Chat functions for OCI Connector: connection management, Compute,
Object Storage, Autonomous Database, IAM (read-only), Monitoring,
Usage/Cost, and a cloud overview (Tier 3 value-add). Built on
oci_client.py / schemas.py, following the same shape as AWS/Azure/GCP
Connector's handlers.py.
"""
from __future__ import annotations

import json
import uuid

from imperal_sdk import ActionResult

import oci_client as oci
from app import ext, chat
from schemas import (
    NoParams,
    ConnectOciParams, ProviderConnection, ProviderConnectionList,
    DisconnectOciParams, DeleteResult, ConnectionIdParams,
    GetCloudOverviewParams, CloudOverview,
    ListInstancesParams, ComputeInstance, ComputeInstanceList,
    InstanceResourceParams, InstanceActionResult,
    ListBucketsParams, StorageBucket, StorageBucketList,
    BucketResourceParams, StorageObject, StorageObjectList,
    ListDatabasesParams, AutonomousDatabase, AutonomousDatabaseList,
    ListIamParams, IamUser, IamUserList, IamGroup, IamGroupList,
    ListAlarmsParams, MonitoringAlarm, MonitoringAlarmList,
    GetUsageParams, UsageResult,
)

_SECRET_NAME = "oci_connections"


# ──────────────────────────────────────────────────────────────────────────
# Connection storage helpers -- one secret holding a JSON array of
# connection records, same precedent as AWS/Azure/GCP Connector.
# ──────────────────────────────────────────────────────────────────────────

async def _load_connections(ctx) -> list[dict]:
    raw = await ctx.secrets.get(_SECRET_NAME)
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


async def _save_connections(ctx, connections: list[dict]) -> None:
    await ctx.secrets.set(_SECRET_NAME, json.dumps(connections))


async def _find_connection(ctx, connection_id: str) -> dict | None:
    connections = await _load_connections(ctx)
    if not connection_id and len(connections) == 1:
        return connections[0]
    for c in connections:
        if c.get("id") == connection_id:
            return c
    return None


async def _resolve(ctx, connection_id: str) -> dict | None:
    return await _find_connection(ctx, connection_id)


def _creds(conn: dict) -> dict:
    return {
        "tenancy_ocid": conn.get("tenancy_ocid", ""),
        "user_ocid": conn.get("user_ocid", ""),
        "fingerprint": conn.get("fingerprint", ""),
        "private_key": conn.get("private_key", ""),
        "region": conn.get("region", ""),
        "compartment_ocid": conn.get("compartment_ocid", ""),
    }


def _no_connection() -> ActionResult:
    return ActionResult.error("No OCI tenancy connected yet. Use connect_oci first.")


def _err(prefix: str, e: "oci.ProviderError") -> ActionResult:
    return ActionResult.error(f"{prefix}: {e.detail}")


@chat.function(
    "connect_oci",
    "Connect your own Oracle Cloud Infrastructure tenancy by saving an API signing key (tenancy OCID + user OCID + fingerprint + private key) plus your home region, after checking it actually works via a harmless Identity read. A Read-only IAM policy is strongly recommended for the user you create.",
    action_type="write",
    chain_callable=True,
    data_model=ProviderConnection,
    event="oci-connector.connect_oci",
    effects=["oci.provider.connected"],
)
async def connect_oci(ctx, params: ConnectOciParams) -> ActionResult:
    """Connect an OCI tenancy after verifying the signing key actually works."""
    creds = {
        "tenancy_ocid": params.tenancy_ocid.strip(),
        "user_ocid": params.user_ocid.strip(),
        "fingerprint": params.fingerprint.strip(),
        "private_key": params.private_key.strip(),
        "region": params.region.strip(),
        "compartment_ocid": params.compartment_ocid.strip(),
    }
    try:
        detail = await oci.check_connection(ctx, creds)
    except oci.ProviderError as e:
        return _err("Couldn't verify your OCI signing key", e)

    connections = await _load_connections(ctx)
    conn_id = str(uuid.uuid4())
    record = {
        "id": conn_id,
        "title": params.label or params.tenancy_ocid[-12:],
        **creds,
    }
    connections.append(record)
    await _save_connections(ctx, connections)
    return ActionResult.success(ProviderConnection(
        id=conn_id, title=record["title"], connected=True,
        detail=detail, tenancy_ocid=params.tenancy_ocid, region=params.region,
    ), summary="Oci connected.")


@chat.function(
    "disconnect_oci",
    "Disconnect an OCI tenancy: deletes the saved API signing key. Nothing in OCI itself is changed.",
    action_type="write",
    chain_callable=True,
    event="oci-connector.disconnect_oci",
    effects=["oci.provider.disconnected"],
    data_model=DeleteResult,
)
async def disconnect_oci(ctx, params: DisconnectOciParams) -> ActionResult:
    """Disconnect an OCI tenancy: deletes the saved signing key."""
    connections = await _load_connections(ctx)
    remaining = [c for c in connections if c.get("id") != params.connection_id]
    if len(remaining) == len(connections):
        return ActionResult.error("No connection found with that id.")
    await _save_connections(ctx, remaining)
    return ActionResult.success(DeleteResult(deleted=True, id=params.connection_id), summary="Oci disconnected.")


@chat.function(
    "list_connections",
    "List the connected Oracle Cloud Infrastructure tenancies.",
    action_type="read",
    chain_callable=True,
    data_model=ProviderConnectionList,
)
async def list_connections(ctx, params: NoParams) -> ActionResult:
    """List the connected OCI tenancies."""
    connections = await _load_connections(ctx)
    items = [
        ProviderConnection(
            id=c.get("id", ""), title=c.get("title", ""), connected=True,
            detail="", tenancy_ocid=c.get("tenancy_ocid", ""), region=c.get("region", ""),
        )
        for c in connections
    ]
    return ActionResult.success(ProviderConnectionList(connections=items), summary="Connections listed.")


# ──────────────────────────────────────────────────────────────────────────
# Compute
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_virtual_machines",
    "List Compute instances in the connected OCI tenancy, optionally filtered to a compartment.",
    action_type="read",
    chain_callable=True,
    data_model=ComputeInstanceList,
)
async def list_virtual_machines(ctx, params: ListInstancesParams) -> ActionResult:
    """List Compute instances in the connected OCI tenancy."""
    conn = await _resolve(ctx, params.connection_id)
    if not conn:
        return _no_connection()
    try:
        items = await oci.list_instances(ctx, _creds(conn))
    except oci.ProviderError as e:
        return _err("Couldn't list Compute instances", e)
    out = [
        ComputeInstance(
            id=i.get("id", ""), display_name=i.get("displayName", ""),
            shape=i.get("shape", ""), lifecycle_state=i.get("lifecycleState", ""),
            availability_domain=i.get("availabilityDomain", ""),
            time_created=i.get("timeCreated", ""),
        )
        for i in items
    ]
    return ActionResult.success(ComputeInstanceList(instances=out), summary="Virtual machines listed.")


@chat.function(
    "get_virtual_machine",
    "Read one Compute instance in full.",
    action_type="read",
    chain_callable=True,
    data_model=ComputeInstance,
)
async def get_virtual_machine(ctx, params: InstanceResourceParams) -> ActionResult:
    """Read one Compute instance in full."""
    conn = await _resolve(ctx, params.connection_id)
    if not conn:
        return _no_connection()
    try:
        i = await oci.get_instance(ctx, _creds(conn), params.instance_id)
    except oci.ProviderError as e:
        return _err("Couldn't read that Compute instance", e)
    return ActionResult.success(ComputeInstance(
        id=i.get("id", ""), display_name=i.get("displayName", ""),
        shape=i.get("shape", ""), lifecycle_state=i.get("lifecycleState", ""),
        availability_domain=i.get("availabilityDomain", ""),
        time_created=i.get("timeCreated", ""),
    ), summary="Virtual machine retrieved.")


@chat.function(
    "start_virtual_machine",
    "Start a stopped Compute instance.",
    action_type="write",
    chain_callable=True,
    data_model=InstanceActionResult,
    event="oci-connector.start_instance",
    effects=["oci.instance.started"],
)
async def start_virtual_machine(ctx, params: InstanceResourceParams) -> ActionResult:
    """Start a stopped Compute instance."""
    conn = await _resolve(ctx, params.connection_id)
    if not conn:
        return _no_connection()
    try:
        await oci.instance_action(ctx, _creds(conn), params.instance_id, "START")
    except oci.ProviderError as e:
        return _err("Couldn't start that Compute instance", e)
    return ActionResult.success(InstanceActionResult(instance_id=params.instance_id, action="start_requested"), summary="Virtual machine start requested.")


@chat.function(
    "stop_virtual_machine",
    "Stop a running Compute instance.",
    action_type="write",
    chain_callable=True,
    data_model=InstanceActionResult,
    event="oci-connector.stop_instance",
    effects=["oci.instance.stopped"],
)
async def stop_virtual_machine(ctx, params: InstanceResourceParams) -> ActionResult:
    """Stop a running Compute instance."""
    conn = await _resolve(ctx, params.connection_id)
    if not conn:
        return _no_connection()
    try:
        await oci.instance_action(ctx, _creds(conn), params.instance_id, "STOP")
    except oci.ProviderError as e:
        return _err("Couldn't stop that Compute instance", e)
    return ActionResult.success(InstanceActionResult(instance_id=params.instance_id, action="stop_requested"), summary="Virtual machine stop requested.")


@chat.function(
    "restart_virtual_machine",
    "Restart (reset) a Compute instance.",
    action_type="write",
    chain_callable=True,
    data_model=InstanceActionResult,
    event="oci-connector.restart_instance",
    effects=["oci.instance.restarted"],
)
async def restart_virtual_machine(ctx, params: InstanceResourceParams) -> ActionResult:
    """Restart (reset) a Compute instance."""
    conn = await _resolve(ctx, params.connection_id)
    if not conn:
        return _no_connection()
    try:
        await oci.instance_action(ctx, _creds(conn), params.instance_id, "RESET")
    except oci.ProviderError as e:
        return _err("Couldn't restart that Compute instance", e)
    return ActionResult.success(InstanceActionResult(instance_id=params.instance_id, action="restart_requested"), summary="Virtual machine restart requested.")


# ──────────────────────────────────────────────────────────────────────────
# Object Storage
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_storage_accounts",
    "List Object Storage buckets in the connected OCI tenancy's namespace.",
    action_type="read",
    chain_callable=True,
    data_model=StorageBucketList,
)
async def list_storage_accounts(ctx, params: ListBucketsParams) -> ActionResult:
    """List Object Storage buckets in the connected tenancy's namespace."""
    conn = await _resolve(ctx, params.connection_id)
    if not conn:
        return _no_connection()
    creds = _creds(conn)
    try:
        namespace = await oci.get_namespace(ctx, creds)
        items = await oci.list_buckets(ctx, creds, namespace)
    except oci.ProviderError as e:
        return _err("Couldn't list Object Storage buckets", e)
    out = [
        StorageBucket(name=b.get("name", ""), namespace=namespace,
                       storage_tier=b.get("storageTier", ""), time_created=b.get("timeCreated", ""))
        for b in items
    ]
    return ActionResult.success(StorageBucketList(buckets=out), summary="Storage accounts listed.")


@chat.function(
    "get_storage_account",
    "Read one Object Storage bucket's metadata in full.",
    action_type="read",
    chain_callable=True,
    data_model=StorageBucket,
)
async def get_storage_account(ctx, params: BucketResourceParams) -> ActionResult:
    """Read one Object Storage bucket's metadata in full."""
    conn = await _resolve(ctx, params.connection_id)
    if not conn:
        return _no_connection()
    creds = _creds(conn)
    try:
        namespace = await oci.get_namespace(ctx, creds)
        b = await oci.get_bucket(ctx, creds, namespace, params.bucket_name)
    except oci.ProviderError as e:
        return _err("Couldn't read that bucket", e)
    return ActionResult.success(StorageBucket(
        name=b.get("name", ""), namespace=namespace,
        storage_tier=b.get("storageTier", ""), time_created=b.get("timeCreated", ""),
    ), summary="Storage account retrieved.")


@chat.function(
    "list_blob_containers",
    "List objects inside one Object Storage bucket, optionally filtered by name prefix.",
    action_type="read",
    chain_callable=True,
    data_model=StorageObjectList,
)
async def list_blob_containers(ctx, params: BucketResourceParams) -> ActionResult:
    """List objects inside one Object Storage bucket."""
    conn = await _resolve(ctx, params.connection_id)
    if not conn:
        return _no_connection()
    creds = _creds(conn)
    try:
        namespace = await oci.get_namespace(ctx, creds)
        items = await oci.list_objects(ctx, creds, namespace, params.bucket_name)
    except oci.ProviderError as e:
        return _err("Couldn't list objects in that bucket", e)
    out = [
        StorageObject(name=o.get("name", ""), size=o.get("size", 0), time_created=o.get("timeCreated", ""))
        for o in items
    ]
    return ActionResult.success(StorageObjectList(objects=out), summary="Blob containers listed.")


# ──────────────────────────────────────────────────────────────────────────
# Autonomous Database
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_sql_databases",
    "List Autonomous Database systems in the connected OCI tenancy/compartment.",
    action_type="read",
    chain_callable=True,
    data_model=AutonomousDatabaseList,
)
async def list_sql_databases(ctx, params: ListDatabasesParams) -> ActionResult:
    """List Autonomous Database systems in the connected tenancy/compartment."""
    conn = await _resolve(ctx, params.connection_id)
    if not conn:
        return _no_connection()
    try:
        items = await oci.list_autonomous_databases(ctx, _creds(conn))
    except oci.ProviderError as e:
        return _err("Couldn't list Autonomous Database systems", e)
    out = [
        AutonomousDatabase(
            id=d.get("id", ""), display_name=d.get("displayName", ""),
            db_name=d.get("dbName", ""), lifecycle_state=d.get("lifecycleState", ""),
            db_workload=d.get("dbWorkload", ""), cpu_core_count=d.get("cpuCoreCount", 0),
        )
        for d in items
    ]
    return ActionResult.success(AutonomousDatabaseList(databases=out), summary="Sql databases listed.")


# ──────────────────────────────────────────────────────────────────────────
# IAM (read-only)
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_iam_users",
    "List IAM users configured in the connected OCI tenancy.",
    action_type="read",
    chain_callable=True,
    data_model=IamUserList,
)
async def list_iam_users(ctx, params: ListIamParams) -> ActionResult:
    """List IAM users configured in the connected tenancy."""
    conn = await _resolve(ctx, params.connection_id)
    if not conn:
        return _no_connection()
    try:
        items = await oci.list_users(ctx, _creds(conn))
    except oci.ProviderError as e:
        return _err("Couldn't list IAM users", e)
    out = [
        IamUser(id=u.get("id", ""), name=u.get("name", ""), description=u.get("description", ""),
                lifecycle_state=u.get("lifecycleState", ""))
        for u in items
    ]
    return ActionResult.success(IamUserList(users=out), summary="Iam users listed.")


@chat.function(
    "list_role_assignments",
    "List IAM groups configured in the connected OCI tenancy -- OCI's IAM-equivalent to role assignments.",
    action_type="read",
    chain_callable=True,
    data_model=IamGroupList,
)
async def list_role_assignments(ctx, params: ListIamParams) -> ActionResult:
    """List IAM groups configured in the connected tenancy."""
    conn = await _resolve(ctx, params.connection_id)
    if not conn:
        return _no_connection()
    try:
        items = await oci.list_groups(ctx, _creds(conn))
    except oci.ProviderError as e:
        return _err("Couldn't list IAM groups", e)
    out = [
        IamGroup(id=g.get("id", ""), name=g.get("name", ""), description=g.get("description", ""),
                  lifecycle_state=g.get("lifecycleState", ""))
        for g in items
    ]
    return ActionResult.success(IamGroupList(groups=out), summary="Role assignments listed.")


# ──────────────────────────────────────────────────────────────────────────
# Monitoring
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_metric_alerts",
    "List Monitoring alarms configured in the connected OCI tenancy/compartment.",
    action_type="read",
    chain_callable=True,
    data_model=MonitoringAlarmList,
)
async def list_metric_alerts(ctx, params: ListAlarmsParams) -> ActionResult:
    """List Monitoring alarms configured in the connected tenancy/compartment."""
    conn = await _resolve(ctx, params.connection_id)
    if not conn:
        return _no_connection()
    try:
        items = await oci.list_alarms(ctx, _creds(conn))
    except oci.ProviderError as e:
        return _err("Couldn't list Monitoring alarms", e)
    out = [
        MonitoringAlarm(
            id=a.get("id", ""), display_name=a.get("displayName", ""),
            severity=a.get("severity", ""), is_enabled=a.get("isEnabled", False),
        )
        for a in items
    ]
    return ActionResult.success(MonitoringAlarmList(alarms=out), summary="Metric alerts listed.")


# ──────────────────────────────────────────────────────────────────────────
# Usage / Cost
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "query_costs",
    "Read OCI Usage/Cost data for the connected tenancy over a time window.",
    action_type="read",
    chain_callable=True,
    data_model=UsageResult,
)
async def query_costs(ctx, params: GetUsageParams) -> ActionResult:
    """Read OCI Usage/Cost data for the connected tenancy over a time window."""
    conn = await _resolve(ctx, params.connection_id)
    if not conn:
        return _no_connection()
    try:
        body = await oci.request_usage_summary(ctx, _creds(conn), params.time_start, params.time_end)
    except oci.ProviderError as e:
        return _err("Couldn't read Usage/Cost data", e)
    items = body.get("items", []) or []
    total = sum(float(i.get("computedAmount", 0) or 0) for i in items)
    return ActionResult.success(UsageResult(
        total_cost=str(total), currency="USD", line_item_count=len(items),
    ), summary="Query costs done.")


# ──────────────────────────────────────────────────────────────────────────
# Cloud Overview (Tier 3 value-add)
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "get_cloud_overview",
    "Value-add report: one-glance OCI tenancy health snapshot -- Compute instance counts by status, Object Storage bucket count, and Autonomous Database count.",
    action_type="read",
    chain_callable=True,
    data_model=CloudOverview,
)
async def get_cloud_overview(ctx, params: GetCloudOverviewParams) -> ActionResult:
    """Value-add report: one-glance OCI tenancy health snapshot."""
    conn = await _resolve(ctx, params.connection_id)
    if not conn:
        return _no_connection()
    creds = _creds(conn)
    running = stopped = 0
    try:
        instances = await oci.list_instances(ctx, creds)
        for i in instances:
            if i.get("lifecycleState") == "RUNNING":
                running += 1
            else:
                stopped += 1
    except oci.ProviderError:
        pass
    bucket_count = 0
    try:
        namespace = await oci.get_namespace(ctx, creds)
        bucket_count = len(await oci.list_buckets(ctx, creds, namespace))
    except oci.ProviderError:
        pass
    db_count = 0
    try:
        db_count = len(await oci.list_autonomous_databases(ctx, creds))
    except oci.ProviderError:
        pass
    return ActionResult.success(CloudOverview(
        instances_running=running, instances_stopped=stopped,
        bucket_count=bucket_count, autonomous_database_count=db_count,
    ), summary="Cloud overview retrieved.")
