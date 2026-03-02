import re
import tempfile
import qrcode
import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from bot.handlers import _format_vnd_thousands, load_users
from config import Config
from bot.base_bot import ZaloBotBase
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

DATA_FILE = "data/data.json"

# -------------------- HÀM PHỤ TRỢ --------------------


def load_data():
    """Đọc file JSON (nếu chưa có thì trả về list rỗng)."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def load_user():
    """Đọc file JSON người dùng (nếu chưa có thì trả về list rỗng)."""
    user_file = "data/users.json"
    if os.path.exists(user_file):
        with open(user_file, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save_data(data):
    """Ghi danh sách dữ liệu vào file JSON."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


bot_app = ZaloBotBase(
    token=Config.TOKEN,
    webhook_url=Config.WEBHOOK_URL,
    secret_token=Config.SECRET_TOKEN,
)
bot_app.set_webhook()


choices = {
    "0": {
        "text": "KHÔNG ĂN",
        "so_buoi": 0
    },
    "1":
        {"text": "CẢ NGÀY",
         "so_buoi": 2},
        "2": {
            "text": "BUỔI TRƯA",
            "so_buoi": 1
    },
    "3": {
            "text": "BUỔI TỐI",
            "so_buoi": 1
    },
}


@app.route("/webhook", methods=["POST"])
def webhook():
    """Nhận webhook từ Zalo và xử lý phản hồi của người dùng."""
    data = request.get_json(force=True)
    logging.info(f"📨 Nhận webhook: {data}")
    print("data:", data)

    user_id = data["message"]["from"]["id"]
    user_name = str(data["message"]["from"].get(
        "display_name", "Không rõ tên"))
    user_message = data["message"].get("text", "").strip()
    selected = None
    if user_message in choices:
        selected = choices[user_message]
        print(type(selected))
        print(selected)

    today = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
    if selected:
        logging.info(f"✅ {user_name} ({user_id}) chọn: {selected}")

        all_data = load_data()
        found = False
        for entry in all_data:
            if entry["date"] == today and entry["user_id"] == user_id:
                # Cập nhật lựa chọn
                bot_app.send_message_to_user(
                    user_id,
                    f"Bạn đã chọn rồi nhé! Lựa chọn hiện tại của bạn là: {entry['choice']} cho ngày {today}."
                )
                found = True
                break

        if not found:
            all_data.append({
                "date": today,
                "user_id": user_id,
                "user_name": user_name,
                "choice": selected["text"],
                "so_buoi": selected["so_buoi"]
            })
            bot_app.send_message_to_user(
                user_id,
                f"Cảm ơn bạn đã chọn: {selected['text']} cho ngày {today}!"
            )

        save_data(all_data)

    bot_app.process_update(data)
    return jsonify({"ok": True})


@app.route("/send_user", methods=["POST"])
def send_user():
    """Gửi tin nhắn thủ công đến user."""
    data = request.get_json(force=True)
    logging.info(f"📨 Gửi tin nhắn đến user: {data}")

    bot_app.send_message_to_user(
        data.get("user_id"),
        data.get("message", "Tin nhắn từ bot")
    )
    return jsonify({"ok": True})


def send_daily_message():
    """Hàm gửi tin nhắn tự động lúc 10 giờ tối mỗi ngày."""
    tomorrow = datetime.now() + timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%d/%m")
    print(tomorrow_str)

    message = ""

    logging.info(f"⏰ Gửi tin nhắn tự động lúc {datetime.now()}")
    with open(r"data/users.json", "r", encoding="utf-8") as f:
        data = f.read()
        data_json = json.loads(data)
    for entry in data_json:
        user_id = entry["user_id"]
        user_name = entry["display_name"]
        message = (
            f"Ngày mai ({tomorrow_str}) {user_name} muốn ăn như thế nào?\n"
            f"0️⃣ {choices['0']['text']}\n"
            f"1️⃣ {choices['1']['text']}\n"
            f"2️⃣ {choices['2']['text']}\n"
            f"3️⃣ {choices['3']['text']}\n"
            f"Nếu không chọn thì mặc định là **BUỔI TỐI** nhé!!\n"
            f"Hạn cuối chọn là 22h hôm nay nha!"
        )
        bot_app.send_message_to_user(user_id, message)
        print(f"Đã gửi tin nhắn đến user_id: {user_id}")


