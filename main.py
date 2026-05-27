from flask import Flask, request
import requests
import os
import json
import re
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

TOKEN = os.environ.get("BOT_TOKEN")
CALENDAR_ID = os.environ.get("PRIVATE_CALENDAR_ID")
TZ = ZoneInfo("Asia/Seoul")

app = Flask(__name__)
user_state = {}
event_map = {}

MAIN_MENU = [["➕ Add plan"], ["📅 View schedule"], ["✨ Today's vibe"]]
DAY_OPTIONS = [["🌤 Today", "🌙 Tomorrow"], ["📆 This week", "💫 Next week"], ["⬅️ Back"]]
HOUR_OPTIONS = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], ["10", "11", "12"], ["⬅️ Back"]]
MINUTE_OPTIONS = [["00", "05", "10"], ["15", "20", "25"], ["30", "35", "40"], ["45", "50", "55"], ["⬅️ Back"]]
AMPM_OPTIONS = [["AM", "PM"], ["⬅️ Back"]]
DURATION_OPTIONS = [["30 min", "1 hour"], ["1.5 hours", "2 hours"], ["3 hours", "✏️ Custom duration"], ["⬅️ Back"]]
CATEGORY_OPTIONS = [["💼 Agency", "📈 Business"], ["✨ Creative", "🎀 Fun / Hobby"], ["🧠 Adulting"], ["⬅️ Back"]]
VIEW_OPTIONS = [["🌤 Today", "🌙 Tomorrow"], ["📆 This week", "💫 All upcoming chaos"], ["⬅️ Back"]]

CATEGORY_MESSAGES = {
    "💼 Agency": "Don’t be late. They’re paying you.",
    "📈 Business": "Future millionaire behavior.",
    "✨ Creative": "Time to make something unnecessarily iconic.",
    "🎀 Fun / Hobby": "You built this life for yourself. Go have fun baby.",
    "🧠 Adulting": "Adulting is slay baby."
}

CATEGORIES = list(CATEGORY_MESSAGES.keys())


def send_message(chat_id, text, keyboard=None, inline_keyboard=None):
    payload = {"chat_id": chat_id, "text": text}

    if keyboard:
        payload["reply_markup"] = {"keyboard": keyboard, "resize_keyboard": True}

    if inline_keyboard:
        payload["reply_markup"] = {"inline_keyboard": inline_keyboard}

    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json=payload)


def answer_callback(callback_id, text="Done ✨"):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery",
        json={"callback_query_id": callback_id, "text": text}
    )


def calendar():
    creds = Credentials.from_service_account_info(
        json.loads(os.environ.get("GOOGLE_CREDENTIALS")),
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    return build("calendar", "v3", credentials=creds)


def parse_duration(text):
    t = text.lower().strip()

    fixed = {
        "30 min": 30,
        "1 hour": 60,
        "1.5 hours": 90,
        "2 hours": 120,
        "3 hours": 180
    }

    if t in fixed:
        return fixed[t]

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


def day_to_date(day):
    now = datetime.now(TZ)

    if day == "🌤 Today":
        return now.date()
    if day == "🌙 Tomorrow":
        return (now + timedelta(days=1)).date()
    if day == "📆 This week":
        return now.date()
    if day == "💫 Next week":
        return (now + timedelta(days=7)).date()

    return now.date()


def build_start_datetime(state):
    hour = int(state["hour"])
    minute = int(state["minute"])

    if state["ampm"] == "PM" and hour != 12:
        hour += 12
    if state["ampm"] == "AM" and hour == 12:
        hour = 0

    d = day_to_date(state["day"])

    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=TZ)


def create_event(state, task):
    start = build_start_datetime(state)
    end = start + timedelta(minutes=state.get("duration", 60))

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


def is_completed(event):
    return event.get("extendedProperties", {}).get("private", {}).get("completed") == "true"


def event_time(event):
    start = event["start"].get("dateTime", event["start"].get("date"))

    try:
        dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        return dt.strftime("%b %d • %H:%M")
    except:
        return start


def remove_category(title):
    for cat in CATEGORIES:
        if title.startswith(cat):
            return title.replace(cat, "", 1).strip(), cat

    return title, "✨ Creative"


