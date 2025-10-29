import os
import httpx

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM", "Thermostat App <noreply@thermostat.local>")

def send_email(to: str, subject: str, html: str):
    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": EMAIL_FROM},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
    }

    try:
        response = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        print(f"[Email] Sent successfully to {to}")
    except Exception as e:
        import traceback
        print("[Email Error]", e)
        traceback.print_exc()
        raise
# import os
# import smtplib
# from email.message import EmailMessage
# from dotenv import load_dotenv
# from pathlib import Path

# # load .env once here (same trick you used in db/database.py)
# load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

# SMTP_HOST = os.getenv("SMTP_HOST")
# SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
# SMTP_USER = os.getenv("SMTP_USER")
# SMTP_PASS = os.getenv("SMTP_PASS")
# SMTP_FROM = os.getenv("SMTP_FROM", "no-reply@thermostat.local")

# def send_email(to: str, subject: str, html: str):
#     msg = EmailMessage()
#     msg["From"] = SMTP_FROM
#     msg["To"] = to
#     msg["Subject"] = subject
#     msg.set_content("HTML email required")
#     msg.add_alternative(html, subtype="html")

#     with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
#         s.starttls()
#         s.login(SMTP_USER, SMTP_PASS)
#         s.send_message(msg)