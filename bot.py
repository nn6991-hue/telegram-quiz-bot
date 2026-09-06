import os
import re
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

LETTER_MAP = {
    "الف": 0,
    "ب": 1,
    "ج": 2,
    "د": 3
}


def normalize_text(text):
    if not text:
        return ""

    # حذف کاراکترهای نامرئی و نیم‌فاصله
    for ch in ["\u200c", "\u200d", "\ufeff", "\u2060"]:
        text = text.replace(ch, "")

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # تبدیل اعداد فارسی و عربی به انگلیسی
    trans = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    )
    text = text.translate(trans)

    # یکسان‌سازی دونقطه
    text = text.replace("：", ":")

    return text.strip()


def parse_one_question(block):
    block = normalize_text(block)

    # پیدا کردن جواب
    answer_match = re.search(
        r"(?:جواب|پاسخ)\s*[:\-]?\s*(الف|ب|ج|د)\b",
        block
    )

    if not answer_match:
        print("ANSWER NOT FOUND")
        return None

    answer_letter = answer_match.group(1)
    correct_index = LETTER_MAP[answer_letter]

    # حذف قسمت جواب از متن
    content = block[:answer_match.start()].strip()

    # پیدا کردن گزینه‌ها
    option_pattern = re.compile(
        r"(الف|ب|ج|د)\s*[\)\.\:\-–—]\s*"
    )

    matches = list(option_pattern.finditer(content))

    if len(matches) < 4:
        print("OPTIONS NOT FOUND:", len(matches))
        return None

    matches = matches[:4]

    question = content[:matches[0].start()].strip()

    # حذف شماره سؤال
    question = re.sub(
        r"^\s*\d+\s*[\.\)]\s*",
        "",
        question
    ).strip()

    if not question:
        print("QUESTION TEXT NOT FOUND")
        return None

    options = []

    for i, match in enumerate(matches):
        start = match.end()

        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(content)

        option = content[start:end].strip()

        # جداکننده‌های اضافی را فقط از ابتدا و انتها حذف می‌کنیم
        option = re.sub(
            r"^[\s|/\\\-–—]+",
            "",
            option
        ).strip()

        option = re.sub(
            r"[\s|/\\]+$",
            "",
            option
        ).strip()

        if not option:
            print("EMPTY OPTION")
            return None

        options.append(option)

    if len(options) != 4:
        return None

    return {
        "question": question,
        "options": options,
        "correct_index": correct_index
    }


def split_questions(text):
    text = normalize_text(text)

    if not text:
        return []

    # پیدا کردن شروع سؤال‌های شماره‌دار
    starts = list(
        re.finditer(
            r"(?m)(?:^|\n)\s*\d+\s*[\.\)]\s*",
            text
        )
    )

    # چند سؤال شماره‌دار
    if len(starts) >= 2:
        blocks = []

        for i, match in enumerate(starts):
            start = match.start()

            if i + 1 < len(starts):
                end = starts[i + 1].start()
            else:
                end = len(text)

            block = text[start:end].strip()

            if block:
                blocks.append(block)

        return blocks

    # یک سؤال
    return [text]


def parse_questions(text):
    text = normalize_text(text)

    blocks = split_questions(text)

    results = []

    for block in blocks:
        print("PROCESSING BLOCK:")
        print(repr(block))

        parsed = parse_one_question(block)

        if parsed:
            print("QUESTION FOUND:", parsed["question"])
            print("OPTIONS:", parsed["options"])
            print("CORRECT:", parsed["correct_index"])

            results.append(parsed)

    print("QUESTIONS FOUND:", len(results))

    return results


def send_quiz(question, options, correct_index):

    url = f"{API_URL}/sendPoll"

    data = {
        "chat_id": CHANNEL_ID,
        "question": question[:300],
        "options": options,
        "type": "quiz",

        # کانال فقط Poll ناشناس را قبول می‌کند
        "is_anonymous": True,

        "allows_multiple_answers": False,

        # گزینه‌ها تصادفی می‌شوند
        "shuffle_options": True,

        # پاسخ صحیح
        "correct_option_ids": [correct_index]
    }

    response = requests.post(
        url,
        json=data,
        timeout=30
    )

    print("SEND POLL:", response.text)

    return response


def send_message(chat_id, text):

    url = f"{API_URL}/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": text
    }

    response = requests.post(
        url,
        json=data,
        timeout=30
    )

    print("SEND MESSAGE:", response.text)

    return response


def process_text(chat_id, text):

    print("===================================")
    print("RAW TEXT:")
    print(repr(text))

    questions = parse_questions(text)

    if not questions:
        send_message(
            chat_id,
            "❌ سؤال قابل تشخیص نبود."
        )
        return

    success = 0

    for item in questions:

        try:
            response = send_quiz(
                item["question"],
                item["options"],
                item["correct_index"]
            )

            result = response.json()

            if result.get("ok"):
                success += 1
            else:
                print("TELEGRAM ERROR:", result)

        except Exception as e:
            print("SEND ERROR:", repr(e))

    send_message(
        chat_id,
        f"✅ {success} سؤال از {len(questions)} سؤال ارسال شد."
    )


def set_webhook():

    if not RENDER_EXTERNAL_URL:
        print("RENDER_EXTERNAL_URL پیدا نشد.")
        return

    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"

    url = f"{API_URL}/setWebhook"

    response = requests.post(
        url,
        json={"url": webhook_url},
        timeout=30
    )

    print("WEBHOOK:", response.text)


@app.route("/", methods=["GET"])
def home():
    return "Telegram Quiz Bot is running!"


@app.route("/webhook", methods=["POST"])
def webhook():

    try:

        update = request.get_json(silent=True)

        print("UPDATE RECEIVED:")
        print(update)

        if not update:
            return "OK"

        message = update.get("message")

        if not message:
            return "OK"

        chat_id = message.get("chat", {}).get("id")

        text = message.get("text", "")

        if not text:
            return "OK"

        # دستور شروع
        if text.strip() == "/start":

            send_message(
                chat_id,
                "سلام 🌷\n"
                "سؤالات تستی را با گزینه‌های الف، ب، ج، د برایم بفرست."
            )

            return "OK"

        # پردازش سؤال
        process_text(chat_id, text)

        return "OK"

    except Exception as e:

        print("WEBHOOK ERROR:", repr(e))

        return "OK"


if __name__ == "__main__":

    set_webhook()

    port = int(
        os.environ.get("PORT", 10000)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
