from datetime import datetime
from typing import Dict, Any


class User:
    def __init__(self, user_id: str, display_name: str, is_bot: bool = False):
        self.user_id = user_id
        self.display_name = display_name
        self.is_bot = is_bot
        self.created_at = datetime.now().isoformat()

    @classmethod
    def from_zalo(cls, data: Dict[str, Any]):
        return cls(
            user_id=data["id"],
            display_name=data.get("display_name", "Unknown"),
            is_bot=data.get("is_bot", False)
        )

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "display_name": self.display_name,
            "is_bot": self.is_bot,
            "created_at": self.created_at
        }


class Message:
    def __init__(self, message_id: str, user_id: str, text: str, timestamp: int):
        self.message_id = message_id
        self.user_id = user_id
        self.text = text
        self.timestamp = timestamp
        self.saved_at = datetime.now().isoformat()

    @classmethod
    def from_zalo(cls, data: Dict[str, Any]):
        msg = data.get("message", {})
        sender = msg.get("from", {})
        return cls(
            message_id=msg.get("message_id", "unknown"),
            user_id=sender.get("id", "unknown"),
            text=msg.get("text", ""),
            timestamp=msg.get("date", 0)
        )

    def to_dict(self):
        return {
            "message_id": self.message_id,
            "user_id": self.user_id,
            "text": self.text,
            "timestamp": self.timestamp,
            "saved_at": self.saved_at
        }