def make_short_event_id(event_id):
    short_id = str(uuid.uuid4())[:8]
    event_map[short_id] = event_id
    return short_id


def show_schedule(chat_id, period):
    try:
        events = get_events(period)

        if not events:
            send_message(chat_id, "No chaos scheduled yet.", MAIN_MENU)
            return

        todo = []
        done = []
        done_buttons = []
        task_buttons = []
        task_number = 1

        for event in events:
            title = event.get("summary", "Unnamed quest")
            time = event_time(event)
            event_id = event["id"]
            sid = make_short_event_id(event_id)

            if is_completed(event):
                done.append(f"{task_number}. ☑ {time}\n{title}")
            else:
                todo.append(f"{task_number}. ☐ {time}\n{title}")
                done_buttons.append({"text": f"✅ {task_number}", "callback_data": f"done|{sid}"})
                task_buttons.append({"text": f"⚙️ {task_number}", "callback_data": f"menu|{sid}"})

            task_number += 1

        msg = f"{period}\n\n"

        if todo:
            msg += "TO DO:\n\n" + "\n\n".join(todo) + "\n\n"

        if done:
            msg += "DONE:\n\n" + "\n\n".join(done) + "\n\n"

        msg += "Your chaos is being documented."

        keyboard = []
        if done_buttons:
            keyboard.append(done_buttons)
        if task_buttons:
            keyboard.append(task_buttons)

        send_message(chat_id, msg, inline_keyboard=keyboard if keyboard else None)

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


def get_event(event_id):
    return calendar().events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()


def update_event(event_id, event):
    calendar().events().update(calendarId=CALENDAR_ID, eventId=event_id, body=event).execute()


def update_event_name(event_id, new_name):
    event = get_event(event_id)
    old_title = event.get("summary", "")
    _, category = remove_category(old_title)
    event["summary"] = f"{category} {new_name}"
    update_event(event_id, event)


