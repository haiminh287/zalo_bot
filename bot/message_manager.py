import json
import os
from typing import List, Dict
from bot.models import Message

MESSAGE_FILE = "data/messages.json"


class MessageManager:
    def __init__(self, file_path: str = MESSAGE_FILE):
        self.file_path = file_path
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self._load_messages()

    def _load_messages(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, "r", encoding="utf-8") as f:
                try:
                    self.messages = json.load(f)
                except json.JSONDecodeError:
                    self.messages = []
        else:
            self.messages = []

    def save_message(self, message: Message):
        self.messages.append(message.to_dict())
        self._write_file()

    def get_messages_by_user(self, user_id: str) -> List[Dict]:
        return [m for m in self.messages if m["user_id"] == user_id]

    def get_all_messages(self) -> List[Dict]:
        return self.messages

    def _write_file(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.messages, f, ensure_ascii=False, indent=2)
