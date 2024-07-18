import os
import json
from pymongo import MongoClient

def handler(request, response):
    username = request.json.get('username')
    client = MongoClient(os.getenv("MONGO_URL"))
    db = client['points']
    users_collection = db['users']
    
    user = users_collection.find_one({'username': username})
    if not user:
        response.status_code = 404
        return json.dumps({'error': 'User not found'})
    
    return json.dumps({'chat_id': user['chat_id']})
