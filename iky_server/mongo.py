from iky_server import app
from pymongo import MongoClient
import json
import ast

from flask import request

# Initialize MongoDb client with default local server
client = MongoClient()
iky = client.iky


def _insert_user(name, email, level):
    users = iky.users
    user_info = {
        "uname": name,
        "email": email,
        "level": "admin",
        "stories": []
    }
    user_id = users.insert_one().inserted_id
    return user_id


@app.route('/_insert_tagged', methods=['POST'])
def _insert_tagged():
    text = request.form['labeled_info']
    data = {
        "item": text,
        "u_id": "1",
        "story_id": "1"
    }
    labled_queries = iky.labled_queries
    post_id = labled_queries.insert_one(data).inserted_id
    return str(post_id)


def _get_tagged(query={"story_id": "1"}):
    try:
        labled_queries = iky.labled_queries
        cursor = labled_queries.find(query)
    except Exception as e:
        print "Unexpected error:", type(e), e
    cursor_list = []
    for item in list(cursor):
    	cursor_list.append(ast.literal_eval(item["item"].encode('ascii','ignore')))
    return cursor_list

