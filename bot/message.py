import datetime
from typing import Optional, Union
from zalo_bot._zalo_object import ZaloObject
from zalo_bot._user import User
from zalo_bot._chat import Chat
from zalo_bot._utils.default_value import DEFAULT_NONE, DefaultValue
from zalo_bot._utils.types import JSONDict, ODVInput


class Message(ZaloObject):
    """Mở rộng message Zalo hỗ trợ phản hồi nhanh (text, action, sticker, photo)."""

    __slots__ = (
        "message_id",
        "date",
        "chat",
        "text",
        "from_user",
        "sticker",
        "photo_url",
        "message_type",
    )

    def __init__(
        self,
        message_id: str,
        date: datetime.datetime,
        chat: Chat,
        message_type: ODVInput[Union[str, DefaultValue]] = DEFAULT_NONE,
        text: Optional[str] = None,
        sticker: Optional[str] = None,
        photo_url: Optional[str] = None,
        from_user: Optional[User] = None,
        *,
        api_kwargs: Optional[JSONDict] = None,
    ):
        super().__init__(api_kwargs=api_kwargs)
        self.message_id = message_id
        self.date = date
        self.chat = chat
        self.text = text
        self.message_type = (
            message_type if message_type is not DEFAULT_NONE else "CHAT_MESSAGE"
        )
        self.sticker = sticker
        self.photo_url = photo_url
        self.from_user = from_user
        self._id_attrs = (self.message_id, self.chat)
        self._freeze()

    # -------------------------------
    # 🔁 Parse JSON từ webhook payload
    # -------------------------------
    @classmethod
    def de_json(cls, data: Optional[JSONDict], bot=None) -> Optional["Message"]:
        data = cls._parse_data(data)
        if not data:
            return None
        msg = cls(
            message_id=data["message_id"],
            date=datetime.datetime.fromtimestamp(data["date"] / 1000),
            chat=Chat.de_json(data.get("chat"), bot),
            message_type=data.get("message_type", "CHAT_MESSAGE"),
            text=data.get("text"),
            sticker=data.get("sticker"),
            photo_url=data.get("photo_url"),
            from_user=User.de_json(data.get("from"), bot),
            api_kwargs=data,
        )
        msg.set_bot(bot)
        return msg

    # -------------------------------
    # 💬 Các hàm phản hồi tiện dụng
    # -------------------------------
    def reply_text(self, text: str):
        """Gửi tin nhắn văn bản phản hồi."""
        return self.get_bot().send_message(chat_id=self.chat.id, text=text)

    def reply_action(self, action: str):
        """Gửi hiệu ứng chat (typing, uploading_photo...)."""
        return self.get_bot().send_chat_action(chat_id=self.chat.id, action=action)

    def reply_photo(self, photo_url: str, caption: Optional[str] = None):
        """Gửi ảnh kèm chú thích."""
        return self.get_bot().send_photo(
            chat_id=self.chat.id, photo=photo_url, caption=caption or ""
        )

    def reply_sticker(self, sticker_id: str):
        """Gửi sticker phản hồi."""
        return self.get_bot().send_sticker(chat_id=self.chat.id, sticker=sticker_id)
