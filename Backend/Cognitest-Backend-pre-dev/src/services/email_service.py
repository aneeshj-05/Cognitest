import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage

from src.config.settings import settings

logger = logging.getLogger(__name__)

_CURRENT_YEAR = datetime.now().year



def send_invitation_email(
    recipient_email: str,
    inviter_name: str,
    workspace_name: str,
    invite_url: str,
    message: str = None
) -> None:
    """Send a workspace invitation email. Logs a warning and no-ops if SMTP is unconfigured."""
    if not settings.smtp_username or not settings.smtp_password:
        logger.warning(
            "SMTP not configured — skipping invitation email to %s (URL: %s)",
            recipient_email,
            invite_url,
        )
        return

    msg = EmailMessage()
    msg["Subject"] = f"Join {workspace_name} on Cognitest"
    msg["From"] = f"Cognitest <{settings.smtp_username}>"
    msg["To"] = recipient_email

    custom_message_html = ""
    if message:
        custom_message_html = f"""
        <div style="background:#27272a;border:1px solid #3f3f46;border-radius:8px;padding:16px;margin-bottom:32px;color:#e4e4e7;font-style:italic;">
          "{message}"
        </div>
        """

    html = f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#09090b;color:#fafafa;margin:0;padding:0}}
    .c{{max-width:600px;margin:40px auto;background:#18181b;border:1px solid #27272a;border-radius:12px;padding:40px;text-align:center}}
    .logo{{font-size:24px;font-weight:700;margin-bottom:24px}}
    .title{{font-size:20px;font-weight:600;margin-bottom:16px;color:#e4e4e7}}
    .text{{font-size:15px;color:#a1a1aa;line-height:1.6;margin-bottom:32px}}
    .btn{{background:#10b981;color:#ffffff;border:none;border-radius:8px;padding:14px 28px;font-size:15px;font-weight:600;text-decoration:none;display:inline-block;margin-bottom:32px;cursor:pointer}}
    .footer{{font-size:13px;color:#71717a;margin-top:40px;border-top:1px solid #27272a;padding-top:24px}}
  </style>
</head>
<body>
  <div class="c">
    <div class="logo">Cognitest</div>
    <div class="title">You've been invited to join {workspace_name}</div>
    <div class="text">{inviter_name} has invited you to collaborate on Cognitest.</div>
    {custom_message_html}
    <a href="{invite_url}" class="btn" style="color: #ffffff;">Accept Invitation</a>
    <div class="text">If you don't want to accept, you can ignore this email.</div>
    <div class="footer">&copy; {_CURRENT_YEAR} Cognitest Inc. — Automated testing redefined.</div>
  </div>
</body>
</html>"""

    msg.set_content(
        f"{inviter_name} has invited you to join {workspace_name} on Cognitest.\n\n"
        f"Accept the invitation by visiting: {invite_url}\n"
    )
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
        logger.info("Invitation email sent to %s", recipient_email)
    except Exception:
        logger.exception("Failed to send invitation email to %s", recipient_email)


def send_otp_email(recipient_email: str, otp_code: str) -> None:
    """Send a verification OTP email. Logs a warning and no-ops if SMTP is unconfigured."""
    if not settings.smtp_username or not settings.smtp_password:
        logger.warning(
            "SMTP not configured — skipping email to %s (OTP: %s)",
            recipient_email,
            otp_code,
        )
        return

    msg = EmailMessage()
    msg["Subject"] = "Your Cognitest Verification Code"
    msg["From"] = f"Cognitest <{settings.smtp_username}>"
    msg["To"] = recipient_email

    html = f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#09090b;color:#fafafa;margin:0;padding:0}}
    .c{{max-width:600px;margin:40px auto;background:#18181b;border:1px solid #27272a;border-radius:12px;padding:40px;text-align:center}}
    .logo{{font-size:24px;font-weight:700;margin-bottom:24px}}
    .title{{font-size:20px;font-weight:600;margin-bottom:16px;color:#e4e4e7}}
    .text{{font-size:15px;color:#a1a1aa;line-height:1.6;margin-bottom:32px}}
    .otp{{background:#27272a;border:1px solid #3f3f46;border-radius:8px;padding:20px;font-size:32px;font-weight:700;letter-spacing:.2em;color:#fafafa;margin-bottom:32px;display:inline-block}}
    .footer{{font-size:13px;color:#71717a;margin-top:40px;border-top:1px solid #27272a;padding-top:24px}}
  </style>
</head>
<body>
  <div class="c">
    <div class="logo">Cognitest</div>
    <div class="title">Verify your email address</div>
    <div class="text">Use the code below to complete your sign-up. It expires in 10 minutes.</div>
    <div class="otp">{otp_code}</div>
    <div class="text">If you didn't request this, you can safely ignore it.</div>
    <div class="footer">&copy; {_CURRENT_YEAR} Cognitest Inc. — Automated testing redefined.</div>
  </div>
</body>
</html>"""

    msg.set_content(f"Your Cognitest verification code is: {otp_code}")
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
        logger.info("Verification email sent to %s", recipient_email)
    except Exception:
        logger.exception("Failed to send email to %s", recipient_email)


def send_support_ticket_email(recipient_email: str, ticket) -> None:
    """Send a support ticket confirmation email with ticket details."""
    if not settings.smtp_username or not settings.smtp_password:
        logger.warning(
            "SMTP not configured — skipping support ticket email to %s for ticket %s",
            recipient_email,
            getattr(ticket, "id", "unknown"),
        )
        return

    msg = EmailMessage()
    msg["Subject"] = "Cognitest Support Ticket Received"
    msg["From"] = f"Cognitest <{settings.smtp_username}>"
    msg["To"] = recipient_email

    html = f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#09090b;color:#fafafa;margin:0;padding:0}}
    .c{{max-width:600px;margin:40px auto;background:#18181b;border:1px solid #27272a;border-radius:12px;padding:40px;text-align:left}}
    .logo{{font-size:24px;font-weight:700;margin-bottom:24px}}
    .title{{font-size:20px;font-weight:600;margin-bottom:16px;color:#e4e4e7}}
    .text{{font-size:15px;color:#a1a1aa;line-height:1.6;margin-bottom:24px}}
    .field{{margin-bottom:12px}}
    .label{{font-weight:700;color:#e4e4e7}}
    .footer{{font-size:13px;color:#71717a;margin-top:40px;border-top:1px solid #27272a;padding-top:24px}}
  </style>
</head>
<body>
  <div class="c">
    <div class="logo">Cognitest</div>
    <div class="title">Support ticket received</div>
    <div class="text">We received your support request and will respond as soon as possible. Here are the details we received:</div>
    <div class="field"><span class="label">Ticket ID:</span> {ticket.id}</div>
    <div class="field"><span class="label">Subject:</span> {ticket.subject}</div>
    <div class="field"><span class="label">Category:</span> {ticket.category}</div>
    <div class="field"><span class="label">Description:</span><br>{ticket.description}</div>
    <div class="footer">&copy; {_CURRENT_YEAR} Cognitest Inc. — Automated testing redefined.</div>
  </div>
</body>
</html>"""

    msg.set_content(
        f"Your support ticket has been received.\n\n"
        f"Ticket ID: {ticket.id}\n"
        f"Subject: {ticket.subject}\n"
        f"Category: {ticket.category}\n"
        f"Description: {ticket.description}\n"
    )
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
        logger.info("Support ticket email sent to %s for ticket %s", recipient_email, ticket.id)
    except Exception:
        logger.exception("Failed to send support ticket email to %s", recipient_email)
