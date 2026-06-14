import smtplib
import os
import yaml
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

def _branding():
    try:
        with open("config.yaml", "r") as f:
            cfg = yaml.safe_load(f)
        app = cfg.get("app", {})
        return {
            "name":    app.get("name",    "DocRegistry Pro"),
            "company": app.get("company", "BK Mehta & Associates"),
            "version": app.get("version", "v1.0"),
            "tagline": app.get("tagline", "Advocate Office Registry Management System"),
        }
    except Exception:
        return {"name": "DocRegistry Pro", "company": "BK Mehta & Associates",
                "version": "v1.0", "tagline": "Advocate Office Registry Management System"}


def _smtp_config():
    return (
        os.getenv("SMTP_USER", ""),
        os.getenv("SMTP_PASS", ""),
        os.getenv("SMTP_HOST", "smtp.gmail.com"),
        int(os.getenv("SMTP_PORT", "587")),
    )


def send_email(to_email: str, subject: str, html_body: str):
    """Send an HTML email. Raises if SMTP credentials are missing or sending fails."""
    smtp_user, smtp_pass, smtp_host, smtp_port = _smtp_config()
    if not smtp_user or not smtp_pass:
        raise ValueError("SMTP credentials not set. Add SMTP_USER and SMTP_PASS to .env")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"DocRegistry Pro <{smtp_user}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_email, msg.as_string())


def _base_template(title: str, body_html: str) -> str:
    from datetime import datetime
    b = _branding()
    year = datetime.now().year
    company_esc = b["company"].replace("&", "&amp;")
    tagline_esc = b["tagline"].replace("&", "&amp;")
    return f"""
    <html><body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:20px;">
    <div style="max-width:580px;margin:auto;background:#fff;border-radius:8px;
                overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);">
      <div style="background:#1a237e;color:#fff;padding:18px 24px;">
        <h2 style="margin:0;font-size:20px;letter-spacing:.3px;">🏛️ {b["name"]}</h2>
        <p style="margin:4px 0 0;font-size:13px;opacity:.85;">
          {company_esc} &nbsp;|&nbsp; {tagline_esc}
        </p>
      </div>
      <div style="padding:28px 24px;">
        <h3 style="color:#1a237e;margin-top:0;border-bottom:2px solid #e8eaf6;
                   padding-bottom:10px;">{title}</h3>
        {body_html}
        <hr style="border:none;border-top:1px solid #eee;margin:28px 0 16px;">
        <p style="font-size:11px;color:#aaa;text-align:center;margin:0;">
          This is an automated notification from <b>{b["name"]}</b> —
          {company_esc}.<br>
          &copy; {year} All Rights Reserved. Please do not reply to this email.
        </p>
      </div>
    </div>
    </body></html>
    """


def send_password_reminder(to_email: str, full_name: str, username: str, password: str):
    """Email a newly-generated password to the user after a password reset request."""
    b = _branding()
    body = f"""
    <p>Hi <b>{full_name}</b>,</p>
    <p>You recently requested a password reset for <b>{b["name"]}</b>.
       A new password has been generated for your account:</p>
    <table style="border-collapse:collapse;width:100%;margin:16px 0;">
      <tr style="background:#f0f4ff;">
          <td style="padding:10px 14px;font-weight:bold;color:#1a237e;width:130px;">Username</td>
          <td style="padding:10px 14px;">
            <code style="background:#f0f0f0;padding:3px 8px;border-radius:4px;font-size:15px;">{username}</code>
          </td></tr>
      <tr>
          <td style="padding:10px 14px;font-weight:bold;color:#1a237e;">New Password</td>
          <td style="padding:10px 14px;">
            <code style="background:#f0f0f0;padding:3px 8px;border-radius:4px;font-size:15px;">{password}</code>
          </td></tr>
    </table>
    <div style="background:#fff8e1;border-left:4px solid #ffc107;padding:12px 16px;
                border-radius:0 6px 6px 0;margin:20px 0;">
      <b>Security Tip:</b> Please log in and keep this password safe — do not share it with
      anyone. If you did not request this reset, please contact the administrator immediately.
    </div>
    """
    send_email(
        to_email=to_email,
        subject=f"[{b['name']}] Your New Password — {username}",
        html_body=_base_template("🔑 Password Reset", body),
    )


