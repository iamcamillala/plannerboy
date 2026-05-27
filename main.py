from flask import Flask, request
import requests
import os
import json
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

TOKEN = os.environ.get("BOT_TOKEN")
PRIVATE_CALENDAR_ID = os.environ.get("PRIVATE_CALENDAR_ID")

app = Flask(__name__)

user_state = {}

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

CATEGORY_OPTIONS = [
    ["💼 Agency", "📈 Business"],
    ["✨ Creative", "🎀 Fun / Hobby"],
    ["🧠 Adulting"],
    ["⬅️ Back"]
]

SCHEDULE_OPTIONS = [
    ["🌤 Today", "🌙 Tomorrow"],
    ["📆 All plans"],
    ["⬅️ Back"]
]

CATEGORY_MESSAGES = {
    "💼 Agency": "Don’t be late. They’re paying you.",
    "📈 Business": "Future millionaire behavior.",
    "✨ Creative": "Time to make something unnecessarily iconic.",
    "🎀 Fun / Hobby": "You built this life for yourself. Go have fun baby.",
    "🧠 Adulting": "Adulting is slay baby."
}

def send_message(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    if keyboard:
        payload["reply_markup"] = {
            "keyboard": keyboard,
            "resize_keyboard": True
        }

    requests.post(url, json=payload)

def get_calendar_service():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    creds_dict = json.loads(creds_json)

    scopes = ["https://www.googleapis.com/auth/calendar"]

    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=scopes
    )

    return build("calendar", "v3", credentials=creds)

def get_plan_date(timeframe):
    today = datetime.now()

    if timeframe == "🌤 Today":
        return today.strftime("%Y-%m-%d")

    if timeframe == "🌙 Tomorrow":
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")

    if timeframe == "📆 This week":
        return today.strftime("%Y-%m-%d")

    if timeframe == "💫 Next week":
        return (today + timedelta(days=7)).strftime("%Y-%m-%d")

    return today.strftime("%Y-%m-%d")

def create_calendar_event(plan):
    service = get_calendar_service()

    title = f"{plan['category']} {plan['task']}"

    if plan["time"] == "No exact time":
        event = {
            "summary": title,
            "description": "Created by Planner Boy ✨",
            "start": {"date": plan["date"]},
            "end": {"date": plan["date"]}
        }
    else:
        start_time = f"{plan['date']}T{plan['time']}:00"
        end_dt = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S") + timedelta(hours=1)

        event = {
            "summary": title,
            "description": "Created by Planner Boy ✨",
            "start": {
                "dateTime": start_time,
                "timeZone": "Asia/Seoul"
            },
            "end": {
                "dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "Asia/Seoul"
            }
        }

    service.events().insert(
        calendarId=PRIVATE_CALENDAR_ID,
        body=event
    ).execute()

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
        user_state[chat_id]["mode"] = "choose_category"
        user_state[chat_id]["time"] = text
        send_message(chat_id, "Choose life mode:", CATEGORY_OPTIONS)

    elif text in CATEGORY_MESSAGES and user_state.get(chat_id, {}).get("mode") == "choose_category":
        user_state[chat_id]["mode"] = "enter_task"
        user_state[chat_id]["category"] = text

        send_message(
            chat_id,
            f"{CATEGORY_MESSAGES[text]}\n\nNow type the task name:"
        )

    elif user_state.get(chat_id, {}).get("mode") == "enter_task":
        state = user_state[chat_id]

        plan = {
            "date": state["date"],
            "timeframe": state["timeframe"],
            "time": state["time"],
            "category": state["category"],
            "task": text
        }

        try:
            create_calendar_event(plan)
            user_state[chat_id] = {}

            send_message(
                chat_id,
                f"✨ QUEST SAVED TO GOOGLE CALENDAR ✨\n\n{plan['category']}\n{plan['date']} • {plan['time']}\n{plan['task']}\n\nYour chaos has been scheduled.",
                MAIN_MENU
            )

        except Exception as e:
            send_message(
                chat_id,
                f"Calendar error:\n{type(e).__name__}: {str(e)}",
                MAIN_MENU
            )

    elif text == "📅 View schedule":
        send_message(chat_id, "Choose schedule:", SCHEDULE_OPTIONS)

    elif text == "✨ Today's vibe":
        send_message(
            chat_id,
            "SYSTEM STATUS:\n\n☕ caffeinated\n🧠 mentally everywhere\n✨ still iconic",
            MAIN_MENU
        )

    elif text == "⬅️ Back":
        user_state[chat_id] = {}
        send_message(chat_id, "Main menu:", MAIN_MENU)

    else:
        send_message(chat_id, "I didn’t get that. Very mysterious. Use the buttons.", MAIN_MENU)

    return "ok"

@app.route("/set_webhook")
def set_webhook():
    webhook_url = "https://plannerboy.onrender.com/webhook"
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}"
    response = requests.get(url)
    return response.text
