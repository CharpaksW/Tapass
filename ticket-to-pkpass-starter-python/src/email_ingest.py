# src/email_ingest.py
# Minimal IMAP fetcher: downloads the first PDF attachment from INBOX (latest first).
import email, imaplib, os, tempfile

def fetch_first_pdf(host, user, password, mailbox="INBOX"):
    imap = imaplib.IMAP4_SSL(host)
    imap.login(user, password)
    imap.select(mailbox)
    typ, data = imap.search(None, 'ALL')
    if typ != 'OK':
        imap.logout()
        return None

    for num in reversed(data[0].split()):  # latest first
        typ, msg_data = imap.fetch(num, '(RFC822)')
        if typ != 'OK':
            continue
        msg = email.message_from_bytes(msg_data[0][1])
        for part in msg.walk():
            cdisp = part.get("Content-Disposition", "")
            ctype = part.get_content_type()
            if "attachment" in (cdisp or "").lower() and ctype == "application/pdf":
                payload = part.get_payload(decode=True)
                fd, path = tempfile.mkstemp(suffix=".pdf")
                with os.fdopen(fd, "wb") as f:
                    f.write(payload)
                imap.logout()
                return path
    imap.logout()
    return None
