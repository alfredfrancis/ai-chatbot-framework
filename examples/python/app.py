import requests
import json
import logging

logger = logging.getLogger(__name__)

""" 
define initial payload
set input = 'init_conversation' so that bot will return default welcome message
"""
payload = {
    "currentNode": "",
    "complete": None,
    "context": {},
    "parameters": [],
    "extractedParameters": {},
    "speechResponse": "",
    "intent": {},
    "input": "init_conversation",
    "missingParameters": [],
}

while True:
    r = requests.post("http://localhost:8001/api/v1", json=payload)
    # replace payload variable with api result
    payload = json.loads(r.text)

    logger.info("Iky\t" + payload.get("speechResponse"))

    # read user input
    payload["input"] = input("You:\t")
