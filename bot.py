import os
import re
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def set_webhook():
    external_url = os.environ.get("RENDER_EXTERNAL_URL")

    if not external_url:
        print("ERROR: RENDER_EXTERNAL_URL is missing")
        return

    webhook_url = external_url.rstrip("/") + "/webhook"

    try:
        result = requests.get(
            f"{API}/setWebhook",
            params={"url": webhook_url},
            timeout=10
        )
        print("setWebhook:", result.text)
    except Exception as e:
        print("setWebhook error:", repr(e))


def send_quiz(question, options, correct_index):
    data = {
        "chat_id": CHANNEL_ID,
        "question": question,
        "options": options,
        "type": "quiz",
        "correct_option_ids": [correct_index],
        "is_anonymous": True,
        "shuffle_options": True
    }

    try:
        response = requests.post(
            f"{API}/sendPoll",
            json=data,
            timeout=15
        )
        result = response.json()
        print("sendPoll:", result)
        return result
    except Exception as e:
        print("sendPoll error:", repr(e))
        return {"ok": False}


def normalize_digits(text):
    table = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
    return text.translate(table)


def parse_questions(text):

    text = text.replace("\u200c", "")
    text = text.replace("\r", "\n")

    # پیدا کردن شروع سؤال‌ها؛ چه در خط جدید باشند چه پشت سر هم
    start_pattern = r'(?<!\d)([0-9۰-۹]+)\s*[\.\)]\s*'

    starts = list(re.finditer(start_pattern, text))

    questions = []

    for i, start in enumerate(starts):

        # متن این سؤال تا شروع سؤال بعدی
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        block = text[start.end():end].strip()

        # پیدا کردن جواب
        answer_match = re.search(
            r'(?:پاسخ|جواب)\s*[:：\-]?\s*([الفبجد])',
            block,
            re.IGNORECASE
        )

        if not answer_match:
            continue

        answer = answer_match.group(1).strip()

        letter_to_index = {
            "الف": 0,
            "ب": 1,
            "ج": 2,
            "د": 3
        }

        if answer not in letter_to_index:
            continue

        # قسمت سؤال و گزینه‌ها
        content = block[:answer_match.start()].strip()

        # پیدا کردن محل گزینه‌های الف، ب، ج، د
        option_pattern = r'(?:^|\s)(الف|ب|ج|د)\s*[\)\.\-:]?\s*'

        option_matches = list(re.finditer(option_pattern, content))

        if len(option_matches) < 4:
            continue

        # متن سؤال
        question = content[:option_matches[0].start()].strip()

        # گزینه‌ها
        options = []

        for j in range(4):
            option_start = option_matches[j].end()

            if j + 1 < 4:
                option_end = option_matches[j + 1].start()
            else:
                option_end = len(content)

            option_text = content[option_start:option_end].strip()

            if option_text:
                options.append(option_text)

        if len(options) != 4:
            continue

        questions.append({
            "question": question,
            "options": options,
            "correct_index": letter_to_index[answer]
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
                "text": (
                    "سلام 🌷\n"
                    "سؤالات تستی را با گزینه‌های الف، ب، ج، د "
                    "و جواب صحیح بفرست."
                )
            },
            timeout=15
        )

        return "OK"

    questions = parse_questions(text)

    if not questions:

        requests.post(
            f"{API}/sendMessage",
            json={
                "chat_id": message["chat"]["id"],
                "text": (
                    "❌ سؤال قابل تشخیص نبود.\n"
                    "فرمت باید شامل چهار گزینه و «جواب: ...» باشد."
                )
            },
            timeout=15
        )

        return "OK"

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
            "text": f"✅ {success} تست از {len(questions)} تست در کانال منتشر شد."
        },
        timeout=15
    )

    return "OK"


set_webhook()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port) 
