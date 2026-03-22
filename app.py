from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

BLYNK_TOKEN    = os.getenv("BLYNK_AUTH_TOKEN")
TWILIO_SID     = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN")
HOD_NUMBER     = os.getenv("HOD_WHATSAPP_NUMBER")
BLYNK_BASE_URL = "https://blynk.cloud/external/api/update"

twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)

# ---------- Blynk helpers ----------

def blynk_set(pin, value):
    url = f"{BLYNK_BASE_URL}?token={BLYNK_TOKEN}&{pin}={value}"
    r = requests.get(url, timeout=5)
    return r.status_code == 200

def send_reply(to, body):
    twilio_client.messages.create(
        from_="whatsapp:+14155238886",  # Twilio sandbox number
        to=to,
        body=body
    )

# ---------- Command parser ----------

def handle_message(sender, text):
    text = text.strip()
    low  = text.lower()

    # ---- msg: Hello I am busy ----
    if low.startswith("msg:"):
        msg = text[4:].strip()
        if not msg:
            return "Please provide a message. Example:\nmsg: I am busy now"
        ok = blynk_set("V0", msg)
        return f"Done! Displaying:\n\"{msg}\"" if ok else "Error updating display. Check device."

    # ---- speed: 5 ----
    elif low.startswith("speed:"):
        try:
            val = int(text[6:].strip())
            val = max(1, min(10, val))
            blynk_set("V1", val)
            return f"Speed set to {val}/10"
        except ValueError:
            return "Invalid speed. Use 1-10.\nExample: speed: 6"

    # ---- bright: 10 ----
    elif low.startswith("bright:"):
        try:
            val = int(text[7:].strip())
            val = max(1, min(15, val))
            blynk_set("V2", val)
            return f"Brightness set to {val}/15"
        except ValueError:
            return "Invalid brightness. Use 1-15.\nExample: bright: 10"

    # ---- dir: left / right / pause ----
    elif low.startswith("dir:"):
        d = text[4:].strip().lower()
        mapping = {"left": 0, "right": 1, "pause": 2}
        if d not in mapping:
            return "Invalid direction.\nUse: dir: left, dir: right, or dir: pause"
        blynk_set("V3", mapping[d])
        return f"Direction set to {d}"

    # ---- preset shortcuts ----
    elif low == "1":
        blynk_set("V0", "Class cancelled today")
        return "Preset 1: \"Class cancelled today\""

    elif low == "2":
        blynk_set("V0", "Meeting in progress - Do not disturb")
        return "Preset 2: \"Meeting in progress - Do not disturb\""

    elif low == "3":
        blynk_set("V0", "Back in 10 minutes")
        return "Preset 3: \"Back in 10 minutes\""

    elif low == "4":
        blynk_set("V0", "Please wait outside")
        return "Preset 4: \"Please wait outside\""

    # ---- off ----
    elif low == "off":
        blynk_set("V2", 0)
        return "Display turned off"

    # ---- on ----
    elif low == "on":
        blynk_set("V2", 8)
        return "Display turned on"

    # ---- help ----
    elif low == "help":
        return (
            "Smart Notice Board Commands:\n\n"
            "msg: your message\n"
            "speed: 1-10\n"
            "bright: 1-15\n"
            "dir: left / right / pause\n"
            "on / off\n\n"
            "Quick presets:\n"
            "1 - Class cancelled\n"
            "2 - Meeting in progress\n"
            "3 - Back in 10 minutes\n"
            "4 - Please wait outside"
        )

    else:
        return "Unknown command. Type *help* to see all commands."

# ---------- Webhook route ----------

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    sender = request.form.get("From", "")
    body   = request.form.get("Body", "").strip()

    print(f"[WhatsApp] From: {sender} | Message: {body}")

    # Security — only HOD can control the board
    if sender != HOD_NUMBER:
        resp = MessagingResponse()
        resp.message("Unauthorized. Only the HOD can control this board.")
        return str(resp)

    reply = handle_message(sender, body)
    send_reply(sender, reply)

    resp = MessagingResponse()
    return str(resp)

@app.route("/", methods=["GET"])
def index():
    return "Smart Notice Board Bot is running!"

if __name__ == "__main__":
    app.run(debug=True, port=5000)
