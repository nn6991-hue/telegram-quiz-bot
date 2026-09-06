import os
import random
import re
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_quiz(question, options, correct_index):
    random.shuffle(options)

    correct_text = options[correct_index]

    # بعد از جابه‌جایی، جای گزینه درست را پیدا می‌کنیم
    new_correct_index = options.index(correct_text)

    data = {
        "chat_id": CHANNEL_ID,
        "question": question,
        "options": options,
        "type": "quiz",
        "correct_option_id": new_correct_index,
        "is_anonymous": True,
        "shuffle_options": True
    }

    return requests.post(f"{API}/sendPoll", json=data).json()


def parse_questions(text):
    pattern = r'(?m)^\s*(\d+)[\.\-)]\s*(.*?)\s*\n\s*الف[\)\.\-:]\s*(.*?)\s*\n\s*ب[\)\.\-:]\s*(.*?)\s*\n\s*ج[\)\.\-:]\s*(.*?)\s*\n\s*د[\)\.\-:]\s*(.*?)(?=\n\s*\d+[\.\-)]|\Z)'

    matches = re.findall(pattern, text, re.S)

    questions = []

    for match in matches:
        number, question, a, b, c, d = match

        options = [
            a.strip(),
            b.strip(),
            c.strip(),
            d.strip()
        ]

        # در مجموعه فعلی، پاسخ صحیح «ب» است
        correct_index = 1

        questions.append({
            "question": question.strip(),
            "options": options,
            "correct_index": correct_index
        })

    return questions


@app.route("/", methods=["GET"])
def home():
    return "Telegram Quiz Bot is running!"


@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(silent=True) or {}

    message = update.get("message", {})
    text = message.get("text", "")

    if not text:
        return "OK"

    if text.startswith("/start"):
        requests.post(
            f"{API}/sendMessage",
            json={
                "chat_id": message["chat"]["id"],
                "text": "سلام 🌷\nسؤالات تستی را با گزینه‌های الف، ب، ج، د برایم بفرست."
            }
        )

    else:
        questions = parse_questions(text)

        if not questions:
            requests.post(
                f"{API}/sendMessage",
                json={
                    "chat_id": message["chat"]["id"],
                    "text": "فرمت سؤال‌ها قابل تشخیص نبود."
                }
            )
        else:
            success = 0

            for q in questions:
                result = send_quiz(
                    q["question"],
                    q["options"],
                    q["correct_index"]
                )

                if result.get("ok"):
                    success += 1

            requests.post(
                f"{API}/sendMessage",
                json={
                    "chat_id": message["chat"]["id"],
                    "text": f"✅ {success} تست در کانال منتشر شد."
                }
            )

    return "OK"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))

    external_url = os.environ.get("RENDER_EXTERNAL_URL")

    if external_url:
        requests.get(
            f"{API}/setWebhook",
            params={"url": external_url + "/webhook"}
        )

    app.run(host="0.0.0.0", port=port)
