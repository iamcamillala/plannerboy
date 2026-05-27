from flask import Flask, request
import requests, os, json, re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

TOKEN = os.environ.get("BOT_TOKEN")
CALENDAR_ID = os.environ.get("PRIVATE_CALENDAR_ID")
TZ = ZoneInfo("Asia/Seoul")

app = Flask(__name__)
user_state = {}

MAIN_MENU = [["➕ Add plan"], ["📅 View schedule"], ["✨ Today's vibe"]]
DAY_OPTIONS = [["🌤 Today", "🌙 Tomorrow"], ["📆 This week", "💫 Next week"], ["⬅️ Back"]]
HOUR_OPTIONS = [["1","2","3"],["4","5","6"],["7","8","9"],["10","11","12"],["⬅️ Back"]]
MINUTE_OPTIONS = [["00","05","10"],["15","20","25"],["30","35","40"],["45","50","55"],["⬅️ Back"]]
AMPM_OPTIONS = [["AM","PM"],["⬅️ Back"]]
DURATION_OPTIONS = [["30 min","1 hour"],["1.5 hours","2 hours"],["3 hours","✏️ Custom duration"],["⬅️ Back"]]
CATEGORY_OPTIONS = [["💼 Agency","📈 Business"],["✨ Creative","🎀 Fun / Hobby"],["🧠 Adulting"],["⬅️ Back"]]
VIEW_OPTIONS = [["🌤 Today","🌙 Tomorrow"],["📆 This week","💫 All upcoming chaos"],["⬅️ Back"]]

CATEGORY_MESSAGES = {
    "💼 Agency": "Don’t be late. They’re paying you.",
    "📈 Business": "Future millionaire behavior.",
    "✨ Creative": "Time to make something unnecessarily iconic.",
    "🎀 Fun / Hobby": "You built this life for yourself. Go have fun baby.",
    "🧠 Adulting": "Adulting is slay baby."
}

def send_message(chat_id, text, keyboard=None, inline_keyboard=None):
    payload = {"chat_id": chat_id, "text": text}
    if keyboard:
        payload["reply_markup"] = {"keyboard": keyboard, "resize_keyboard": True}
    if inline_keyboard:
        payload["reply_markup"] = {"inline_keyboard": inline_keyboard}
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json=payload)

def answer_callback(callback_id, text="Done ✨"):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery",
                  json={"callback_query_id": callback_id, "text": text})

def calendar():
    creds = Credentials.from_service_account_info(
        json.loads(os.environ.get("GOOGLE_CREDENTIALS")),
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    return build("calendar", "v3", credentials=creds)

def day_to_date(day):
    now = datetime.now(TZ)
    if day == "🌤 Today": return now.date()
    if day == "🌙 Tomorrow": return (now + timedelta(days=1)).date()
    if day == "📆 This week": return now.date()
    if day == "💫 Next week": return (now + timedelta(days=7)).date()
    return now.date()

def parse_duration(text):
    t = text.lower().strip()
    if t == "30 min": return 30
    if t == "1 hour": return 60
    if t == "1.5 hours": return 90
    if t == "2 hours": return 120
    if t == "3 hours": return 180

    nums = re.findall(r"\d+", t)
    if "h" in t or "hour" in t:
        hours = int(nums[0]) if nums else 0
        mins = int(nums[1]) if len(nums) > 1 else 0
        return hours * 60 + mins

    if len(nums) == 2:
        return int(nums[0]) * 60 + int(nums[1])
    if len(nums) == 1:
        return int(nums[0])
    return None

def build_start_datetime(state):
    hour = int(state["hour"])
    minute = int(state["minute"])
    if state["ampm"] == "PM" and hour != 12: hour += 12
    if state["ampm"] == "AM" and hour == 12: hour = 0
    d = day_to_date(state["day"])
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=TZ)

