"""
services/slack_service.py
--------------------------
Slack Integration Service for Purchase Order Approvals.

Provides:
  1. Interactive Block Kit approval message dispatch (Approve & Reject buttons)
  2. Slack Webhook request signature verification (SLACK_SIGNING_SECRET)
  3. In-place message updates when PO is approved or rejected
"""

import os
import time
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier

load_dotenv(override=True)

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

slack_client = WebClient(token=SLACK_BOT_TOKEN) if SLACK_BOT_TOKEN else None
verifier = SignatureVerifier(SLACK_SIGNING_SECRET) if SLACK_SIGNING_SECRET else None


def verify_slack_signature(body_bytes: bytes, timestamp: str, signature: str) -> bool:
    """
    Verifies that incoming Slack HTTP requests originated from Slack using SLACK_SIGNING_SECRET.
    Returns True if valid, False if invalid/forged.
    """
    if not SLACK_SIGNING_SECRET:
        print("[Slack Auth Warning] SLACK_SIGNING_SECRET is not configured in .env. Skipping verification.")
        return True

    if not timestamp or not signature:
        return False

    # Check timestamp freshness (replay attack prevention within 5 minutes)
    try:
        req_timestamp = int(timestamp)
        if abs(time.time() - req_timestamp) > 60 * 5:
            print("[Slack Auth Warning] Request timestamp is expired (older than 5 minutes).")
            return False
    except ValueError:
        return False

    return verifier.is_valid(body_bytes, timestamp, signature)


DASHBOARD_BASE_URL = os.getenv("DASHBOARD_BASE_URL", "http://localhost:7000")


def send_slack_po_approval_request(po_data: dict) -> dict:
    """
    Posts an interactive Slack Block Kit message to SLACK_CHANNEL_ID for PO approval requests (> ₹25,000).
    Includes [View PO] button (linking to /po-detail/{po_id}), Risk rating, Supplier ID, [Approve], and [Reject] buttons.

    Returns:
        {"success": bool, "channel": str, "ts": str}
    """
    if not slack_client or not SLACK_CHANNEL_ID:
        print("[Slack Service Warning] SLACK_BOT_TOKEN or SLACK_CHANNEL_ID not configured.")
        return {"success": False, "channel": None, "ts": None}

    po_id = po_data.get("po_id", "N/A")
    supplier = po_data.get("supplier_id", "N/A")
    sku = po_data.get("sku", "N/A")
    qty = po_data.get("quantity", 0)
    unit_price = po_data.get("unit_price", 0.0)
    total_val = po_data.get("total_value", 0.0)
    risk_level = po_data.get("risk_level", "Medium")
    dashboard_url = f"{DASHBOARD_BASE_URL}/po-detail/{po_id}"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🚨 Purchase Order Approval Required",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*PO-{po_id}* — *₹{total_val:,.2f}*\n• *Supplier:* `{supplier}`\n• *Risk Level:* `{risk_level}`\n• *Product (SKU):* `{sku}` ({qty:,} units @ ₹{unit_price:,.2f})",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "⚠️ *Order total exceeds the ₹25,000 threshold.* Manager authorization is required.",
            },
        },
        {"type": "divider"},
        {
            "type": "actions",
            "block_id": f"po_actions_{po_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔍 View PO", "emoji": True},
                    "url": dashboard_url,
                    "action_id": "view_po_details",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🟢 Approve", "emoji": True},
                    "style": "primary",
                    "value": str(po_id),
                    "action_id": "approve_po",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔴 Reject", "emoji": True},
                    "style": "danger",
                    "value": str(po_id),
                    "action_id": "reject_po",
                },
            ],
        },
    ]

    try:
        response = slack_client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text=f"🚨 Approval Required: PO-{po_id} (Total: ₹{total_val:,.2f})",
            blocks=blocks,
        )
        print(f"[Slack Service] Posted PO Approval request for PO {po_id} to channel {SLACK_CHANNEL_ID} (ts={response['ts']})")
        return {
            "success": True,
            "channel": response["channel"],
            "ts": response["ts"],
        }
    except SlackApiError as e:
        print(f"[Slack Service API Error] Failed to post message: {e.response['error']}")
        return {"success": False, "channel": None, "ts": None}


def send_slack_po_reminder(po_data: dict, stage_title: str) -> dict:
    """
    Posts a reminder or escalation message to Slack for a pending PO.
    """
    if not slack_client or not SLACK_CHANNEL_ID:
        return {"success": False}

    po_id = po_data.get("po_id", "N/A")
    supplier = po_data.get("supplier_id", "N/A")
    total_val = po_data.get("total_value", 0.0)
    risk_level = po_data.get("risk_level", "Medium")
    dashboard_url = f"{DASHBOARD_BASE_URL}/po-detail/{po_id}"

    is_overdue = "OVERDUE" in stage_title.upper() or "ESCALAT" in stage_title.upper()
    header_emoji = "⚠️" if is_overdue else "⏰"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{header_emoji} {stage_title}: PO-{po_id}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{stage_title}*\n"
                    f"• *PO Number:* `{po_id}`\n"
                    f"• *Supplier:* `{supplier}`\n"
                    f"• *Total Value:* *₹{total_val:,.2f}*\n"
                    f"• *Risk Level:* `{risk_level}`"
                ),
            },
        },
    ]

    if not is_overdue:
        blocks.append({
            "type": "actions",
            "block_id": f"po_reminder_actions_{po_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔍 View PO", "emoji": True},
                    "url": dashboard_url,
                    "action_id": "view_po_details",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🟢 Approve", "emoji": True},
                    "style": "primary",
                    "value": str(po_id),
                    "action_id": "approve_po",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔴 Reject", "emoji": True},
                    "style": "danger",
                    "value": str(po_id),
                    "action_id": "reject_po",
                },
            ],
        })

    try:
        response = slack_client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text=f"{header_emoji} {stage_title}: PO-{po_id} (Total: ₹{total_val:,.2f})",
            blocks=blocks,
        )
        return {"success": True, "ts": response["ts"]}
    except SlackApiError as e:
        print(f"[Slack Service Error] Failed to send reminder: {e.response['error']}")
        return {"success": False}


def update_slack_po_message(channel_id: str, message_ts: str, po_id: str, status: str, action_by: str = "Manager"):
    """
    Updates the Slack Block Kit message in place when a PO is APPROVED or REJECTED.
    Removes the interactive action buttons and replaces them with an audit confirmation banner.
    """
    if not slack_client or not channel_id or not message_ts:
        return

    is_approved = status.upper() == "APPROVED"
    banner_emoji = "✅" if is_approved else "❌"
    status_text = "APPROVED" if is_approved else "REJECTED"
    status_color_text = "*APPROVED*" if is_approved else "*REJECTED*"

    updated_blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{banner_emoji} Purchase Order #{po_id} — {status_text}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{banner_emoji} *Purchase Order `{po_id}` has been {status_color_text} by {action_by}.*\n"
                    f"• *Final Status:* `{status_text}`\n"
                    f"• *Action Timestamp:* <!date^{int(time.time())}^{{date_num}} {{time_secs}}|{time.strftime('%Y-%m-%d %H:%M:%S')}>"
                ),
            },
        },
    ]

    try:
        slack_client.chat_update(
            channel=channel_id,
            ts=message_ts,
            text=f"{banner_emoji} Purchase Order {po_id} {status_text} by {action_by}",
            blocks=updated_blocks,
        )
        print(f"[Slack Service] Updated message for PO {po_id} to status '{status_text}'.")
    except SlackApiError as e:
        print(f"[Slack Service API Error] Failed to update message: {e.response['error']}")
