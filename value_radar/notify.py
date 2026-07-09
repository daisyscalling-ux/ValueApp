"""
notify.py — E-Mail-Benachrichtigung fuer den Nacht-Job (precompute.py).

Konfiguration ausschliesslich ueber Umgebungsvariablen (GitHub-Actions-Secrets):
    SMTP_HOST     z.B. smtp.gmail.com
    SMTP_PORT     z.B. 587   (STARTTLS)  oder 465 (SSL)
    SMTP_USER     Login / Absenderadresse
    SMTP_PASS     Passwort bzw. App-Passwort (bei Gmail: App-Passwort noetig!)
    EMAIL_TO      Empfaenger (kann = SMTP_USER sein)
    EMAIL_FROM    optional, sonst = SMTP_USER

Fehlt etwas oder schlaegt der Versand fehl, wird das geloggt, aber nichts crasht.
"""
from __future__ import annotations
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def configured() -> bool:
    return all(os.getenv(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "EMAIL_TO"))


def send_email(subject: str, html_body: str, text_body: str = "") -> bool:
    if not configured():
        print("[notify] E-Mail nicht konfiguriert (SMTP_* / EMAIL_TO fehlen) - uebersprungen.")
        return False
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")
    to = os.getenv("EMAIL_TO")
    sender = os.getenv("EMAIL_FROM") or user

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if port == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
                s.login(user, pwd)
                s.sendmail(sender, [to], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(user, pwd)
                s.sendmail(sender, [to], msg.as_string())
        print(f"[notify] E-Mail an {to} gesendet.")
        return True
    except Exception as e:
        print(f"[notify] E-Mail-Versand fehlgeschlagen: {e}")
        return False
