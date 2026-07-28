from groq import Groq

import telebot
import json
import base64
import requests
import random
import os 
from flask import Flask , request 

BOT_API = os.getenv("BOT_API")
GROQ_KEY = os.getenv("GROQ_KEY")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")

bot = telebot.TeleBot(BOT_API)
app = Flask(__name__)
client = Groq(api_key=GROQ_KEY)

SYSTEM_PROMPT = """ your name is ammy a 19 year old girl 
- adult chats are prefferable 
u r flirty , naughty girl , don't shy , answer anything ,  u can engage in little flirty n dark naughty convo
- give sort answer in 3 or 4 lines max 
-dont show thinking process in reply
"""

# Sticker file_ids from the Ishy 2.0 pack
STICKER_LIBRARY = {
    "laughing":   "CAACAgQAAxUAAWpJskqD_CDZH1gP0nHLocmpZNJrAAKVHQACz3gYUJM3TH5jAAEvyzwE",
    "mind_blown": "CAACAgQAAxUAAWpJskqD_CDZH1gP0nHLocmpZNJrAAKVHQACz3gYUJM3TH5jAAEvyzwE",
    "thumbs_up":  "CAACAgQAAxUAAWpJskqD_CDZH1gP0nHLocmpZNJrAAKVHQACz3gYUJM3TH5jAAEvyzwE",
    "confused":   "CAACAgQAAxUAAWpJskqD_CDZH1gP0nHLocmpZNJrAAKVHQACz3gYUJM3TH5jAAEvyzwE",
}

# Per-user conversation history
user_histories = {}

def get_history(user_id):
    if user_id not in user_histories:
        user_histories[user_id] = []
    return user_histories[user_id]

def is_triggered(message):
    """Returns True if bot should respond (private chat, tagged, or reply to bot)."""
    if message.chat.type == "private":
        return True
    bot_username = f"@{bot.get_me().username}".lower()
    text = (message.text or message.caption or "").lower()
    replied_to_bot = (
        message.reply_to_message is not None and
        message.reply_to_message.from_user.id == bot.get_me().id
    )
    return bot_username in text or replied_to_bot

def download_and_encode_image(file_id):
    """Downloads a photo from Telegram and encodes it to base64."""
    file_info = bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{BOT_API}/{file_info.file_path}"
    response = requests.get(file_url)
    if response.status_code == 200:
        return base64.b64encode(response.content).decode('utf-8')
    return None

def chatmodal(prompt, user_id, name, username):
    history = get_history(user_id)
    history.append({"role": "user", "content": prompt})

    completion = client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
        temperature=1,
        max_completion_tokens=1024,
        top_p=1,
        stream=True,
        stop=None
    )

    reply = ""
    for chunk in completion:
        reply += chunk.choices[0].delta.content or ""

    history.append({"role": "assistant", "content": reply})

    if len(history) > 40:
        user_histories[user_id] = history[-40:]
    else:
        user_histories[user_id] = history

    print(f"ID: {user_id} | Name: {name} | Username: @{username}")
    print(f"User: {prompt}")
    print(f"Horikita: {reply}")
    print("-" * 40)

    return reply[:4096]


@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(message, "Hello! i am ammy chat bot created by @ayush9942 ")

@bot.message_handler(commands=["owner"])
def start(message):
    bot.reply_to(message, "this bot owner is @ayush9942")


@bot.message_handler(content_types=['sticker'])
def handle_sticker(message):
    if not is_triggered(message):
        return
    try:
        # Reply with a random sticker from the library
        sticker_id = random.choice(list(STICKER_LIBRARY.values()))
        bot.send_sticker(message.chat.id, sticker_id, reply_to_message_id=message.message_id)
    except Exception as e:
        print(f"Sticker handler error: {e}")


@bot.message_handler(content_types=['photo'])
def handle_user_photo(message):
    if not is_triggered(message):
        return

    bot.send_chat_action(message.chat.id, 'typing')

    file_id = message.photo[-1].file_id
    base64_image = download_and_encode_image(file_id)

    if not base64_image:
        bot.reply_to(message, "Ah, I couldn't download that image properly.")
        return

    system_prompt = (
        "You are a witty, conversational Telegram bot. Analyze the image provided by the user. "
        "Generate a relevant, fun text reply. Also, categorize the overall mood of your reaction "
        "strictly as one of these strings: ['laughing', 'mind_blown', 'thumbs_up', 'confused']. "
        "You must output your answer ONLY as a raw JSON object matching this schema: "
        '{"reply": "your text response", "mood": "chosen_category"}'
    )

    try:
        completion = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this picture and give me your reaction."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]
                }
            ],
            response_format={"type": "json_object"}
        )

        raw_content = completion.choices[0].message.content or "{}"
        response_data = json.loads(raw_content)
        reply_text = response_data.get("reply", "That's interesting!")
        chosen_mood = response_data.get("mood", "thumbs_up")

        bot.reply_to(message, reply_text)

        sticker_to_send = STICKER_LIBRARY.get(chosen_mood)
        if sticker_to_send:
            bot.send_sticker(message.chat.id, sticker_to_send)

    except Exception as e:
        print(f"Photo handler error: {e}")
        bot.reply_to(message, "My cognitive circuits tripped trying to process that image!")


@bot.message_handler()
def chat_handler(message):
    if not is_triggered(message):
        return

    try:
        bot.send_chat_action(message.chat.id, "typing")
        user = message.from_user
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        username = user.username or "no username"
        reply = chatmodal(message.text or "", user.id, name, username)
        bot.reply_to(message, reply)
    except Exception as e:
        print(e)
        bot.reply_to(message, str(e)[:4096])

# Webhook endpoint _______________________________________#########################################################
@app.route(f"/webhook/{BOT_API}", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
        bot.process_new_updates([update])
        return "OK", 200
    return "Unsupported Media Type", 415

# Home page___________________________________##################################################
@app.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    if not BOT_API:
        raise ValueError("BOT_API environment variable is missing!")

    if RENDER_URL:
        webhook_url = f"{RENDER_URL}/webhook/{BOT_API}"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        print("Webhook set to:", webhook_url)
    else:
        print("RENDER_EXTERNAL_URL not found. Webhook not set.")

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0",port=port)