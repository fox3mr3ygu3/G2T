import os
import time
import base64
import requests
import html
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Load environment
load_dotenv()
TELEGRAM_TOKEN = os.getenv("token")
CHAT_ID = os.getenv("chat_id")
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def send_to_telegram(subject, sender, body):
    subject = html.escape(subject)
    sender = html.escape(sender)
    body = html.escape(body[:4000])  # Telegram limit

    message = f"<b>📩 New Email</b>\nFrom: {sender}\nSubject: {subject}\n\n{body}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    response = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    })

    if response.ok:
        print("✅ Message sent to Telegram")
    else:
        print(f"❌ Failed to send to Telegram: {response.text}")

def get_gmail_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def fetch_unread_emails():
    print("🔍 Checking for new emails...")
    service = get_gmail_service()
    result = service.users().messages().list(userId='me', labelIds=['INBOX'], q='is:unread').execute()
    messages = result.get('messages', [])

    if not messages:
        print("📭 No new messages.")
        return

    print(f"📨 Found {len(messages)} new email(s).")

    for msg in messages:
        full_msg = service.users().messages().get(userId='me', id=msg['id']).execute()
        headers = full_msg['payload']['headers']
        subject = sender = ''
        for h in headers:
            if h['name'] == 'Subject':
                subject = h['value']
            if h['name'] == 'From':
                sender = h['value']

        try:
            body_data = full_msg['payload']['parts'][0]['body']['data']
        except:
            body_data = full_msg['payload']['body'].get('data', '')
        decoded_body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
        soup = BeautifulSoup(decoded_body, "html.parser")
        body = soup.get_text(separator="\n")
        body = '\n'.join([line.strip() for line in body.splitlines() if line.strip()])  # clean lines

        print(f"📤 Forwarding email: {subject} from {sender}")
        send_to_telegram(subject, sender, body)

        for attempt in range(3):
            try:
                service.users().messages().modify(
                    userId='me',
                    id=msg['id'],
                    body={'removeLabelIds': ['UNREAD']}
                ).execute()
                print("✅ Marked as read.")
                break
            except Exception as e:
                print(f"⚠️ Error marking as read: {e}")
                time.sleep(2)

if __name__ == "__main__":
    print("🚀 Bot started. Sending test message to Telegram...")
    send_to_telegram("🤖 Bot Started", "System", "Gmail-to-Telegram bot is now running.")

    while True:
        fetch_unread_emails()
        time.sleep(60)  # check every minute
