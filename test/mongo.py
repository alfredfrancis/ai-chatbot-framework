from pymongo import MongoClient
import json
import ast
from bson.json_util import loads
from bson.json_util import dumps
from bson.objectid import ObjectId
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

def _insert_tagged(): 
    data = {
        "item": request.form['labeled_info'],
        "user_id": "1",
        "story_id": request.form['story_id']
    }
    labled_queries = iky.labled_queries
    post_id = labled_queries.insert_one(data).inserted_id
    return str(post_id)


def _get_tagged(query):
    try:
        labled_queries = iky.labled_queries
        cursor = labled_queries.find(query)
    except Exception as e:
        print "Unexpected error:", type(e), e
    cursor_list = []
    for item in list(cursor):
    	cursor_list.append(ast.literal_eval(item["item"].encode('ascii','ignore')))
    return cursor_list

def _insert(document_name,data):
    document_name = iky[document_name]
    post_id = document_name.insert_one(data).inserted_id
    return str(post_id)

def _retrieve(document_name,query):
    document_name = iky[document_name]
    posts = dumps(document_name.find(query))
    return posts

def _delete(document_name,query):
    document_name = iky[document_name]
    document_name.delete_many(query)