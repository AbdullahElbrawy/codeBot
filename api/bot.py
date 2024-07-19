from http.server import BaseHTTPRequestHandler
from os.path import dirname, abspath
import os
from datetime import datetime
import random
from flask import Flask, request, jsonify
from pymongo import MongoClient
import telebot
from dotenv import load_dotenv
import requests

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
FRONT_URL = os.getenv("FRONT_URL")

bot = telebot.TeleBot(BOT_TOKEN)
client = MongoClient(MONGO_URL)
db = client['points']
users_collection = db['users']

app = Flask(__name__)

dir = dirname(abspath(__file__))

# Set the bot start date manually
BOT_START_DATE = datetime(2023, 1, 1)  # Change this to the actual bot start date

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        return

def spin_wheel():
    prizes = [0, 10, 20, 50, 100]
    return random.choice(prizes)

def update_user_points(chat_id, points):
    users_collection.update_one(
        {'chat_id': chat_id},
        {'$inc': {'points': points}},
        upsert=True
    )

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    try:
        username = message.from_user.username or 'unknown user'
        
        user = users_collection.find_one({'chat_id': chat_id})
        if not user:
            join_date = datetime.now()
            users_collection.update_one(
                {'chat_id': chat_id},
                {'$set': {'username': username, 'chat_id': chat_id, 'points': 0, 'account_age': 0, 'join_date': join_date}},
                upsert=True
            )
            account_age = 0
        else:
            join_date = user['join_date']
            if isinstance(join_date, datetime):
                account_age = (datetime.now() - join_date).days
            elif isinstance(join_date, int):
                join_date = datetime.fromtimestamp(join_date)
                account_age = (datetime.now() - join_date).days
            else:
                join_date = datetime.strptime(join_date, '%Y-%m-%d %H:%M:%S.%f')
                account_age = (datetime.now() - join_date).days

        # Calculate bot account age
        bot_account_age = (datetime.now() - BOT_START_DATE).days

        message_text = f"Hello {username}, your account is {account_age} days old. The bot is {bot_account_age} days old."
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(
            text='Open Web App',
            web_app=telebot.types.WebAppInfo(url=f"{FRONT_URL}?username={username}&age={account_age}")
        ))

        bot.send_message(chat_id, message_text, reply_markup=markup)
    except Exception as e:
        bot.send_message(chat_id, 'Failed to retrieve chat information. Please try again later.')
        print(f"Failed to retrieve chat information: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    if call.data == "spin":
        spin(call.message)
    elif call.data == "view_points":
        view_points(call.message)

def spin(message):
    chat_id = message.chat.id
    user = users_collection.find_one({'chat_id': chat_id})
    last_spin_date = user.get('last_spin_date') if user else None
    current_date = datetime.now().date()

    if last_spin_date == current_date:
        bot.send_message(chat_id, "You've already spun the wheel today. Come back tomorrow!")
        return

    points = spin_wheel()
    update_user_points(chat_id, points)
    users_collection.update_one(
        {'chat_id': chat_id},
        {'$set': {'last_spin_date': current_date}},
        upsert=True
    )

    bot.send_message(chat_id, f"You spun the wheel and won {points} points!")

def view_points(message):
    chat_id = message.chat.id
    user = users_collection.find_one({'chat_id': chat_id})
    if user:
        points = user['points']
        bot.send_message(chat_id, f"You have {points} points.")
    else:
        bot.send_message(chat_id, "No points data found.")

@app.route('/api/sendChatId', methods=['POST'])
def send_chat_id():
    username = request.json.get('username')
    user = users_collection.find_one({'username': username})
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'chat_id': user['chat_id']})

@app.route('/data/<string:username>/<int:account_age>', methods=['GET'])
def get_data(username, account_age=None):
    user = users_collection.find_one({'username': username})
    if not user:
        return jsonify({'error': 'User not found'}), 404

    chat_id = user['chat_id']
    user_info = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChat?chat_id={chat_id}").json().get('result', {})

    updates = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates").json().get('result', [])
    user_messages = [update for update in updates if update.get('message', {}).get('chat', {}).get('id') == chat_id]
    
    leaderboard = calculate_leaderboard(updates)

    if account_age is None:
        join_date = user['join_date']
        if isinstance(join_date, datetime):
            account_age = (datetime.now() - join_date).days
        elif isinstance(join_date, int):
            join_date = datetime.fromtimestamp(join_date)
            account_age = (datetime.now() - join_date).days
        else:
            join_date = datetime.strptime(join_date, '%Y-%m-%d %H:%M:%S.%f')
            account_age = (datetime.now() - join_date).days

    data = {
        'username': user_info.get('username'),
        'account_age': account_age or user['account_age'],
        'points': user['points'],
        'cats_count': 707,
        'community': {'name': 'CATS COMMUNITY', 'bonus': 100},
        'leaderboard': leaderboard,
    }

    return jsonify(data)

@app.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    users = users_collection.find().sort('points', -1)
    leaderboard = [
        {'rank': idx + 1, 'name': user['username'], 'score': user['points'], 'medal': get_medal(idx + 1)}
        for idx, user in enumerate(users)
    ]
    return jsonify(leaderboard)

def calculate_leaderboard(updates):
    user_scores = {}
    for update in updates:
        if 'message' in update:
            user_id = update['message']['from']['id']
            username = update['message']['from'].get('username', f"User {user_id}")
            if user_id not in user_scores:
                user_scores[user_id] = {'username': username, 'score': 0}
            user_scores[user_id]['score'] += 1

    leaderboard = sorted(user_scores.values(), key=lambda x: x['score'], reverse=True)
    for idx, user in enumerate(leaderboard):
        user['rank'] = idx + 1
        user['medal'] = get_medal(idx + 1)
    return leaderboard

def get_medal(rank):
    if rank == 1:
        return '🥇'
    elif rank == 2:
        return '🥈'
    elif rank == 3:
        return '🥉'
    else:
        return ''

if __name__ == '__main__':
    import threading
    threading.Thread(target=lambda: bot.polling(none_stop=True)).start()
    app.run(port=3000)
