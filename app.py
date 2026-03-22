import os
import logging
import requests
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv

load_dotenv()

# setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

app = Flask(__name__)

BLYNK_TOKEN   = os.getenv("BLYNK_AUTH_TOKEN")
TWILIO_SID    = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN")
HOD_NUMBER    = os.getenv("HOD_WHATSAPP_NUMBER")
BLYNK_URL     = "https://blynk.cloud/external/api/update"

log.info("=== Smart Notice Board Bot Starting ===")
log.info(f"BLYNK_TOKEN   : {'SET' if BLYNK_TOKEN  else 'MISSING'}")
log.info(f"TWILIO_SID    : {'SET' if TWILIO_SID   else 'MISSING'}")
log.info(f"TWILIO_TOKEN  : {'SET' if TWILIO_TOKEN else 'MISSING'}")
log.info(f"HOD_NUMBER    : {HOD_NUMBER if HOD_NUMBER else 'MISSING'}")

try:
    twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)
    log.info("Twilio client initialized OK")
except Exception as e:
    log.error(f"Twilio client failed: {e}")
    twilio_client = None

# ---------- helpers ----------

def blynk_set(pin, value):
    url = f"{BLYNK_URL}?token={BLYNK_TOKEN}&{pin}={value}"
    log.debug(f"Blynk request → {url}")
    try:
        r = requests.get(url, timeout=5)
        log.info(f"Blynk response [{pin}={value}] → status {r.status_code} | body: {r.text}")
        return r.status_code == 200
    except requests.exceptions.Timeout:
        log.error(f"Blynk request timed out for {pin}={value}")
        return False
    except requests.exceptions.ConnectionError:
        log.error(f"Blynk connection error for {pin}={value}")
        return False
    except Exception as e:
        log.error(f"Blynk unexpected error: {e}")
        return False

def send_reply(to, body):
    log.info(f"Sending WhatsApp reply to {to}: {body}")
    try:
        twilio_client.messages.create(
            from_="whatsapp:+14155238886",
            to=to,
            body=body
        )
        log.info("WhatsApp reply sent OK")
    except Exception as e:
        log.error(f"WhatsApp reply failed: {e}")

# ---------- command parser ----------

def handle_command(sender, text):
    log.info(f"Handling command from {sender}: '{text}'")
    low = text.lower().strip()

    if low.startswith("msg:"):
        msg = text[4:].strip()
        log.debug(f"Command: msg → '{msg}'")
        if not msg:
            return "Please provide a message.\nExample: msg: I am busy now"
        ok = blynk_set("V0", msg)
        return f"Done! Displaying:\n\"{msg}\"" if ok else "Error updating display. Is ESP32 online?"

    elif low.startswith("speed:"):
        try:
            val = constrain(int(text[6:].strip()), 1, 10)
            log.debug(f"Command: speed → {val}")
            blynk_set("V1", val)
            return f"Speed set to {val}/10"
        except ValueError:
            return "Invalid speed. Use 1-10.\nExample: speed: 6"

    elif low.startswith("bright:"):
        try:
            val = constrain(int(text[7:].strip()), 1, 15)
            log.debug(f"Command: bright → {val}")
            blynk_set("V2", val)
            return f"Brightness set to {val}/15"
        except ValueError:
            return "Invalid brightness. Use 1-15.\nExample: bright: 10"

    elif low.startswith("dir:"):
        d = text[4:].strip().lower()
        mapping = {"left": 0, "right": 1, "pause": 2}
        log.debug(f"Command: dir → {d}")
        if d not in mapping:
            return "Invalid direction.\nUse: dir: left, dir: right, or dir: pause"
        blynk_set("V3", mapping[d])
        return f"Direction set to {d}"

    elif low == "1":
        blynk_set("V0", "Class cancelled today")
        return "Preset 1: \"Class cancelled today\""

    elif low == "2":
        blynk_set("V0", "Meeting in progress - Do not disturb")
        return "Preset 2: \"Meeting in progress\""

    elif low == "3":
        blynk_set("V0", "Back in 10 minutes")
        return "Preset 3: \"Back in 10 minutes\""

    elif low == "4":
        blynk_set("V0", "Please wait outside")
        return "Preset 4: \"Please wait outside\""

    elif low == "off":
        blynk_set("V2", 0)
        return "Display turned off"

    elif low == "on":
        blynk_set("V2", 8)
        return "Display turned on"

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
        log.warning(f"Unknown command: '{text}'")
        return "Unknown command. Type *help* to see all commands."

def constrain(val, min_val, max_val):
    return max(min_val, min(max_val, val))

# ---------- routes ----------

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    log.info("=== Incoming WhatsApp webhook ===")
    log.debug(f"Form data: {dict(request.form)}")

    sender = request.form.get("From", "")
    body   = request.form.get("Body", "").strip()

    log.info(f"From   : {sender}")
    log.info(f"Message: {body}")
    log.info(f"HOD    : {HOD_NUMBER}")

    if sender != HOD_NUMBER:
        log.warning(f"Unauthorized sender: {sender}")
        resp = MessagingResponse()
        resp.message("Unauthorized. Only the HOD can control this board.")
        return str(resp)

    log.info("Sender authorized OK")
    reply = handle_command(sender, body)
    log.info(f"Reply: {reply}")
    send_reply(sender, reply)

    resp = MessagingResponse()
    return str(resp)

@app.route("/", methods=["GET"])
def index():
    log.info("Health check ping received")
    return "Smart Notice Board Bot is running!", 200

@app.route("/test-blynk", methods=["GET"])
def test_blynk():
    log.info("Testing Blynk connection...")
    ok = blynk_set("V0", "Test from server!")
    return f"Blynk test: {'OK' : 'FAILED'}", 200

# keep alive
import threading, time
def keep_alive():
    time.sleep(60)
    while True:
        try:
            url = os.getenv("RENDER_URL", "http://localhost:5000")
            requests.get(url)
            log.debug("Keep-alive ping sent")
        except:
            pass
        time.sleep(600)

threading.Thread(target=keep_alive, daemon=True).start()

if __name__ == "__main__":
    log.info("Starting Flask server on port 5000...")
    app.run(debug=True, port=5000)