def notify_admins_new_request(admin_emails: list, full_name: str, username: str,
                               role: str, email: str, requested_date: str):
    """Email all admins when a new access request is submitted."""
    body = f"""
    <p>A new account request has been submitted and is waiting for your approval.</p>
    <table style="border-collapse:collapse;width:100%;margin:16px 0;">
      <tr style="background:#f0f4ff;">
          <td style="padding:10px 14px;font-weight:bold;color:#1a237e;width:150px;">Full Name</td>
          <td style="padding:10px 14px;font-size:15px;"><b>{full_name}</b></td></tr>
      <tr>
          <td style="padding:10px 14px;font-weight:bold;color:#1a237e;">Username</td>
          <td style="padding:10px 14px;">
            <code style="background:#f0f0f0;padding:3px 8px;border-radius:4px;font-size:14px;">{username}</code>
          </td></tr>
      <tr style="background:#f0f4ff;">
          <td style="padding:10px 14px;font-weight:bold;color:#1a237e;">Requested Role</td>
          <td style="padding:10px 14px;">{role.title()}</td></tr>
      <tr>
          <td style="padding:10px 14px;font-weight:bold;color:#1a237e;">Email</td>
          <td style="padding:10px 14px;">{email or '—'}</td></tr>
      <tr style="background:#f0f4ff;">
          <td style="padding:10px 14px;font-weight:bold;color:#1a237e;">Requested On</td>
          <td style="padding:10px 14px;">{requested_date}</td></tr>
    </table>
    <div style="background:#fff8e1;border-left:4px solid #ffc107;padding:12px 16px;
                border-radius:0 6px 6px 0;margin:20px 0;">
      <b>Action Required:</b> Please log in to
      <b>DocRegistry Pro → User Management → Pending Requests</b>
      to approve or reject this request.
    </div>
    """
    for admin_email in admin_emails:
        try:
            send_email(
                to_email=admin_email,
                subject=f"[DocRegistry Pro] New Access Request — {full_name}",
                html_body=_base_template("🔔 New Account Request Received", body),
            )
        except Exception:
            pass


def notify_user_registration_received(to_email: str, full_name: str, username: str):
    """Send a confirmation email to the user right after they submit a request."""
    if not to_email:
        return
    body = f"""
    <p>Hi <b>{full_name}</b>,</p>
    <p>Thank you for requesting access to <b>DocRegistry Pro</b> — the Advocate Office
       Registry Management System.</p>
    <p>Your request has been successfully submitted with the following details:</p>
    <table style="border-collapse:collapse;width:100%;margin:16px 0;">
      <tr style="background:#f0f4ff;">
          <td style="padding:10px 14px;font-weight:bold;color:#1a237e;width:130px;">Full Name</td>
          <td style="padding:10px 14px;"><b>{full_name}</b></td></tr>
      <tr>
          <td style="padding:10px 14px;font-weight:bold;color:#1a237e;">Username</td>
          <td style="padding:10px 14px;">
            <code style="background:#f0f0f0;padding:3px 8px;border-radius:4px;">{username}</code>
          </td></tr>
    </table>
    <div style="background:#e8f5e9;border-left:4px solid #4caf50;padding:12px 16px;
                border-radius:0 6px 6px 0;margin:20px 0;">
      <b>What happens next?</b><br>
      Our administrator will review your request and activate your account shortly.
      You will receive another email once your account has been approved.
    </div>
    <p style="color:#555;">
      If you did not submit this request, please ignore this email or contact us immediately.
    </p>
    """
    send_email(
        to_email=to_email,
        subject="[DocRegistry Pro] Your Account Request Has Been Received",
        html_body=_base_template("✅ Request Received — Pending Approval", body),
    )


def notify_user_request_status(to_email: str, full_name: str,
                                username: str, status: str):
    """Email the requester when their request is approved or rejected."""
    if not to_email:
        return
    if status == "Approved":
        body = f"""
        <p>Hi <b>{full_name}</b>,</p>
        <p>Great news! Your DocRegistry Pro account has been
           <span style="color:#2e7d32;font-weight:bold;">Approved</span>. 🎉</p>
        <p>You can now log in using your credentials:</p>
        <table style="border-collapse:collapse;width:100%;margin:16px 0;">
          <tr style="background:#f0f4ff;">
              <td style="padding:10px 14px;font-weight:bold;color:#1a237e;width:130px;">Username</td>
              <td style="padding:10px 14px;">
                <code style="background:#f0f0f0;padding:3px 8px;border-radius:4px;">{username}</code>
              </td></tr>
          <tr>
              <td style="padding:10px 14px;font-weight:bold;color:#1a237e;">Password</td>
              <td style="padding:10px 14px;">Use the password you set during registration</td></tr>
        </table>
        <div style="background:#e8f5e9;border-left:4px solid #4caf50;padding:12px 16px;
                    border-radius:0 6px 6px 0;margin:20px 0;">
          Welcome to <b>DocRegistry Pro</b>! Please keep your credentials safe and do not
          share your password with anyone.
        </div>
        """
        subject = f"[DocRegistry Pro] 🎉 Account Approved — Welcome, {full_name}!"
    else:
        body = f"""
        <p>Hi <b>{full_name}</b>,</p>
        <p>We regret to inform you that your DocRegistry Pro account request has been
           <span style="color:#c62828;font-weight:bold;">Rejected</span>.</p>
        <p>If you believe this is a mistake or need further clarification, please contact
           the administrator directly.</p>
        <div style="background:#fff3e0;border-left:4px solid #ff9800;padding:12px 16px;
                    border-radius:0 6px 6px 0;margin:20px 0;">
          You may submit a new request if you feel this decision was made in error.
        </div>
        """
        subject = f"[DocRegistry Pro] Account Request Update — {full_name}"

    send_email(
        to_email=to_email,
        subject=subject,
        html_body=_base_template(f"Account {status}", body),
    )