def create_event(state, task):
    start = build_start_datetime(state)
    duration = state.get("duration", 60)
    end = start + timedelta(minutes=duration)

    event = {
        "summary": f"{state['category']} {task}",
        "description": "Created by Planner Boy ✨",
        "start": {"dateTime": start.isoformat(), "timeZone": "Asia/Seoul"},
        "end": {"dateTime": end.isoformat(), "timeZone": "Asia/Seoul"},
        "extendedProperties": {"private": {"completed": "false"}}
    }
    calendar().events().insert(calendarId=CALENDAR_ID, body=event).execute()

def get_range(period):
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

def get_events(period):
    start, end = get_range(period)
    result = calendar().events().list(
        calendarId=CALENDAR_ID,
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    return result.get("items", [])

def completed(event):
    return event.get("extendedProperties", {}).get("private", {}).get("completed") == "true"

def event_time(event):
    start = event["start"].get("dateTime", event["start"].get("date"))
    try:
        return datetime.fromisoformat(start).strftime("%H:%M")
    except:
        return "No time"

def show_schedule(chat_id, period):
    try:
        events = get_events(period)
        if not events:
            send_message(chat_id, "No chaos scheduled yet.", MAIN_MENU)
            return

        todo, done, buttons = [], [], []

        for e in events:
            title = e.get("summary", "Unnamed quest")
            time = event_time(e)
            eid = e["id"]

            if completed(e):
                done.append(f"☑ {time} — {title}")
            else:
                todo.append(f"☐ {time} — {title}")
                buttons.append([
                    {"text": f"☑ Done", "callback_data": f"done|{eid}"},
                    {"text": f"✏️ Edit", "callback_data": f"edit|{eid}"},
                    {"text": f"🗑 Delete", "callback_data": f"del|{eid}"}
                ])

        msg = f"{period}\n\n"
        if todo: msg += "TO DO:\n" + "\n".join(todo) + "\n\n"
        if done: msg += "DONE:\n" + "\n".join(done) + "\n\n"
        msg += "Your chaos is being documented."

        send_message(chat_id, msg, inline_keyboard=buttons if buttons else None)

    except Exception as e:
        send_message(chat_id, f"Schedule error:\n{type(e).__name__}: {e}", MAIN_MENU)

def mark_done(event_id):
    calendar().events().patch(
        calendarId=CALENDAR_ID,
        eventId=event_id,
        body={"extendedProperties": {"private": {"completed": "true"}}}
    ).execute()

def delete_event(event_id):
    calendar().events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()

@app.route("/")
def home():
    return "Planner Boy is alive ✨"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if "callback_query" in data:
        cb = data["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        callback_id = cb["id"]
        action, eid = cb["data"].split("|", 1)

        try:
            if action == "done":
                mark_done(eid)
                answer_callback(callback_id, "Task completed. Iconic.")
                send_message(chat_id, "☑ Done.\n\nProductive behavior detected.", MAIN_MENU)

            elif action == "del":
                delete_event(eid)
                answer_callback(callback_id, "Deleted.")
                send_message(chat_id, "🗑 Deleted.\n\nChaos removed from the timeline.", MAIN_MENU)

            elif action == "edit":
                user_state[chat_id] = {"mode": "edit_name", "event_id": eid}
                answer_callback(callback_id, "Edit mode")
                send_message(chat_id, "Type the new task name:")

        except Exception as e:
            send_message(chat_id, f"Action error:\n{type(e).__name__}: {e}", MAIN_MENU)

        return "ok"

    if "message" not in data:
        return "ok"

    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "")

    if text == "/start":
        user_state[chat_id] = {}
        send_message(chat_id, "✨ Planner Boy ✨\n\nFine. Let’s pretend we have our life together.", MAIN_MENU)

    elif text == "➕ Add plan":
        user_state[chat_id] = {"mode": "day"}
        send_message(chat_id, "Choose day:", DAY_OPTIONS)

    elif text in DAY_OPTIONS[0] + DAY_OPTIONS[1] and user_state.get(chat_id, {}).get("mode") == "day":
        user_state[chat_id]["day"] = text
        user_state[chat_id]["mode"] = "hour"
        send_message(chat_id, "Choose hour:", HOUR_OPTIONS)

    elif text in [str(i) for i in range(1, 13)] and user_state.get(chat_id, {}).get("mode") == "hour":
        user_state[chat_id]["hour"] = text
        user_state[chat_id]["mode"] = "minute"
        send_message(chat_id, "Choose minutes:", MINUTE_OPTIONS)

    elif text in ["00","05","10","15","20","25","30","35","40","45","50","55"] and user_state.get(chat_id, {}).get("mode") == "minute":
        user_state[chat_id]["minute"] = text
        user_state[chat_id]["mode"] = "ampm"
        send_message(chat_id, "AM or PM?", AMPM_OPTIONS)

    elif text in ["AM", "PM"] and user_state.get(chat_id, {}).get("mode") == "ampm":
        user_state[chat_id]["ampm"] = text
        user_state[chat_id]["mode"] = "duration"
        send_message(chat_id, "How long will it take?", DURATION_OPTIONS)

    elif user_state.get(chat_id, {}).get("mode") == "duration":
        if text == "✏️ Custom duration":
            send_message(chat_id, "Type duration like:\n2 30\n90\n2h 30m")
            return "ok"

        duration = parse_duration(text)
        if not duration:
            send_message(chat_id, "I didn’t understand duration. Try: 2 30 or 90.")
            return "ok"

        user_state[chat_id]["duration"] = duration
        user_state[chat_id]["mode"] = "category"
        send_message(chat_id, "Choose life mode:", CATEGORY_OPTIONS)

    elif text in CATEGORY_MESSAGES and user_state.get(chat_id, {}).get("mode") == "category":
        user_state[chat_id]["category"] = text
        user_state[chat_id]["mode"] = "task"
        send_message(chat_id, f"{CATEGORY_MESSAGES[text]}\n\nNow type the task name:")

    elif user_state.get(chat_id, {}).get("mode") == "task":
        try:
            create_event(user_state[chat_id], text)
            user_state[chat_id] = {}
            send_message(chat_id, f"✨ QUEST SAVED ✨\n\n{text}\n\nYour chaos has been scheduled.", MAIN_MENU)
        except Exception as e:
            send_message(chat_id, f"Calendar error:\n{type(e).__name__}: {e}", MAIN_MENU)

    elif user_state.get(chat_id, {}).get("mode") == "edit_name":
        try:
            eid = user_state[chat_id]["event_id"]
            event = calendar().events().get(calendarId=CALENDAR_ID, eventId=eid).execute()
            old = event.get("summary", "")
            prefix = old.split(" ", 1)[0] if old else "✨"
            event["summary"] = f"{prefix} {text}"
            calendar().events().update(calendarId=CALENDAR_ID, eventId=eid, body=event).execute()
            user_state[chat_id] = {}
            send_message(chat_id, "✏️ Edited.\n\nThe timeline has been adjusted.", MAIN_MENU)
        except Exception as e:
            send_message(chat_id, f"Edit error:\n{type(e).__name__}: {e}", MAIN_MENU)

    elif text == "📅 View schedule":
        send_message(chat_id, "Choose schedule:", VIEW_OPTIONS)

    elif text in ["🌤 Today", "🌙 Tomorrow", "📆 This week", "💫 All upcoming chaos"]:
        show_schedule(chat_id, text)

    elif text == "✨ Today's vibe":
        send_message(chat_id, "SYSTEM STATUS:\n\n☕ caffeinated\n🧠 mentally everywhere\n✨ still iconic", MAIN_MENU)

    elif text == "⬅️ Back":
        user_state[chat_id] = {}
        send_message(chat_id, "Main menu:", MAIN_MENU)

    else:
        send_message(chat_id, "I didn’t get that. Very mysterious. Use the buttons.", MAIN_MENU)

    return "ok"

@app.route("/set_webhook")
def set_webhook():
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url=https://plannerboy.onrender.com/webhook"
    return requests.get(url).text

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
