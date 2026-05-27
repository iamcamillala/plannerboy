from flask import Flask, request
import requests
import os
from datetime import datetime, timedelta

TOKEN = os.environ.get("BOT_TOKEN")

app = Flask(__name__)

user_state = {}
plans = []

MAIN_MENU = [
    ["➕ Add plan"],
    ["📅 View schedule"],
    ["✨ Today's vibe"]
]

TIMEFRAME_OPTIONS = [
    ["🌤 Today", "🌙 Tomorrow"],
    ["📆 This week", "💫 Next week"],
    ["⬅️ Back"]
]

TIME_OPTIONS = [
    ["09:00", "12:00", "15:00"],
    ["18:00", "21:00", "No exact time"],
    ["⬅️ Back"]
]

SCHEDULE_OPTIONS = [
    ["🌤 Today", "🌙 Tomorrow"],
    ["📆 All plans"],
    ["⬅️ Back"]
]

def send_message(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    if keyboard:
        payload["reply_markup"] = {
            "keyboard": keyboard,
            "resize_keyboard": True
        }

    requests.post(url, json=payload)

def get_plan_date(timeframe):
    today = datetime.now()

    if timeframe == "🌤 Today":
        return today.strftime("%Y-%m-%d")

    if timeframe == "🌙 Tomorrow":
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")

    if timeframe == "📆 This week":
        return "This week"

    if timeframe == "💫 Next week":
        return "Next week"

    return "No date"

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
            "✨ Planner Boy ✨\n\nFine. Let’s pretend we have our life together.",
            MAIN_MENU
        )

    elif text == "➕ Add plan":
        user_state[chat_id] = {"mode": "choose_timeframe"}
        send_message(chat_id, "Choose timeframe:", TIMEFRAME_OPTIONS)

    elif text in ["🌤 Today", "🌙 Tomorrow", "📆 This week", "💫 Next week"] and user_state.get(chat_id, {}).get("mode") == "choose_timeframe":
        user_state[chat_id] = {
            "mode": "choose_time",
            "timeframe": text,
            "date": get_plan_date(text)
        }
        send_message(chat_id, "Choose time:", TIME_OPTIONS)

    elif text in ["09:00", "12:00", "15:00", "18:00", "21:00", "No exact time"] and user_state.get(chat_id, {}).get("mode") == "choose_time":
        user_state[chat_id]["mode"] = "enter_task"
        user_state[chat_id]["time"] = text
        send_message(chat_id, "Now type the task name:")

    elif user_state.get(chat_id, {}).get("mode") == "enter_task":
        state = user_state[chat_id]

        plan = {
            "date": state["date"],
            "timeframe": state["timeframe"],
            "time": state["time"],
            "task": text
        }

        plans.append(plan)
        user_state[chat_id] = {}

        send_message(
            chat_id,
            f"✨ QUEST SAVED ✨\n\n{plan['date']} • {plan['time']}\n{plan['task']}\n\nYour chaos has been scheduled.",
            MAIN_MENU
        )

    elif text == "📅 View schedule":
        send_message(chat_id, "Choose schedule:", SCHEDULE_OPTIONS)

    elif text == "📆 All plans":
        if not plans:
            send_message(chat_id, "No plans yet. Suspiciously free.", MAIN_MENU)
        else:
            result = "📂 ALL PLANS\n\n"
            for plan in plans:
                result += f"• {plan['date']} • {plan['time']} — {plan['task']}\n"

            send_message(chat_id, result, MAIN_MENU)

    elif text == "✨ Today's vibe":
        send_message(
            chat_id,
            "SYSTEM STATUS:\n\n☕ caffeinated\n🧠 mentally everywhere\n✨ still iconic",
            MAIN_MENU
        )

    elif text == "⬅️ Back":
        user_state[chat_id] = {}
        send_message(chat_id, "Main menu:", MAIN_MENU)

    elif text == "🌤 Today":
        today = datetime.now().strftime("%Y-%m-%d")
        today_plans = [p for p in plans if p["date"] == today]

        if not today_plans:
            send_message(chat_id, "Today is empty. Suspicious, but glamorous.", MAIN_MENU)
        else:
            result = "🌤 TODAY\n\n"
            for plan in today_plans:
                result += f"• {plan['time']} — {plan['task']}\n"

            send_message(chat_id, result, MAIN_MENU)

    elif text == "🌙 Tomorrow":
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        tomorrow_plans = [p for p in plans if p["date"] == tomorrow]

        if not tomorrow_plans:
            send_message(chat_id, "Tomorrow is empty. Your future self is confused.", MAIN_MENU)
        else:
            result = "🌙 TOMORROW\n\n"
            for plan in tomorrow_plans:
                result += f"• {plan['time']} — {plan['task']}\n"

            send_message(chat_id, result, MAIN_MENU)

    else:
        send_message(chat_id, "I didn’t get that. Very mysterious. Use the buttons.", MAIN_MENU)

    return "ok"

@app.route("/set_webhook")
def set_webhook():
    webhook_url = "https://plannerboy.onrender.com/webhook"
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}"
    response = requests.get(url)
    return response.text
