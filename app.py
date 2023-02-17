import json

from asgiref.wsgi import WsgiToAsgi
from flask import Flask, request
from os.path import exists
from revChatGPT.V1 import Chatbot


def configure():
    config_files = ["config.json"]
    config_file = next((f for f in config_files if exists(f)), None)
    if config_file:
        with open(config_file, encoding="utf-8") as f:
            config = json.load(f)
    else:
        print("No config file found.")
        raise Exception("No config file found.")
    return config


app = Flask(__name__)

chatbot = Chatbot(configure())


@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"


@app.route("/ask", methods=['POST'])
def ask():
    req = request.json
    conversation_id = req.get("conversation_id", '')
    parent_id = req.get("parent_id", "")
    prompt = req['prompt']
    answer = ""
    for data in chatbot.ask(prompt, conversation_id, parent_id):
        answer = data["message"]
        parent_id = data["parent_id"]
        conversation_id = data["conversation_id"]
    return {
        "answer": answer,
        "parent_id": parent_id,
        "conversation_id": conversation_id,
    }


asgi_app = WsgiToAsgi(app)
