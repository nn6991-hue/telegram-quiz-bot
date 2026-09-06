import os
import re
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


# -----------------------------
# پاکسازی متن
# -----------------------------

def normalize_text(text):
    if not text:
        return ""

    # حذف کاراکترهای نامرئی و نیم‌فاصله
    for ch in ["\u200c", "\u200d", "\ufeff", "\u2060"]:
        text = text.replace(ch, "")

    # یکسان‌سازی Enter
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # تبدیل اعداد فارسی و عربی به انگلیسی
    text = text.translate(
        str.maketrans(
            "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
            "01234567890123456789"
        )
    )

    # یکسان‌سازی دونقطه
    text = text.replace("：", ":")
    text = text.replace("﹕", ":")
    text = text.replace("꞉", ":")

    return text.strip()


# -----------------------------
# پیدا کردن جواب
# -----------------------------

def find_answer(text):
    match = re.search(
        r"(?:جواب|پاسخ)\s*[:\-]?\s*(الف|ب|ج|د)",
        text,
        re.IGNORECASE
    )

    if not match:
        return None

    answer = match.group(1)

    answer_map = {
        "الف": 0,
        "ب": 1,
        "ج": 2,
        "د": 3
    }

    return answer_map.get(answer)


# -----------------------------
# خواندن یک سؤال
# -----------------------------

def parse_one_question(block):

    block = normalize_text(block)

    correct_index = find_answer(block)

    if correct_index is None:
        return None

    # فقط متن قبل از جواب
    answer_match = re.search(
        r"(?:جواب|پاسخ)\s*[:\-]?\s*(الف|ب|ج|د)",
        block,
        re.IGNORECASE
    )

    content = block[:answer_match.start()].strip()

    # پیدا کردن گزینه‌ها
    # این الگو فاصله قبل از گزینه را اجباری نمی‌کند.
    option_pattern = re.compile(
        r"(الف|ب|ج|د)\s*[\)\.\:\-–—]\s*"
    )

    matches = list(option_pattern.finditer(content))

    # اگر گزینه‌ها بدون علامت بعد از حرف باشند
    if len(matches) < 4:

        option_pattern = re.compile(
            r"(الف|ب|ج|د)(?=\s)"
        )

        matches = list(option_pattern.finditer(content))

    # باید دقیقاً چهار گزینه داشته باشیم
    if len(matches) < 4:
        return None

    matches = matches[:4]

    # متن سؤال
    question = content[:matches[0].start()].strip()

    # حذف شماره سؤال
    question = re.sub(
        r"^\s*\d+\s*[\.\)]\s*",
        "",
        question
    ).strip()

    if not question:
        return None

    options = []

    for i, match in enumerate(matches):

        start = match.end()

        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(content)

        option = content[start:end].strip()

        # جداکننده‌های اضافی ابتدا و انتهای گزینه
        option = re.sub(
            r"^[\s|/\\\-–—]+",
            "",
            option
        )

        option = re.sub(
            r"[\s|/\\]+$",
            "",
            option
        )

        option = option.strip()

        if not option:
            return None

        options.append(option)

    if len(options) != 4:
        return None

    return {
        "question": question,
        "options": options,
        "correct_index": correct_index
    }


# -----------------------------
# جدا کردن چند سؤال
# -----------------------------

def split_questions(text):

    text = normalize_text(text)

    # پیدا کردن شماره سؤال
    pattern = re.compile(
        r"(?:^|\n)\s*\d+\s*[\.\)]\s*"
    )

    starts = list(pattern.finditer(text))

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

    # اگر فقط یک سؤال باشد
    return [text]


# -----------------------------
# پردازش همه سؤال‌ها
# -----------------------------

def parse_questions(text):

    text = normalize_text(text)

    if not text:
        return []

    blocks = split_questions(text)

    results = []

    for block in blocks:

        parsed = parse_one_question(block)

        if parsed:
            results.append(parsed)

    return results


# -----------------------------
# ارسال Quiz به تلگرام
# -----------------------------

def send_quiz(question, options, correct_index):

    url = f"{API_URL}/sendPoll"

    data = {
        "chat_id": CHANNEL_ID,
        "question": question[:300],
        "options": options,
        "type": "quiz",
        "is_anonymous": False,
        "allows_multiple_answers": False,

        # تصادفی شدن گزینه‌ها
        "shuffle_options": True,

        # گزینه صحیح
        "correct_option_ids": [correct_index]
    }

    response = requests.post(
        url,
        json=data,
        timeout=30
    )

    print("SEND POLL:")
    print(response.text)

    return response


# -----------------------------
# ارسال پیام معمولی
# -----------------------------

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

    print("SEND MESSAGE:")
    print(response.text)

    return response


# -----------------------------
# پردازش پیام دریافتی
# -----------------------------

def process_text(chat_id, text):

    print("--------------------------------")
    print("TEXT RECEIVED:")
    print(repr(text))

    questions = parse_questions(text)

    print("QUESTIONS FOUND:", len(questions))

    if not questions:

        send_message(
            chat_id,
            "❌ سؤال قابل تشخیص نبود."
        )

        return

    success = 0

    for item in questions:

        print("--------------------------------")
        print("QUESTION:", item["question"])
        print("OPTIONS:", item["options"])
        print("CORRECT:", item["correct_index"])

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
                print("TELEGRAM ERROR:")
                print(result)

        except Exception as e:

            print("SEND ERROR:")
            print(repr(e))

    send_message(
        chat_id,
        f"✅ {success} سؤال از {len(questions)} سؤال ارسال شد."
    )


# -----------------------------
# تنظیم Webhook
# -----------------------------

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

    print("WEBHOOK:")
    print(response.text)


# -----------------------------
# صفحه اصلی
# -----------------------------

@app.route("/", methods=["GET"])
def home():

    return "Telegram Quiz Bot is running!"


# -----------------------------
# دریافت پیام تلگرام
# -----------------------------

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

        chat = message.get("chat", {})
        chat_id = chat.get("id")

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
        process_text(
            chat_id,
            text
        )

        return "OK"

    except Exception as e:

        print("WEBHOOK ERROR:")
        print(repr(e))

        return "OK"


# -----------------------------
# اجرای برنامه
# -----------------------------

if __name__ == "__main__":

    set_webhook()

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
