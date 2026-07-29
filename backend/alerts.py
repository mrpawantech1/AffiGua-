"""
alerts.py – Notification system for AffiGuard
Supports: Telegram (active), Email (active, Basic+ plans), WhatsApp (stub)
"""

import os
import html
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ── Telegram ───────────────────────────────────────────────────────────────────

def _get_telegram_token() -> Optional[str]:
    return os.getenv("TELEGRAM_BOT_TOKEN")


def send_telegram_message(chat_id: str, message: str) -> bool:
    """
    Send a message via Telegram Bot API.
    Returns True on success, False on failure.
    """
    token = _get_telegram_token()
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set – skipping alert")
        return False
    if not chat_id:
        logger.warning("No telegram_chat_id for user – skipping alert")
        return False

    import requests
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return True
        else:
            logger.error(f"Telegram API error {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


def build_alert_message(link_name: str, link_url: str,
                        status: str, layer_used: str,
                        error_msg: Optional[str] = None) -> str:
    """Build a formatted Telegram HTML alert message."""
    emoji_map = {
        "broken":       "🔴",
        "out_of_stock": "🟡",
        "error":        "⚠️",
    }
    status_label = {
        "broken":       "BROKEN",
        "out_of_stock": "OUT OF STOCK",
        "error":        "ERROR",
    }

    emoji = emoji_map.get(status, "❓")
    label = status_label.get(status, status.upper())

    # Escape all user-controlled strings before inserting into HTML message
    safe_name  = html.escape(link_name  or "Unnamed")
    safe_url   = html.escape(link_url   or "")
    safe_layer = html.escape(layer_used or "N/A")

    msg = (
        f"{emoji} <b>AffiGuard Alert</b>\n\n"
        f"<b>Link:</b> {safe_name}\n"
        f"<b>Status:</b> {label}\n"
        f"<b>URL:</b> <a href=\"{safe_url}\">{safe_url[:60]}...</a>\n"
        f"<b>Detected via:</b> {safe_layer}\n"
    )
    if error_msg:
        msg += f"<b>Error:</b> {html.escape(error_msg[:200])}\n"

    msg += "\n🔗 <a href=\"https://affiguard.com/dashboard\">View Dashboard</a>"
    return msg


def build_alert_email_html(link_name: str, link_url: str,
                            status: str, layer_used: str,
                            error_msg: Optional[str] = None) -> tuple[str, str]:
    """
    Build a (subject, html_body) pair for a link-status email alert.
    Mirrors build_alert_message() but formatted for email rendering
    instead of Telegram's HTML subset.
    """
    color_map = {
        "broken":       "#f87171",
        "out_of_stock": "#fbbf24",
        "error":        "#f87171",
    }
    label_map = {
        "broken":       "BROKEN",
        "out_of_stock": "OUT OF STOCK",
        "error":        "CHECK ERROR",
    }

    color = color_map.get(status, "#94a3b8")
    label = label_map.get(status, status.upper())

    safe_name  = html.escape(link_name  or "Unnamed")
    safe_url   = html.escape(link_url   or "")
    safe_layer = html.escape(layer_used or "N/A")

    subject = f"[AffiGuard] {safe_name} — {label}"

    error_row = ""
    if error_msg:
        error_row = f'''
        <tr>
          <td style="padding:8px 0;color:#94a3b8;font-size:13px;">Error</td>
          <td style="padding:8px 0;color:#e2e8f0;font-size:13px;">{html.escape(error_msg[:200])}</td>
        </tr>'''

    html_body = f"""
    <div style="background:#0B0F1A;padding:32px 16px;font-family:Arial,sans-serif;">
      <div style="max-width:480px;margin:0 auto;background:#151B28;border-radius:16px;padding:32px;border:1px solid rgba(255,255,255,0.08);">
        <div style="display:inline-block;background:{color}22;color:{color};font-size:12px;font-weight:700;padding:4px 12px;border-radius:999px;margin-bottom:16px;">
          {label}
        </div>
        <h2 style="color:#F8FAFC;font-size:20px;margin:0 0 20px;">{safe_name}</h2>
        <table style="width:100%;border-collapse:collapse;">
          <tr>
            <td style="padding:8px 0;color:#94a3b8;font-size:13px;width:90px;">URL</td>
            <td style="padding:8px 0;color:#00E5FF;font-size:13px;word-break:break-all;">
              <a href="{safe_url}" style="color:#00E5FF;text-decoration:none;">{safe_url[:70]}</a>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 0;color:#94a3b8;font-size:13px;">Detected via</td>
            <td style="padding:8px 0;color:#e2e8f0;font-size:13px;">{safe_layer}</td>
          </tr>{error_row}
        </table>
        <a href="https://affiguard.com/dashboard"
           style="display:inline-block;margin-top:24px;background:#00E5FF;color:#000;
                  padding:10px 20px;border-radius:8px;font-weight:700;font-size:14px;
                  text-decoration:none;">
          View Dashboard →
        </a>
      </div>
    </div>
    """
    return subject, html_body


def build_plan_expiry_message(full_name: str, plan: str,
                               days_left: int) -> str:
    """Build a plan expiry warning message."""
    safe_name = html.escape(full_name or "there")
    safe_plan = html.escape((plan or "").upper())
    if days_left <= 0:
        return (
            f"🚫 <b>Plan Expired – AffiGuard</b>\n\n"
            f"Hi {safe_name},\n"
            f"Your <b>{safe_plan}</b> plan has expired.\n"
            f"Link monitoring has been paused.\n\n"
            f"🔗 <a href=\"https://affiguard.com/dashboard\">Renew Now</a>"
        )
    return (
        f"⏰ <b>Plan Expiry Reminder – AffiGuard</b>\n\n"
        f"Hi {safe_name},\n"
        f"Your <b>{safe_plan}</b> plan expires in "
        f"<b>{days_left} day(s)</b>.\n"
        f"Renew to keep monitoring your links.\n\n"
        f"🔗 <a href=\"https://affiguard.com/dashboard\">Renew Now</a>"
    )


# ── WhatsApp (stub) ────────────────────────────────────────────────────────────

def send_whatsapp_message(phone: str, message: str) -> bool:
    """
    WhatsApp alert stub.
    Implement using Twilio, Meta Cloud API, or WATI when ready.
    """
    logger.info(f"[STUB] WhatsApp to {phone}: {message[:80]}")
    return False  # stub returns False until implemented


# ── Dispatcher ────────────────────────────────────────────────────────────────

def dispatch_alert(user: dict, link: dict, status: str,
                   layer_used: str, error_msg: Optional[str] = None,
                   send_email_fn=None) -> dict:
    """
    Dispatch alert to all configured channels for a user.

    Channels:
      - Telegram: sent if user has telegram_chat_id configured (all plans).
      - Email: sent if user's plan is Basic or higher AND send_email_fn is
        provided. Free plan does not get email alerts — Telegram only.
      - WhatsApp: stub, not yet implemented.

    Args:
        send_email_fn: callable(to_email, subject, html_body) -> bool.
            Passed in from app.py to avoid a circular import between
            alerts.py and app.py (app.py owns the SMTP connection logic).

    Returns dict of {channel: success_bool}.
    """
    results = {}

    message = build_alert_message(
        link_name=link.get("name", "Unnamed"),
        link_url=link.get("url", ""),
        status=status,
        layer_used=layer_used,
        error_msg=error_msg,
    )

    # Telegram — available on all plans
    chat_id = user.get("telegram_chat_id")
    if chat_id:
        ok = send_telegram_message(chat_id, message)
        results["telegram"] = ok

    # Email — Pro plan and above only (matches pricing page: Basic is
    # Telegram-only, Email alerts start at Pro).
    user_plan = (user.get("plan") or "free").lower()
    email_eligible_plans = {"pro", "business"}
    user_email = user.get("email")
    if send_email_fn and user_email and user_plan in email_eligible_plans:
        subject, html_body = build_alert_email_html(
            link_name=link.get("name", "Unnamed"),
            link_url=link.get("url", ""),
            status=status,
            layer_used=layer_used,
            error_msg=error_msg,
        )
        ok = send_email_fn(user_email, subject, html_body)
        results["email"] = ok

    # WhatsApp (stub)
    wa_num = user.get("whatsapp_number")
    if wa_num:
        ok = send_whatsapp_message(wa_num, message)
        results["whatsapp"] = ok

    return results
