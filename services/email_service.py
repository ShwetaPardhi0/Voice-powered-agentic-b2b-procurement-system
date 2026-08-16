"""
services/email_service.py
--------------------------
Email Notification Service for Manager Purchase Order Approvals.

Sends structured HTML notification emails to MANAGER_EMAIL when a purchase order
exceeding ₹25,000 is created and pending approval.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv(override=True)

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
MANAGER_EMAIL = os.getenv("MANAGER_EMAIL", "manager@company.com")


def send_email_po_approval_request(po_data: dict) -> bool:
    """
    Sends an email notification to MANAGER_EMAIL detailing a PO pending approval.

    Returns True if sent successfully, False otherwise.
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("[Email Service Warning] SMTP_USERNAME or SMTP_PASSWORD not configured. Skipping email notification.")
        return False

    po_id = po_data.get("po_id", "N/A")
    supplier = po_data.get("supplier_id", "N/A")
    sku = po_data.get("sku", "N/A")
    qty = po_data.get("quantity", 0)
    unit_price = po_data.get("unit_price", 0.0)
    total_val = po_data.get("total_value", 0.0)

    subject = f"[Action Required] Purchase Order Approval Request - PO #{po_id} (₹{total_val:,.2f})"

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f4f6f9; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: #ffffff; border-radius: 8px; padding: 25px; border: 1px solid #e1e4e8;">
          <h2 style="color: #d9534f; margin-top: 0;">🚨 Purchase Order Approval Required</h2>
          <p style="font-size: 15px; color: #333333;">
            A new Purchase Order has been created that exceeds the automatic approval limit of <strong>₹25,000.00</strong>.
          </p>
          <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <tr style="background-color: #f8f9fa;">
              <td style="padding: 10px; border: 1px solid #dddddd; font-weight: bold;">PO Number</td>
              <td style="padding: 10px; border: 1px solid #dddddd;">{po_id}</td>
            </tr>
            <tr>
              <td style="padding: 10px; border: 1px solid #dddddd; font-weight: bold;">Supplier ID</td>
              <td style="padding: 10px; border: 1px solid #dddddd;">{supplier}</td>
            </tr>
            <tr style="background-color: #f8f9fa;">
              <td style="padding: 10px; border: 1px solid #dddddd; font-weight: bold;">Product SKU</td>
              <td style="padding: 10px; border: 1px solid #dddddd;">{sku}</td>
            </tr>
            <tr>
              <td style="padding: 10px; border: 1px solid #dddddd; font-weight: bold;">Quantity</td>
              <td style="padding: 10px; border: 1px solid #dddddd;">{qty:,} units</td>
            </tr>
            <tr style="background-color: #f8f9fa;">
              <td style="padding: 10px; border: 1px solid #dddddd; font-weight: bold;">Unit Price</td>
              <td style="padding: 10px; border: 1px solid #dddddd;">₹{unit_price:,.2f}</td>
            </tr>
            <tr style="background-color: #fff3cd;">
              <td style="padding: 10px; border: 1px solid #dddddd; font-weight: bold; color: #856404;">Total Amount</td>
              <td style="padding: 10px; border: 1px solid #dddddd; font-weight: bold; color: #856404;">₹{total_val:,.2f}</td>
            </tr>
          </table>
          <p style="font-size: 14px; color: #555555;">
            An interactive approval card has been posted to Slack channel. You can approve or reject this purchase order directly in Slack.
          </p>
          <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" />
          <p style="font-size: 12px; color: #888888;">
            B2B Agentic Inventory Control Tower — Autonomous Procurement System
          </p>
        </div>
      </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USERNAME
    msg["To"] = MANAGER_EMAIL
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=5) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_USERNAME, [MANAGER_EMAIL], msg.as_string())
        print(f"[Email Service] Sent PO Approval notification email to {MANAGER_EMAIL} for PO {po_id}.")
        return True
    except Exception as e:
        print(f"[Email Service Error] Failed to send email: {e}")
        return False
