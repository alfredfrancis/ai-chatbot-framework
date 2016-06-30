from ikyWebServer import app
from pymongo import MongoClient
from flask import request

# Initialize MongoDb client with default local server
client = MongoClient()
iky = client.iky


def _insert(document_name, data):
    document_name = iky[document_name]
    post_id = document_name.insert_one(data).inserted_id
    return str(post_id)


def _retrieve(document_name, query):
    document_name = iky[document_name]
    posts = list(document_name.find(query))
    return posts


def _update(document_name, condition, query):
    document_name = iky[document_name]
    posts = document_name.update_one(
        condition,
        {
            "$set": query
        }
    )
    return "Done"


def _delete(document_name, query):
    document_name = iky[document_name]
    document_name.delete_many(query)


"""
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
"""
