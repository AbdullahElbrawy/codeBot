import os
import json
from pymongo import MongoClient

def handler(request, response):
    client = MongoClient(os.getenv("MONGO_URL"))
    db = client['points']
    users_collection = db['users']
    
    users = users_collection.find().sort('points', -1)
    leaderboard = [
        {'rank': idx + 1, 'name': user['username'], 'score': user['points'], 'medal': get_medal(idx + 1)}
        for idx, user in enumerate(users)
    ]
    
    return json.dumps(leaderboard)

def get_medal(rank):
    if rank == 1:
        return '🥇'
    elif rank == 2:
        return '🥈'
    elif rank == 3:
        return '🥉'
    else:
        return ''