def update_event_date_time(event_id, state):
    event = get_event(event_id)
    new_start = build_start_datetime(state)
    new_end = new_start + timedelta(minutes=state.get("duration", 60))

    event["start"] = {"dateTime": new_start.isoformat(), "timeZone": "Asia/Seoul"}
    event["end"] = {"dateTime": new_end.isoformat(), "timeZone": "Asia/Seoul"}

    update_event(event_id, event)


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
        action, sid = cb["data"].split("|", 1)

        event_id = event_map.get(sid)

        if not event_id:
            answer_callback(callback_id, "Open schedule again.")
            send_message(chat_id, "This button expired. Open schedule again.", MAIN_MENU)
            return "ok"

        try:
            if action == "done":
                mark_done(event_id)
                answer_callback(callback_id, "Task completed. Iconic.")
                send_message(chat_id, "☑ Done.\n\nProductive behavior detected.", MAIN_MENU)

            elif action == "del":
                delete_event(event_id)
                answer_callback(callback_id, "Deleted.")
                send_message(chat_id, "🗑 Deleted.\n\nChaos removed from the timeline.", MAIN_MENU)

            elif action == "menu":
                answer_callback(callback_id, "Task menu")
                send_message(
                    chat_id,
                    "Task actions:",
                    inline_keyboard=[
                        [{"text": "✅ Done", "callback_data": f"done|{sid}"}],
                        [{"text": "✏️ Edit name", "callback_data": f"editname|{sid}"}],
                        [{"text": "🕒 Edit date/time/duration", "callback_data": f"editdatetime|{sid}"}],
                        [{"text": "🗑 Delete", "callback_data": f"del|{sid}"}]
                    ]
                )

            elif action == "editname":
                user_state[chat_id] = {"mode": "edit_name", "event_id": event_id}
                answer_callback(callback_id, "Name edit")
                send_message(chat_id, "Type the new task name:")

            elif action == "editdatetime":
                user_state[chat_id] = {"mode": "edit_day", "event_id": event_id}
                answer_callback(callback_id, "Date/time edit")
                send_message(chat_id, "Choose new day:", DAY_OPTIONS)

        except Exception as e:
            send_message(chat_id, f"Action error:\n{type(e).__name__}: {e}", MAIN_MENU)

        return "ok"

    if "message" not in data:
        return "ok"

    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "")
    state = user_state.get(chat_id, {})

    if text == "/start":
        user_state[chat_id] = {}
        send_message(chat_id, "✨ Planner Boy ✨\n\nFine. Let’s pretend we have our life together.", MAIN_MENU)

    elif text == "➕ Add plan":
        user_state[chat_id] = {"mode": "day"}
        send_message(chat_id, "Choose day:", DAY_OPTIONS)

    elif text in DAY_OPTIONS[0] + DAY_OPTIONS[1] and state.get("mode") in ["day", "edit_day"]:
        user_state[chat_id]["day"] = text

        if state.get("mode") == "edit_day":
            user_state[chat_id]["mode"] = "edit_hour"
            send_message(chat_id, "Choose new hour:", HOUR_OPTIONS)
        else:
            user_state[chat_id]["mode"] = "hour"
            send_message(chat_id, "Choose hour:", HOUR_OPTIONS)

    elif text in [str(i) for i in range(1, 13)] and state.get("mode") in ["hour", "edit_hour"]:
        user_state[chat_id]["hour"] = text

        if state.get("mode") == "edit_hour":
            user_state[chat_id]["mode"] = "edit_minute"
            send_message(chat_id, "Choose new minutes:", MINUTE_OPTIONS)
        else:
            user_state[chat_id]["mode"] = "minute"
            send_message(chat_id, "Choose minutes:", MINUTE_OPTIONS)

    elif text in ["00", "05", "10", "15", "20", "25", "30", "35", "40", "45", "50", "55"] and state.get("mode") in ["minute", "edit_minute"]:
        user_state[chat_id]["minute"] = text

        if state.get("mode") == "edit_minute":
            user_state[chat_id]["mode"] = "edit_ampm"
            send_message(chat_id, "AM or PM?", AMPM_OPTIONS)
        else:
            user_state[chat_id]["mode"] = "ampm"
            send_message(chat_id, "AM or PM?", AMPM_OPTIONS)

    elif text in ["AM", "PM"] and state.get("mode") in ["ampm", "edit_ampm"]:
        user_state[chat_id]["ampm"] = text

        if state.get("mode") == "edit_ampm":
            user_state[chat_id]["mode"] = "edit_duration"
            send_message(chat_id, "New duration?", DURATION_OPTIONS)
        else:
            user_state[chat_id]["mode"] = "duration"
            send_message(chat_id, "How long will it take?", DURATION_OPTIONS)

    elif state.get("mode") in ["duration", "edit_duration"]:
        if text == "✏️ Custom duration":
            send_message(chat_id, "Type duration like:\n2 30\n90\n2h 30m")
            return "ok"

        duration = parse_duration(text)

        if not duration:
            send_message(chat_id, "I didn’t understand duration. Try: 2 30 or 90.")
            return "ok"

        user_state[chat_id]["duration"] = duration

        if state.get("mode") == "edit_duration":
            try:
                update_event_date_time(state["event_id"], user_state[chat_id])
                user_state[chat_id] = {}
                send_message(chat_id, "🗓 Edited.\n\nThe timeline has been corrected.", MAIN_MENU)
            except Exception as e:
                send_message(chat_id, f"Date/time edit error:\n{type(e).__name__}: {e}", MAIN_MENU)
        else:
            user_state[chat_id]["mode"] = "category"
            send_message(chat_id, "Choose life mode:", CATEGORY_OPTIONS)

    elif text in CATEGORY_MESSAGES and state.get("mode") == "category":
        user_state[chat_id]["category"] = text
        user_state[chat_id]["mode"] = "task"
        send_message(chat_id, f"{CATEGORY_MESSAGES[text]}\n\nNow type the task name:")

    elif state.get("mode") == "task":
        try:
            create_event(user_state[chat_id], text)
            user_state[chat_id] = {}
            send_message(chat_id, f"✨ QUEST SAVED ✨\n\n{text}\n\nYour chaos has been scheduled.", MAIN_MENU)
        except Exception as e:
            send_message(chat_id, f"Calendar error:\n{type(e).__name__}: {e}", MAIN_MENU)

    elif state.get("mode") == "edit_name":
        try:
            update_event_name(state["event_id"], text)
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
