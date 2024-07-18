import os
import random
from datetime import datetime
from pymongo import MongoClient
import telebot
from dotenv import load_dotenv
import requests
import aiohttp
import asyncio

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
FRONT_URL = os.getenv("FRONT_URL")

bot = telebot.AsyncTeleBot(BOT_TOKEN)
client = MongoClient(MONGO_URL)
db = client['points']
users_collection = db['users']

def calculate_telegram_account_age(join_date):
    current_date = datetime.now()
    creation_date = datetime.fromtimestamp(join_date)
    age_in_days = (current_date - creation_date).days
    return age_in_days

def spin_wheel():
    prizes = [0, 10, 20, 50, 100]
    return random.choice(prizes)

def update_user_points(chat_id, points):
    users_collection.update_one(
        {'chat_id': chat_id},
        {'$inc': {'points': points}},
        upsert=True
    )

async def start(message):
    chat_id = message.chat.id
    try:
        join_date = message.date
        account_age = calculate_telegram_account_age(join_date)
        username = message.from_user.username or 'unknown user'

        # Check if the user already exists
        user = users_collection.find_one({'chat_id': chat_id})
        if not user:
            users_collection.update_one(
                {'chat_id': chat_id},
                {'$set': {'username': username, 'chat_id': chat_id, 'points': 0, 'account_age': account_age, 'join_date': join_date}},
                upsert=True
            )
        else:
            users_collection.update_one(
                {'chat_id': chat_id},
                {'$set': {'account_age': account_age, 'join_date': join_date}}
            )

        message_text = f"Hello {username}, your account is {account_age} days old."
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(
            text='Open Web App',
            web_app=telebot.types.WebAppInfo(url=f"{FRONT_URL}?username={username}&age={account_age}")
        ))

        await bot.send_message(chat_id, message_text, reply_markup=markup)
    except Exception as e:
        await bot.send_message(chat_id, 'Failed to retrieve chat information. Please try again later.')
        print(f"Failed to retrieve chat information: {e}")

async def callback_query(call):
    chat_id = call.message.chat.id
    if call.data == "spin":
        await spin(call.message)
    elif call.data == "view_points":
        await view_points(call.message)

async def spin(message):
    chat_id = message.chat.id
    user = users_collection.find_one({'chat_id': chat_id})
    last_spin_date = user.get('last_spin_date') if user else None
    current_date = datetime.now().date()

    if last_spin_date == current_date:
        await bot.send_message(chat_id, "You've already spun the wheel today. Come back tomorrow!")
        return

    points = spin_wheel()
    update_user_points(chat_id, points)
    users_collection.update_one(
        {'chat_id': chat_id},
        {'$set': {'last_spin_date': current_date}},
        upsert=True
    )

    await bot.send_message(chat_id, f"You spun the wheel and won {points} points!")

async def view_points(message):
    chat_id = message.chat.id
    user = users_collection.find_one({'chat_id': chat_id})
    if user:
        points = user['points']
        await bot.send_message(chat_id, f"You have {points} points.")
    else:
        await bot.send_message(chat_id, "No points data found.")

if __name__ == '__main__':
    bot.polling(none_stop=True)
