from flask import Flask, request
import requests
import os

TOKEN = os.environ.get("BOT_TOKEN")

app = Flask(__name__)

MAIN_MENU = [
    ["➕ Add plan"],
    ["📅 View schedule"],
    ["✨ Today's vibe"]
]

TIME_OPTIONS = [
    ["🌤 Today", "🌙 Tomorrow"],
    ["📆 This week", "💫 Next week"],
    ["🗓 Pick a date"],
    ["⬅️ Back"]
]

def send_message(chat_id, text, keyboard=None):

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard:
        payload["reply_markup"] = {
            "keyboard": keyboard,
            "resize_keyboard": True
        }

    requests.post(url, json=payload)

@app.route("/")
def home():
    return "Planner Boy is alive ✨"

@app.route("/webhook", methods=["POST"])
def webhook():

    data = request.get_json()

    if "message" not in data:
        return "ok"

    chat_id = data["message"]["chat"]["id"]

    text = data["message"].get("text", "")

    if text == "/start":

        send_message(
            chat_id,
            "✨ Planner Boy ✨\n\nYour chaos is now aesthetically organized.",
            MAIN_MENU
        )

    elif text == "➕ Add plan":

        send_message(
            chat_id,
            "Choose timeframe:",
            TIME_OPTIONS
        )

    elif text == "📅 View schedule":

        send_message(
            chat_id,
            "📂 Schedule system coming soon.",
            MAIN_MENU
        )

    elif text == "✨ Today's vibe":

        send_message(
            chat_id,
            "SYSTEM STATUS:\n\n☕ caffeinated\n🧠 mentally everywhere\n✨ still iconic",
            MAIN_MENU
        )

    elif text == "⬅️ Back":

        send_message(
            chat_id,
            "Main menu:",
            MAIN_MENU
        )

    elif text in [
        "🌤 Today",
        "🌙 Tomorrow",
        "📆 This week",
        "💫 Next week",
        "🗓 Pick a date"
    ]:

        send_message(
            chat_id,
            f"✨ New quest added for:\n{text}",
            MAIN_MENU
        )

    return "ok"

@app.route("/set_webhook")
def set_webhook():

    webhook_url = "https://plannerboy.onrender.com/webhook"

    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}"

    response = requests.get(url)

    return response.text

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