def load_family():
    DATA_FILE = "data/family.json"
    """Đọc file JSON (nếu chưa có thì trả về list rỗng)."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


TMPFILES_UPLOAD_URL = "https://tmpfiles.org/api/v1/upload"


def generate_qr_code(amount, content=""):
    """Gọi API VietQR, trả về chuỗi qrCode (EMV) hoặc None."""
    payload = {
        "bankAccount": "799999992004",
        "userBankName": "NGUYEN HAI MINH",
        "bankCode": "TCB",
        "amount": str(amount),
        "content": content
    }
    resp = requests.post(
        "https://api.vietqr.org/vqr/api/qr/generate/unauthenticated",
        json=payload,
        timeout=10
    )
    if resp.status_code == 200:
        return resp.json().get("qrCode")
    return None


def create_qr_image_file(qr_string, filename_prefix="qr"):
    """Tạo ảnh QR tạm, trả về đường dẫn file (PNG)."""
    img = qrcode.make(qr_string)
    tmp = tempfile.NamedTemporaryFile(
        suffix=".png", prefix=filename_prefix, delete=False)
    tmp_path = tmp.name
    tmp.close()
    img.save(tmp_path)
    return tmp_path


def upload_file_to_tmpfiles(file_path):
    """Upload file lên tmpfiles.org, trả về public URL hoặc None."""
    with open(file_path, "rb") as f:
        files = {"file": f}
        resp = requests.post(TMPFILES_UPLOAD_URL, files=files, timeout=20)

    print("Upload response:", resp.text)

    try:
        data = resp.json()
        # API format luôn là data → url
        print("Extracted URL:", data["data"]["url"])
        direct_url = data["data"]["url"].replace(
            "tmpfiles.org/", "tmpfiles.org/dl/")
        return direct_url
    except Exception:
        return None


def house_bill_message():
    """Tính toán và gửi hóa đơn nhà."""
    house_bill = 8000000
    users = load_family()
    each_user_pay = int(house_bill / 6)
    qr_string = generate_qr_code(each_user_pay, content="")
    file_path = create_qr_image_file(qr_string, filename_prefix="qr")
    uploaded_url = upload_file_to_tmpfiles(file_path)
    for user in users:
        user_name = user["display_name"]
        message_user = (
            f"👋 Chào {user_name},\n\n"
            f"🏡 Hóa đơn nhà tháng này là: {_format_vnd_thousands(house_bill)} VND\n"
            "-----------------------------------\n"
            f"💰 **Số tiền bạn cần thanh toán:** "
            f"➡️ {_format_vnd_thousands(each_user_pay)} VND\n\n"
        )

        bot_app.send_photo_to_user(
            user_id=user["user_id"], photo_url=uploaded_url, caption=message_user
        )

    print("Đã gửi hóa đơn nhà đến tất cả thành viên.")


def calculate_month_bill():
    electric_bill = 1084482
    water_bill = 178070
    junk_bill = 70000
    users = load_family()

    # extra_fee = 142000

    total_bill = electric_bill + water_bill + junk_bill
    each_user_pay = int(total_bill / 6)

    message = (
        "💡 *Hóa đơn tháng này*\n\n"
        f"⚡ Tiền điện: {_format_vnd_thousands(electric_bill)} VND\n"
        f"💧 Tiền nước: {_format_vnd_thousands(water_bill)} VND\n"
        f"🗑️ Tiền rác: {_format_vnd_thousands(junk_bill)} VND\n"
        # f"🏡 Tiền phát sinh (khu phố): {_format_vnd_thousands(extra_fee)} VND\n"
        "-----------------------------------\n"
        f"💰 **Tổng cộng: {_format_vnd_thousands(total_bill)} VND**"
    )

    qr_string = generate_qr_code(each_user_pay, content="")
    file_path = create_qr_image_file(
        qr_string, filename_prefix=f"qr")
    uploaded_url = upload_file_to_tmpfiles(file_path)
    for user in users:
        user_name = user["display_name"]
        message_user = (
            f"👋 Chào {user_name},\n\n"
            f"{message}\n"
            "-----------------------------------\n"
            f"🧍 **Số tiền bạn cần thanh toán:** "
            f"➡️ {_format_vnd_thousands(each_user_pay)} VND\n\n"
            f"🔔 Quét QR chuyển khoản nhé!!!"
        )

        bot_app.send_photo_to_user(
            user_id=user["user_id"], photo_url=uploaded_url, caption=message_user
        )
    print("Đã gửi hóa đơn tháng đến tất cả thành viên.")


def send_meal_schedule_to_Loan():
    with open(r"data/data.json", "r", encoding="utf-8") as f:
        data_json = json.loads(f.read())

    tomorrow = datetime.now() + timedelta(days=1)
    # tomorrow = datetime.now()
    tomorrow_str = tomorrow.strftime("%d/%m/%Y")

    ca_ngay = []
    bua_trua = []
    bua_toi = []

    for entry in data_json:
        if entry["date"] != tomorrow_str:
            continue

        name = entry["user_name"]
        choice = entry["choice"]

        if choice == "CẢ NGÀY":
            ca_ngay.append(f"• 👤 {name}")
        elif choice == "BUỔI TRƯA":
            bua_trua.append(f"• 👤 {name}")
        elif choice == "BUỔI TỐI":
            bua_toi.append(f"• 👤 {name}")

    message = f"🍽️ LỊCH ĂN NGÀY {tomorrow_str}\n━━━━━━\n"

    if ca_ngay:
        message += "🌞 CẢ NGÀY\n"
        message += "\n".join(ca_ngay) + "\n"

    if bua_trua:
        message += "🍚 BUỔI SÁNG\n"
        message += "\n".join(bua_trua) + "\n"

    if bua_toi:
        message += "🌙 BUỔI TỐI\n"
        message += "\n".join(bua_toi) + "\n"

    bot_app.send_message_to_user(
        "e58a3c15dc5935076c48",
        message
    )
    # bot_app.send_message_to_user(
    #     "fff1d6ab58e4b1bae8f5",
    #     message
    # )

    print("✅ Đã gửi lịch ăn (ẩn mục trống)")


def add_choice_evening_default_date_22h():
    """Thêm lựa chọn BUỔI TỐI mặc định cho những người chưa chọn lúc 22h hàng ngày."""
    all_data = load_data()
    tomorrow = datetime.now() + timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%d/%m/%Y")

    with open(r"data/users.json", "r", encoding="utf-8") as f:
        users_data = json.load(f)

    for entry in users_data:
        user_id = entry["user_id"]
        user_name = entry["display_name"]

        if not any(d["date"] == tomorrow_str and d["user_id"] == user_id for d in all_data):
            all_data.append({
                "date": tomorrow_str,
                "user_id": user_id,
                "user_name": user_name,
                "choice": choices["3"]["text"],
                "so_buoi": choices["3"]["so_buoi"]
            })
            bot_app.send_message_to_user(
                user_id,
                f"Bạn chưa chọn gì cho ngày mai, mình đã đặt mặc định là: {choices['3']['text']} nhé!"
            )

    save_data(all_data)
    print("Đã thêm lựa chọn mặc định cho những người chưa chọn.")


if __name__ == "__main__":
    # calculate_month_bill()
    # house_bill_message()
    send_meal_schedule_to_Loan()
    if not Config.DEBUG or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        scheduler = BackgroundScheduler()
        scheduler.add_job(send_daily_message, "cron", hour=21,
                          minute=42, timezone="Asia/Ho_Chi_Minh")
        scheduler.add_job(
            add_choice_evening_default_date_22h,
            "cron",
            hour=22,
            minute=0,
            timezone="Asia/Ho_Chi_Minh"
        )
        scheduler.add_job(
            send_meal_schedule_to_Loan,
            "cron",
            hour=22,
            minute=5,
            timezone="Asia/Ho_Chi_Minh"
        )
        scheduler.start()
        logging.info("🕒 Scheduler started (chạy mỗi 19:00 hằng ngày).")

    logging.info("🚀 Server đang chạy...")
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)
