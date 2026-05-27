from flask import Flask, request
import requests
import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

TOKEN = os.environ.get("BOT_TOKEN")
PRIVATE_CALENDAR_ID = os.environ.get("PRIVATE_CALENDAR_ID")
TZ = ZoneInfo("Asia/Seoul")

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

VIEW_OPTIONS = [
    ["🌤 Today", "🌙 Tomorrow"],
    ["📆 This week", "💫 All upcoming chaos"],
    ["⬅️ Back"]
]

CATEGORY_MESSAGES = {
    "💼 Agency": "Don’t be late. They’re paying you.",
    "📈 Business": "Future millionaire behavior.",
    "✨ Creative": "Time to make something unnecessarily iconic.",
    "🎀 Fun / Hobby": "You built this life for yourself. Go have fun baby.",
    "🧠 Adulting": "Adulting is slay baby."
}

def send_message(chat_id, text, keyboard=None, inline_keyboard=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    if keyboard:
        payload["reply_markup"] = {
            "keyboard": keyboard,
            "resize_keyboard": True
        }

    if inline_keyboard:
        payload["reply_markup"] = {
            "inline_keyboard": inline_keyboard
        }

    requests.post(url, json=payload)

def answer_callback(callback_id, text="Done ✨"):
    url = f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery"
    requests.post(url, json={
        "callback_query_id": callback_id,
        "text": text
    })

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
    today = datetime.now(TZ)

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
        next_day = (
            datetime.strptime(plan["date"], "%Y-%m-%d")
            + timedelta(days=1)
        ).strftime("%Y-%m-%d")

        event = {
            "summary": title,
            "description": "Created by Planner Boy ✨",
            "start": {"date": plan["date"]},
            "end": {"date": next_day},
            "extendedProperties": {
                "private": {"completed": "false"}
            }
        }

    else:
        start_time = f"{plan['date']}T{plan['time']}:00"
        end_dt = (
            datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S")
            + timedelta(hours=1)
        )

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
            },
            "extendedProperties": {
                "private": {"completed": "false"}
            }
        }

    service.events().insert(
        calendarId=PRIVATE_CALENDAR_ID,
        body=event
    ).execute()

def get_period_range(period):
    now = datetime.now(TZ)

    if period == "🌤 Today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

    elif period == "🌙 Tomorrow":
        start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

    elif period == "📆 This week":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)

    else:
        start = now - timedelta(days=1)
        end = now + timedelta(days=365)

    return start, end

def get_events_for_period(period):
    service = get_calendar_service()
    start, end = get_period_range(period)

    events_result = service.events().list(
        calendarId=PRIVATE_CALENDAR_ID,
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    return events_result.get("items", [])

def is_completed(event):
    return (
        event.get("extendedProperties", {})
        .get("private", {})
        .get("completed", "false")
        == "true"
    )

def format_event_time(event):
    start = event["start"].get("dateTime", event["start"].get("date"))

    try:
        dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        return dt.strftime("%H:%M")
    except:
        return "No exact time"

def show_schedule(chat_id, period):
    try:
        events = get_events_for_period(period)

        if not events:
            send_message(chat_id, "No chaos scheduled yet.", MAIN_MENU)
            return

        active = []
        completed = []
        inline_buttons = []

        for event in events:
            title = event.get("summary", "Unnamed quest")
            time = format_event_time(event)
            event_id = event["id"]

            if is_completed(event):
                completed.append(f"☑ {time} — {title}")
            else:
                active.append(f"☐ {time} — {title}")
                inline_buttons.append([{
                    "text": f"☐ {time} — {title[:30]}",
                    "callback_data": f"done|{event_id}"
                }])

        message = f"{period}\n\n"

        if active:
            message += "TO DO:\n"
            message += "\n".join(active)
            message += "\n\n"

        if completed:
            message += "DONE:\n"
            message += "\n".join(completed)
            message += "\n\n"

        message += "Your chaos is being documented."

        send_message(
            chat_id,
            message,
            inline_keyboard=inline_buttons if inline_buttons else None
        )

    except Exception as e:
        send_message(
            chat_id,
            f"Schedule error:\n{type(e).__name__}: {str(e)}",
            MAIN_MENU
        )

def mark_event_done(event_id):
    service = get_calendar_service()

    service.events().patch(
        calendarId=PRIVATE_CALENDAR_ID,
        eventId=event_id,
        body={
            "extendedProperties": {
                "private": {
                    "completed": "true"
                }
            }
        }
    ).execute()

@app.route("/")
def home():
    return "Planner Boy is alive ✨"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if "callback_query" in data:
        callback = data["callback_query"]
        chat_id = callback["message"]["chat"]["id"]
        callback_id = callback["id"]
        callback_data = callback["data"]

        if callback_data.startswith("done|"):
            event_id = callback_data.split("|", 1)[1]

            try:
                mark_event_done(event_id)
                answer_callback(callback_id, "Task completed. Iconic.")
                send_message(
                    chat_id,
                    "☑ Done.\n\nProductive behavior detected.",
                    MAIN_MENU
                )
            except Exception as e:
                answer_callback(callback_id, "Error")
                send_message(
                    chat_id,
                    f"Checkbox error:\n{type(e).__name__}: {str(e)}",
                    MAIN_MENU
                )

        return "ok"

    if "message" not in data:
        return "ok"

    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "")

    if text == "/start":
        user_state[chat_id] = {}
        send_message(
            chat_id,
            "✨ Planner Boy ✨\n\nFine. Let’s pretend we have our life together.",
            MAIN_MENU
        )

    elif text == "➕ Add plan":
        user_state[chat_id] = {"mode": "choose_timeframe"}
        send_message(chat_id, "Choose timeframe:", TIMEFRAME_OPTIONS)

    elif (
        text in ["🌤 Today", "🌙 Tomorrow", "📆 This week", "💫 Next week"]
        and user_state.get(chat_id, {}).get("mode") == "choose_timeframe"
    ):
        user_state[chat_id] = {
            "mode": "choose_time",
            "timeframe": text,
            "date": get_plan_date(text)
        }
        send_message(chat_id, "Choose time:", TIME_OPTIONS)

    elif (
        text in ["09:00", "12:00", "15:00", "18:00", "21:00", "No exact time"]
        and user_state.get(chat_id, {}).get("mode") == "choose_time"
    ):
        user_state[chat_id]["mode"] = "choose_category"
        user_state[chat_id]["time"] = text
        send_message(chat_id, "Choose life mode:", CATEGORY_OPTIONS)

    elif (
        text in CATEGORY_MESSAGES
        and user_state.get(chat_id, {}).get("mode") == "choose_category"
    ):
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
        send_message(chat_id, "Choose schedule:", VIEW_OPTIONS)

    elif text in ["🌤 Today", "🌙 Tomorrow", "📆 This week", "💫 All upcoming chaos"]:
        show_schedule(chat_id, text)

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
        send_message(
            chat_id,
            "I didn’t get that. Very mysterious. Use the buttons.",
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
