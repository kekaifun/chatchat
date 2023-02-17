import requests
import uuid
import json
from OpenAIAuth.OpenAIAuth import OpenAIAuth


class Error(Exception):
    """Base class for exceptions in this module."""

    source: str
    message: str
    code: int


class Chatbot:
    """
    Chatbot class for ChatGPT
    """

    def __int__(self, config, conversation_id=None, parent_id=None):
        self.config = config
        self.session = requests.Session()
        self.conversation_id = conversation_id
        self.parent_id = parent_id
        self.baseurl = config.get("baseurl")
        self.conversation_mapping = {}
        self.conversation_id_prev_queue = []
        self.parent_id_prev_queue = []
        self.__login()

    def __refresh_headers(self, access_token):
        self.session.headers.clear()
        self.session.headers.update(
            {
                "Accept": "text/event-stream",
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Openai-Assistant-App-Id": "",
                "Connection": "close",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://chat.openai.com/chat",
            },
        )

    def __login(self):
        auth = OpenAIAuth(
            email_address=self.config.get("email"),
            password=self.config.get("password"),
            proxy=self.config.get("proxy"),
        )
        auth.begin()
        self.config["session_token"] = auth.session_token
        auth.get_access_token()
        self.__refresh_headers(auth.access_token)

    def ask(self, prompt, conversation_id=None, parent_id=None):
        """
        Ask a question to the chatbot
        :param prompt: String
        :param conversation_id: UUID
        :param parent_id: UUID
        """
        if conversation_id is None:  # new conversation
            parent_id = str(uuid.uuid4())
        else:  # old conversation
            if conversation_id == self.conversation_id:  # conversation not changed
                parent_id = self.parent_id
            else:  # conversation changed
                # assume no one else can access the current conversation
                # hence no need to invoke __map_conversations()
                # if conversation_id exists in conversation_mapping
                if conversation_id not in self.conversation_mapping:
                    self.__map_conversations()
                parent_id = self.conversation_mapping[conversation_id]

        data = {
            "action": "next",
            "messages": [
                {
                    "id": str(uuid.uuid4()),
                    "role": "user",
                    "content": {"content_type": "text", "parts": [prompt]},
                },
            ],
            "conversation_id": conversation_id,
            "parent_message_id": parent_id,
            "model": "text-davinci-002-render-sha"
            if not self.config.get("paid")
            else "text-davinci-002-render-paid",
        }

        # new_conv = data["conversation_id"] is None
        self.conversation_id_prev_queue.append(
            data["conversation_id"],
        )  # for rollback
        self.parent_id_prev_queue.append(data["parent_message_id"])
        response = self.session.post(
            url=self.baseurl + "api/conversation",
            data=json.dumps(data),
            timeout=360,
            stream=True,
        )
        self.__check_response(response)
        for line in response.iter_lines():
            line = str(line)[2:-1]
            if line == "" or line is None:
                continue
            if "data: " in line:
                line = line[6:]
            if line == "[DONE]":
                break

            # Replace accidentally escaped double quotes
            line = line.replace('\\"', '"')
            line = line.replace("\\'", "'")
            line = line.replace("\\\\", "\\")
            # Try parse JSON
            try:
                line = json.loads(line)
            except json.decoder.JSONDecodeError:
                continue
            if not self.__check_fields(line):
                print("Field missing")
                print(line)
                continue
            message = line["message"]["content"]["parts"][0]
            conversation_id = line["conversation_id"]
            parent_id = line["message"]["id"]
            yield {
                "message": message,
                "conversation_id": conversation_id,
                "parent_id": parent_id,
            }
        if parent_id is not None:
            self.parent_id = parent_id
        if conversation_id is not None:
            self.conversation_id = conversation_id

    def __check_response(self, response):
        if response.status_code != 200:
            print(response.text)
            error = Error()
            error.source = "OpenAI"
            error.code = response.status_code
            error.message = response.text
            raise error

    def __check_fields(self, data: dict) -> bool:
        try:
            data["message"]["content"]
        except TypeError:
            return False
        except KeyError:
            return False
        return True

    def __map_conversations(self):
        conversations = self.get_conversations()
        histories = [self.get_msg_history(x["id"]) for x in conversations]
        for x, y in zip(conversations, histories):
            self.conversation_mapping[x["id"]] = y["current_node"]

    def get_conversations(self, offset=0, limit=50):
        """
        Get conversations
        :param offset: Integer
        :param limit: Integer
        """
        url = self.baseurl + f"api/conversations?offset={offset}&limit={limit}"
        response = self.session.get(url)
        self.__check_response(response)
        data = json.loads(response.text)
        return data["items"]

    def get_msg_history(self, convo_id):
        """
        Get message history
        :param convo_id: UUID of conversation
        """
        url = self.baseurl + f"api/conversation/{convo_id}"
        response = self.session.get(url)
        self.__check_response(response)
        data = json.loads(response.text)
        return data
