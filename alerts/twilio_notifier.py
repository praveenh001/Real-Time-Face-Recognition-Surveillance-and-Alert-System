import threading
from twilio.rest import Client
from config import settings

class TwilioNotifier:
    def __init__(self):
        self.sid = settings.TWILIO_ACCOUNT_SID
        self.token = settings.TWILIO_AUTH_TOKEN
        self.from_num = settings.TWILIO_FROM_NUMBER
        self.to_num = settings.TO_NUMBER
        
        # Validate configuration parameters
        self.is_configured = bool(
            self.sid and 
            self.token and 
            self.from_num and 
            self.to_num and
            "your_account_sid" not in self.sid and
            "your_twilio_number" not in self.from_num
        )
        
        if not self.is_configured:
            print("[WARNING] Twilio credentials are not set up or are using placeholders in the .env file.")
            print("[WARNING] Alerts will be simulated in the terminal output. Please configure your .env file to enable actual SMS.")

    def _send_sms_thread(self, message_body):
        try:
            client = Client(self.sid, self.token)
            message = client.messages.create(
                body=message_body,
                from_=self.from_num,
                to=self.to_num
            )
            print(f"[INFO] Twilio alert sent successfully. SID: {message.sid}")
        except Exception as e:
            print(f"[ERROR] Failed to send Twilio alert: {e}")

    def send_alert(self, timestamp_str, photo_name):
        message_body = (
            f"⚠️ SECURITY ALERT: An unknown person was detected at {timestamp_str}.\n"
            f"Photo captured and saved as: {photo_name}"
        )
        
        if not self.is_configured:
            print(f"\n--- [SIMULATED SMS ALERT] ---\nTo: {self.to_num}\nBody: {message_body}\n-----------------------------\n")
            return
            
        print(f"[INFO] Dispatching Twilio alert thread...")
        thread = threading.Thread(target=self._send_sms_thread, args=(message_body,))
        thread.daemon = True
        thread.start()
        print("[INFO] Twilio thread dispatched.")
        
# Initialize single instance
notifier = TwilioNotifier()
