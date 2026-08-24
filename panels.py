"""Panel UI -- connections list/connect form for OCI Connector.

SIDEBAR CONTENT -- NO CARDS ANYWHERE, per ~/UI_INTERFACE_STANDARD.md's
"left sidebar, no decorated cards" rule (same convention as AWS/Azure/
GCP Connector's panels.py).

Every section (connections, connect form) is a plain ui.Stack, content
stacked vertically and left-aligned, sections separated by ui.Divider() --
no Card border/background/shadow anywhere in this slot. Disconnect lives
only in the "App settings" screen (panels_settings.py). The one secondary
"App settings" button is always the LAST element at the bottom of the
sidebar.

WHY 5 FIELDS (tenancy OCID, user OCID, fingerprint, private key, region),
UNLIKE GCP'S SINGLE JSON-KEY FIELD.

Unlike GCP's Service Account (one downloadable JSON file), OCI's API
signing key setup gives the user each of these values SEPARATELY across
different Console screens (tenancy/user OCID from Console headers,
fingerprint + key from the API Keys page) -- there is no single file to
paste. The form asks for each explicitly, matching how OCI's own SDK
config file (~/.oci/config) is structured.

Per Vlad's standing rule: every input carries its own label (not just a
placeholder), placeholders are contextually specific, and the form
container is stretched to the full width of the left sidebar with its
contents stretched to fill it. The sidebar carries NO instructions that
duplicate the "How do I set this up?" modal.
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext
import handlers as h


def _settings_button() -> ui.UINode:
    """The one required secondary entry point into the settings screen --
    always the last element at the bottom of the sidebar."""
    return ui.Button(
        "App settings", variant="secondary", size="sm", full_width=True,
        icon="settings", on_click=ui.Call("__panel__oci_settings"),
    )


def _connection_row(c: dict) -> ui.UINode:
    return ui.Stack(direction="v", gap=1, children=[
        ui.Text(c.get("title") or c.get("tenancy_ocid", ""), variant="body"),
        ui.Text(f"Region: {c.get('region', '')}", variant="caption"),
    ])


def _connections_section(connections: list[dict]) -> ui.UINode:
    if not connections:
        return ui.Text("No OCI tenancies connected yet.", variant="caption")
    children: list[ui.UINode] = []
    for i, c in enumerate(connections):
        if i > 0:
            children.append(ui.Divider())
        children.append(_connection_row(c))
    return ui.Stack(direction="v", gap=2, children=children)


def _connect_section() -> ui.UINode:
    return ui.Stack(direction="v", gap=3, full_width=True, children=[
        ui.Text("Connect a tenancy", variant="heading"),
        ui.Stack(direction="v", gap=2, full_width=True, children=[
            ui.Input(
                label="Tenancy OCID", param_name="tenancy_ocid",
                placeholder="ocid1.tenancy.oc1..aaaaaaaa...",
            ),
            ui.Input(
                label="User OCID", param_name="user_ocid",
                placeholder="ocid1.user.oc1..aaaaaaaa...",
            ),
            ui.Input(
                label="Fingerprint", param_name="fingerprint",
                placeholder="aa:bb:cc:dd:ee:ff:...",
            ),
            ui.Input(
                label="Private key (PEM)", param_name="private_key",
                input_type="password", multiline=True,
                placeholder="-----BEGIN PRIVATE KEY-----",
            ),
            ui.Input(
                label="Home region", param_name="region",
                placeholder="us-ashburn-1",
            ),
            ui.Input(
                label="Compartment OCID (optional)", param_name="compartment_ocid",
                placeholder="Leave empty to use the tenancy root compartment",
            ),
        ]),
        ui.Button(
            "Verify and connect", variant="primary", full_width=True,
            on_click=ui.Call("connect_oci"),
        ),
    ])


@ext.panel("oci_sidebar", slot="left", title="Oracle Cloud Infrastructure")
async def oci_sidebar_panel(ctx, **kwargs) -> object:
    connections = await h._load_connections(ctx)
    content = ui.Stack(direction="v", gap=4, full_width=True, children=[
        _connections_section(connections),
        ui.Divider(),
        _connect_section(),
        ui.Divider(),
        _settings_button(),
    ])
    return content


@ext.panel("oci_center", slot="center", title="Oracle Cloud Infrastructure", center_overlay=True)
async def oci_center_panel(ctx, **kwargs) -> object:
    return ui.Stack(direction="v", align="center", justify="center", full_height=True, children=[
        ui.Text("Nothing to show here", variant="body"),
    ])


@ext.panel("oci_connect_help", slot="center", title="How do I set this up?", center_overlay=True)
async def oci_connect_help(ctx, **kwargs) -> object:
    content = ui.Stack(direction="v", gap=3, children=[
        ui.Text("1. Sign in to the OCI Console and open your Profile menu (top right) -- copy "
                "your User OCID from there."),
        ui.Text("2. Open the tenancy name link in the same menu (or Administration > Tenancy "
                "Details) and copy the Tenancy OCID."),
        ui.Text("3. Open your user's Console page > API Keys > Add API Key > Generate API Key "
                "Pair. Download the private key file, then copy the Fingerprint shown after "
                "adding the key."),
        ui.Text("4. Open your user's Groups membership (or ask an administrator) and confirm "
                "you belong to a group with at least a Read policy on the compartment you "
                "want to explore -- this is enough to start safely."),
        ui.Text("5. Paste the Tenancy OCID, User OCID, Fingerprint, Private Key and your home "
                "region into the form and Verify and connect."),
        ui.Divider(),
        ui.Alert(
            title="Scope your IAM policy before connecting",
            message=(
                "We strongly recommend a Read-only policy for your first connection "
                "(e.g. 'Allow group ImperalReaders to read all-resources in compartment "
                "...'). Broader policies (manage) work too, but a mis-scoped policy can "
                "affect real infrastructure -- start read-only and widen only when you "
                "need to act."
            ),
            type="warning",
        ),
        ui.Divider(),
        ui.Alert(
            title="Covers the operational core, not every OCI service",
            message=(
                "This connector reads/manages Compute instances, Object Storage buckets, "
                "Autonomous Database systems, IAM users/groups (read-only), Monitoring "
                "alarms, and Usage/Cost reports. OKE, Data Science/GenAI, and Oracle "
                "Analytics Cloud are out of scope."
            ),
            type="info",
        ),
    ])
    return content
