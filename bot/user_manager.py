import json
import os
import logging
from typing import Dict, List
from bot.models import User

USER_FILE = "data/users.json"


class UserManager:
    """Quản lý và lưu trữ danh sách user duy nhất (unique theo user_id)."""

    def __init__(self, file_path: str = USER_FILE):
        self.file_path = file_path
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self.users: Dict[str, Dict] = {}
        self._load_users()
        logging.info(
            f"📁 UserManager khởi động, có {len(self.users)} user hiện tại.")

    def _load_users(self):
        """Đọc dữ liệu user từ file JSON."""
        if not os.path.exists(self.file_path):
            self.users = {}
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.users = {u["user_id"]: u for u in data if "user_id" in u}
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logging.warning(
                f"⚠️ Không thể load users.json ({e}), tạo file mới.")
            self.users = {}

    def _write_file(self):
        """Ghi danh sách user ra file JSON."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(list(self.users.values()), f,
                          ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"❌ Lỗi khi ghi users.json: {e}")

    def save_user(self, user: User):
        """Lưu user mới nếu chưa có trong danh sách."""
        if user.user_id not in self.users:
            self.users[user.user_id] = user.to_dict()
            self._write_file()
            logging.info(
                f"✅ Lưu user mới: {user.display_name} ({user.user_id})")
        else:
            logging.debug(f"⏩ User {user.display_name} đã tồn tại, bỏ qua.")

    def get_user(self, user_id: str) -> Dict:
        """Trả về thông tin user theo ID."""
        return self.users.get(user_id)

    def get_all_users(self) -> List[Dict]:
        """Trả về toàn bộ danh sách user."""
        return list(self.users.values())
