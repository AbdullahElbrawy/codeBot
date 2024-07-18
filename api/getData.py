import os
import json
import requests
from pymongo import MongoClient

def handler(request, response):
    username = request.path_params['username']
    account_age = request.path_params.get('account_age', None)
    client = MongoClient(os.getenv("MONGO_URL"))
    db = client['points']
    users_collection = db['users']
    
    user = users_collection.find_one({'username': username})
    if not user:
        response.status_code = 404
        return json.dumps({'error': 'User not found'})
    
    chat_id = user['chat_id']
    user_info = requests.get(f"https://api.telegram.org/bot{os.getenv('BOT_TOKEN')}/getChat?chat_id={chat_id}").json().get('result', {})
    
    updates = requests.get(f"https://api.telegram.org/bot{os.getenv('BOT_TOKEN')}/getUpdates").json().get('result', [])
    leaderboard = calculate_leaderboard(updates)
    
    data = {
        'username': user_info.get('username'),
        'account_age': account_age or user['account_age'],
        'points': user['points'],
        'cats_count': 707,
        'community': {'name': 'CATS COMMUNITY', 'bonus': 100},
        'leaderboard': leaderboard,
    }
    
    return json.dumps(data)

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
