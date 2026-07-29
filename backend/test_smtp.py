"""Run with your backend's .venv, from the backend/ folder:

    python test_smtp.py aanchalsingh02022003@gmail.com

Sends one plain test email using whatever SMTP_* settings are in your
.env right now - completely independent of the rest of the app - so we
can tell whether this is a Gmail/SMTP config problem or an app-logic
problem (e.g. the TASK_ASSIGNMENT_TEST_EMAIL env var not being set).
"""
import os
import smtplib
import sys
from email.message import EmailMessage


def main() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    to_email = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SMTP_USERNAME")
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")

    print(f"SMTP_HOST: {host}")
    print(f"SMTP_PORT: {port}")
    print(f"SMTP_USERNAME: {username}")
    print(f"SMTP_PASSWORD set: {'yes' if password else 'NO'}")
    print(f"Sending test email to: {to_email}\n")

    if not host:
        print(">>> SMTP_HOST is not set - .env isn't being read, or that line is missing.")
        sys.exit(1)
    if not to_email:
        print(">>> No recipient given. Usage: python test_smtp.py you@example.com")
        sys.exit(1)

    message = EmailMessage()
    message["From"] = username or "noreply@meetflow.ai"
    message["To"] = to_email
    message["Subject"] = "MeetFlow AI - SMTP test"
    message.set_content("If you got this, your SMTP settings work correctly.")

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.set_debuglevel(1)  # prints the full SMTP conversation below
            smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
        print(f"\n✅ SUCCESS - check the inbox (and Spam folder) for {to_email}")
    except smtplib.SMTPAuthenticationError as e:
        print(f"\n❌ AUTH FAILED: {e}")
        print(
            "\n>>> Gmail is rejecting SMTP_PASSWORD. Gmail does not accept your\n"
            "    normal account password for SMTP anymore - you need an App\n"
            "    Password instead (requires 2-Step Verification to be on):\n"
            "    1. https://myaccount.google.com/apppasswords\n"
            "    2. Generate one for 'Mail' / 'Other'\n"
            "    3. Put THAT 16-character value as SMTP_PASSWORD in .env\n"
            "       (not your real Gmail password)\n"
        )
    except Exception as e:
        print(f"\n❌ FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
