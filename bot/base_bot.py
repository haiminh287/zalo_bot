import logging
from zalo_bot import Bot
from zalo_bot.ext import Dispatcher
from .handlers import register_all_handlers
import requests


class ZaloBotBase:

    def __init__(self, token: str, webhook_url: str, secret_token: str):
        self.token = token
        self.webhook_url = webhook_url
        self.secret_token = secret_token
        self.bot = Bot(token=token)
        self.dispatcher = Dispatcher(self.bot, None, workers=0)
        self.api_url = f"https://bot-api.zapps.me/bot{self.token}"

        logging.info("🧩 Khởi tạo ZaloBotBase")

        # Gắn các handler mặc định
        for handler in register_all_handlers():
            self.dispatcher.add_handler(handler)

    def set_webhook(self):
        """Đăng ký webhook cho bot."""
        result = self.bot.set_webhook(
            url=self.webhook_url, secret_token=self.secret_token)
        if result:
            logging.info(f"✅ Webhook set thành công: {self.webhook_url}")
        else:
            logging.error("❌ Webhook không set được, kiểm tra lại URL/token.")
        return result

    def process_update(self, data: dict):
        """Xử lý dữ liệu webhook gửi đến."""
        from zalo_bot import Update

        if "result" in data:
            update_data = data["result"]
        else:
            update_data = data

        update = Update.de_json(update_data, self.bot)
        self.dispatcher.process_update(update)

    def send_message_to_user(self, user_id: str, text: str):
        """Bot chủ động gửi tin nhắn đến 1 user cụ thể."""
        url = f"{self.api_url}/sendMessage"
        body = {
            "chat_id": user_id,
            "text": text
        }
        resp = requests.post(url, json=body, timeout=10)
        logging.info(f"主动发送 (send_message_to_user) -> {resp.text}")
        return resp.json()

    def send_photo_to_user(self, user_id: str, photo_url: str, caption: str = ""):
        """Bot chủ động gửi ảnh đến 1 user cụ thể."""
        url = f"{self.api_url}/sendPhoto"
        body = {
            "chat_id": user_id,
            "photo": photo_url,
            "caption": caption
        }
        resp = requests.post(url, json=body, timeout=10)
        logging.info(f"主动发送 (send_photo_to_user) -> {resp.text}")
        return resp.json()
