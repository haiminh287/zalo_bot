from decimal import Decimal, ROUND_FLOOR
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import asyncio
import logging
import re
import tempfile
from turtle import update
import qrcode
import requests
from zalo_bot.ext import CommandHandler, MessageHandler, filters

from bot.models import User, Message
from bot.user_manager import UserManager
from bot.message_manager import MessageManager
from services.gg_calendar_api import GGCalendarAPI
import datetime as dt
import os
import json


TZ = "Asia/Ho_Chi_Minh"


user_manager = UserManager()
message_manager = MessageManager()


def load_data():
    DATA_FILE = "data/data.json"
    """Đọc file JSON (nếu chưa có thì trả về list rỗng)."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def load_users():
    DATA_FILE = "data/users.json"
    """Đọc file JSON (nếu chưa có thì trả về list rỗng)."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def load_users_bad():
    DATA_FILE = "data/users_badmintion.json"
    """Đọc file JSON (nếu chưa có thì trả về list rỗng)."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


async def start(update, context):
    user = update.effective_user

    # Lưu thông tin người dùng
    user_obj = User.from_zalo({
        "id": user.id,
        "display_name": user.display_name,
        "is_bot": user.is_bot
    })
    user_manager.save_user(user_obj)

    await update.message.reply_action("typing")
    await asyncio.sleep(0.5)
    await update.message.reply_text(f"Xin chào {user.display_name}! Tôi là bot Zalo của bạn 🤖")


PAIR_RE = re.compile(r'''
    (?P<key>\w+)                # key
    \s*(?:=|:)\s*              # = hoặc :
    (?P<val>                   # value:
        "(?:[^"\\]|\\.)*"      #   "…có thể có dấu :"…
        |\[[^\]]*\]            #   [a;b;c]
        |[^,\s]+               #   hoặc 1 token không chứa dấu cách, dấu phẩy
    )
''', re.VERBOSE)


def _parse_kv_args(s: str) -> dict:
    out = {}
    for m in PAIR_RE.finditer(s):
        k = m.group("key").strip().lower()
        v = m.group("val").strip()
        if len(v) >= 2 and v[0] == v[-1] == '"':
            v = v[1:-1]  # bỏ dấu "
        out[k] = v
    # chuẩn hoá một số field
    if "attendees" in out and out["attendees"]:
        raw = out["attendees"].strip()
        if raw.startswith("[") and raw.endswith("]"):
            raw = raw[1:-1]
        out["attendees"] = [x.strip()
                            for x in re.split(r"[;,]", raw) if x.strip()]
    if "remind" in out:
        try:
            out["remind"] = int(out["remind"])
            print(
                f"✅ Parsed remind value: {out['remind']} (type: {type(out['remind'])})")
        except Exception as e:
            print(f"❌ Failed to parse remind: {out['remind']}, error: {e}")
            pass
    print("📋 Full parsed args:", out)
    return out


def _ensure_tz(dt_or_str: str) -> str:
    # Hỗ trợ 'YYYY-MM-DDTHH:MM' hoặc 'YYYY-MM-DDTHH:MM:SS' (+/- tz)
    # Trả về ISO string với timezone Asia/Ho_Chi_Minh (+07:00)
    try:
        d = dt.datetime.fromisoformat(dt_or_str)
    except ValueError:
        d = dt.datetime.strptime(dt_or_str, "%Y-%m-%dT%H:%M")

    # Nếu không có timezone, coi như là giờ Việt Nam (UTC+7)
    if d.tzinfo is None:
        # Trả về string với timezone +07:00
        return d.strftime("%Y-%m-%dT%H:%M:%S") + "+07:00"

    return d.isoformat()


def _build_times(data: dict, default_tz: str = TZ):
    if "start" not in data or "end" not in data:
        raise ValueError(
            "Bạn phải truyền cả `start` và `end` (không dùng duration).")

    sdt = _ensure_tz(data["start"])
    edt = _ensure_tz(data["end"])
    tz = data.get("tz", default_tz)
    # sdt và edt đã là ISO string rồi
    return sdt, edt, tz


async def create_event(update, context):
    text = (update.message.text or "").strip()
    args_str = text.split(" ", 1)[1].strip() if " " in text else ""

    if not args_str:
        await update.message.reply_text(
            "Cú pháp:\n"
            "/create_event summary=\"Tiêu đề\" start=\"2025-11-07T10:00\" end=\"2025-11-07T11:00\""
        )
        return

    data = _parse_kv_args(args_str)

    if "summary" not in data or "start" not in data or "end" not in data:
        await update.message.reply_text("Thiếu `summary`, `start` hoặc `end`.")
        return

    client = GGCalendarAPI.service_account(
        r"C:\Users\MINH\Desktop\ZaloBot\services\service_account.json",
        subject=None,
        default_calendar_id="minhht2k4@gmail.com",
    )

    try:
        start_iso, end_iso, tz = _build_times(data)

        # Lấy giá trị remind, nếu không có thì để None (không dùng giá trị mặc định)
        remind_value = data.get("remind")
        print(
            f"🔔 Remind value being passed to API: {remind_value} (type: {type(remind_value)})")

        ev = client.create_event(
            summary=data["summary"],
            start=start_iso,
            end=end_iso,
            time_zone=tz,
            location=data.get("location"),
            description=data.get("desc"),
            attendees=data.get("attendees"),
            reminders_minutes=remind_value,
            recurrence_rrule=data.get("recur"),
        )
        await update.message.reply_text(
            f"✅ Đã tạo sự kiện:\n• {data['summary']}\n🔗 {ev['htmlLink']}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")


async def create_events(update, context):
    text = update.message.text or ""
    lines = [ln for ln in text.splitlines() if ln.strip().startswith("-")]

    if not lines:
        await update.message.reply_text(
            "Cú pháp:\n"
            "/create_events\n"
            "- summary=\"Đi học\" start=\"2025-11-07T10:00\" end=\"2025-11-07T11:00\"\n"
            "- summary=\"Gym\" start=\"2025-11-07T18:00\" end=\"2025-11-07T19:30\""
        )
        return

    client = GGCalendarAPI.service_account(
        r"C:\Users\MINH\Desktop\ZaloBot\services\service_account.json",
        subject=None,
        default_calendar_id="minhht2k4@gmail.com",
    )

    oks, fails = [], []

    for ln in lines:
        data = _parse_kv_args(ln)
        if "summary" not in data or "start" not in data or "end" not in data:
            fails.append(f"• {ln.strip()} -> Thiếu summary/start/end")
            continue
        try:
            start_iso, end_iso, tz = _build_times(data)
            ev = client.create_event(
                summary=data["summary"],
                start=start_iso,
                end=end_iso,
                time_zone=tz,
                location=data.get("location"),
                description=data.get("desc"),
                attendees=data.get("attendees"),
                reminders_minutes=data.get("remind"),
                recurrence_rrule=data.get("recur"),
            )
            oks.append(f"• {data['summary']} — {ev['htmlLink']}")
        except Exception as e:
            fails.append(f"• {data['summary']}: ❌ {e}")

    result = ""
    if oks:
        result += "✅ Tạo thành công:\n" + "\n".join(oks) + "\n"
    if fails:
        result += "\n❌ Lỗi:\n" + "\n".join(fails)
    await update.message.reply_text(result)

# -------------------------------
# 🔹 Lệnh /help
# -------------------------------


async def help_command(update, context):
    user = update.effective_user

    help_text = (
        f"Xin chào {user.display_name} 👋\n\n"
        "Tôi có thể giúp bạn:\n"
        "• /start - Bắt đầu trò chuyện\n"
        "• /help - Hiển thị hướng dẫn\n"
        "• /create_events - Tạo nhiều sự kiện lịch Google Calendar\n"
        "• /check - Kiểm tra danh sách ăn hôm nay 🍽\n"
        "• /update + Tuấn + CẢ NGÀY + 29/01/2026\n"
        "• /create_event - Tạo sự kiện lịch Google Calendar ,Cú Pháp : /create_event summary=\"Gửi mẫu xác nhận thực tập\" start=\"2025-12-27T07:15\" end=\"2025-12-27T10:00\" \n"
        "• Gửi bất kỳ tin nhắn nào, tôi sẽ phản hồi lại 💬"
    )

    await update.message.reply_action("typing")
    await asyncio.sleep(0.8)
    await update.message.reply_text(help_text)


# -------------------------------
# 🔹 Xử lý tin nhắn thường
# -------------------------------
async def check_meal(update, context):
    # Nếu user nhập: /check-02/03/2026
    print("Received command:", update.message.text)
    try:
        command = update.message.text
        print("Received command:", command)

        if "-" in command:
            date_part = command.split("-")[1].strip()
            target_date = datetime.strptime(date_part, "%d/%m/%Y")
        else:
            # Nếu chỉ nhập /check → lấy hôm nay
            target_date = datetime.now()

        today_str = target_date.strftime("%d/%m/%Y")

    except Exception:
        await update.message.reply_text(
            "❌ Sai định dạng!\nVí dụ đúng:\n/check-02/03/2026"
        )
        return

    all_data = load_data()
    today_meals = [e for e in all_data if e["date"] == today_str]

    if not today_meals:
        await update.message.reply_text(
            f"📅 {today_str}\n\n❌ Không có ai đăng ký ăn."
        )
        return

    ca_ngay = []
    buoi_trua = []
    buoi_toi = []
    khong_an = []

    for e in today_meals:
        if e["choice"] == "CẢ NGÀY":
            ca_ngay.append(e)
        elif e["choice"] == "BUỔI TRƯA":
            buoi_trua.append(e)
        elif e["choice"] == "BUỔI TỐI":
            buoi_toi.append(e)
        else:
            khong_an.append(e)

    message = f"📅 DANH SÁCH ĂN ({today_str})\n\n"

    if ca_ngay:
        message += "🍱 CẢ NGÀY\n"
        for i, e in enumerate(ca_ngay, 1):
            message += f"{i}. {e['user_name']}\n"
        message += "\n"

    if buoi_trua:
        message += "🌞 BUỔI TRƯA\n"
        for i, e in enumerate(buoi_trua, 1):
            message += f"{i}. {e['user_name']}\n"
        message += "\n"

    if buoi_toi:
        message += "🌙 BUỔI TỐI\n"
        for i, e in enumerate(buoi_toi, 1):
            message += f"{i}. {e['user_name']}\n"
        message += "\n"

    if khong_an:
        message += "❌ KHÔNG ĂN\n"
        for i, e in enumerate(khong_an, 1):
            message += f"{i}. {e['user_name']}\n"
        message += "\n"

    await update.message.reply_text(message)


def save_data(data):
    """Ghi danh sách dữ liệu vào file JSON."""
    DATA_FILE = "data/data.json"
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


CHOICE_TO_SO_BUOI = {
    "CẢ NGÀY": 2,
    "BUỔI TRƯA": 1,
    "BUỔI TỐI": 1,
    "KHÔNG ĂN": 0
}


async def update_meal(update, context):
    text = update.message.text

    # /update + Tuấn + CẢ NGÀY + 29/01/2026
    pattern = r"^/update\s*\+\s*(.+?)\s*\+\s*(.+?)\s*\+\s*(\d{2}/\d{2}/\d{4})$"
    match = re.match(pattern, text, re.IGNORECASE)

    if not match:
        await update.message.reply_text(
            "❌ Sai cú pháp\n\nVí dụ:\n/update + Tuấn + CẢ NGÀY + 29/01/2026"
        )
        return

    name_keyword = match.group(1).strip()
    choice = match.group(2).strip().upper()
    date_str = match.group(3)

    if choice not in CHOICE_TO_SO_BUOI:
        await update.message.reply_text(
            "❌ Loại bữa ăn không hợp lệ\n"
            "Chỉ nhận: CẢ NGÀY / BUỔI TRƯA / BUỔI TỐI / KHÔNG ĂN"
        )
        return

    so_buoi = CHOICE_TO_SO_BUOI[choice]
    data = load_data()

    # tìm user theo tên (contains)
    matched_users = [
        e for e in data
        if name_keyword.lower() in e["user_name"].lower()
    ]

    if not matched_users:
        await update.message.reply_text(f"❌ Không tìm thấy user chứa tên: {name_keyword}")
        return

    # lấy user đầu tiên làm chuẩn
    user = matched_users[0]
    user_id = user["user_id"]
    user_name = user["user_name"]

    updated = False

    for e in data:
        if e["date"] == date_str and e["user_id"] == user_id:
            e["choice"] = choice
            e["so_buoi"] = so_buoi
            updated = True
            break

    if not updated:
        data.append({
            "date": date_str,
            "user_id": user_id,
            "user_name": user_name,
            "choice": choice,
            "so_buoi": so_buoi
        })

    save_data(data)

    await update.message.reply_text(
        f"✅ Đã cập nhật:\n"
        f"👤 {user_name}\n"
        f"📅 {date_str}\n"
        f"🍽 {choice} ({so_buoi} bữa)"
    )


async def echo(update, context):
    msg = update.message
    user_data = msg.from_user
    users = load_users_bad() or []

    # --- kiểm tra user có tồn tại chưa ---
    exists = any(u["user_id"] == user_data.id for u in users)
    # if user_data.id == "4bb10f95b4c15d9f04d0":
    #     # await update.message.reply_action("typing")
    #     # await asyncio.sleep(0.8)
    #     await update.message.reply_text("Minh đẹp trai vcl")
    #     return
    if not exists:
        # Thêm user mới
        new_user = {
            "user_id": user_data.id,
            "display_name": user_data.display_name,
            "is_bot": user_data.is_bot
        }

        users.append(new_user)

        # 🔥 Ghi lại toàn bộ mảng users (KHÔNG ghi đè mất dữ liệu cũ)
        with open("data/users_badmintion.json", "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=4)

    else:
        # User đã tồn tại → lưu qua UserManager
        user_obj = User.from_zalo({
            "id": user_data.id,
            "display_name": user_data.display_name,
            "is_bot": user_data.is_bot
        })
        user_manager.save_user(user_obj)

    # 🔸 Lưu thông tin tin nhắn
    # msg_obj = Message(
    #     message_id=msg.message_id,
    #     user_id=user_data.id if user_data else "unknown",
    #     text=msg.text or "",
    #     timestamp=int(msg.date.timestamp() * 1000),
    # )
    # message_manager.save_message(msg_obj)

    # # 🔸 Phản hồi
    # await msg.reply_action("typing")
    # await asyncio.sleep(1)
    # await msg.reply_text(f"Bạn vừa nói: {msg.text}")


# -------------------------------
# 🔹 Hàm đăng ký tất cả handler
# # -------------------------------


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


async def summarize_the_number_of_meals(update, context):
    """Hàm tổng hợp số bữa ăn và tính tiền cho mỗi người trong tháng hiện tại."""
    text = update.message.text or ""

    # Lấy tổng tiền từ lệnh, ví dụ: /summary 5000000
    parts = text.split()
    if len(parts) < 2:
        await update.message.reply_text(
            "❌ Vui lòng nhập tổng tiền!\n"
            "Cú pháp: /summary <tổng_tiền>\n"
            "Ví dụ: /summary 5000000"
        )
        return

    try:
        total_meal_cost = Decimal(parts[1])
    except Exception:
        await update.message.reply_text("❌ Tổng tiền không hợp lệ!")
        return

    all_data = load_data()

    if not all_data:
        await update.message.reply_text("❌ Chưa có dữ liệu bữa ăn!")
        return

    # Lấy tháng và năm hiện tại
    now = datetime.now()
    current_month = now.month-1
    current_year = now.year

    summary = {}
    total_sessions = 0
    start_dt = None
    end_dt = None

    # Lọc dữ liệu theo tháng hiện tại
    for entry in all_data:
        try:
            d = _parse_date(entry["date"])
            # Chỉ lấy dữ liệu của tháng hiện tại
            if d.month != current_month or d.year != current_year:
                continue

            user_name = entry["user_name"]
            so_buoi = int(entry["so_buoi"])
            summary[user_name] = summary.get(user_name, 0) + so_buoi
            total_sessions += so_buoi

            start_dt = d if start_dt is None else min(start_dt, d)
            end_dt = d if end_dt is None else max(end_dt, d)
        except Exception:
            pass

    if total_sessions == 0:
        await update.message.reply_text(
            f"❌ Chưa có dữ liệu bữa ăn cho tháng {current_month}/{current_year}!"
        )
        return

    start_day = _format_date(start_dt) if start_dt else ""
    end_day = _format_date(end_dt) if end_dt else ""

    # Tính tiền mỗi buổi
    amount_per_session = total_meal_cost / Decimal(total_sessions)

    # Tính tiền cho từng người (làm tròn xuống nghìn)
    items = []
    sum_floor = Decimal("0")

    for user, meals in summary.items():
        raw = Decimal(meals) * amount_per_session
        base_thousands = (raw / Decimal("1000")
                          ).to_integral_value(rounding=ROUND_FLOOR)
        base = base_thousands * Decimal("1000")
        frac = raw - base
        sum_floor += base
        items.append([user, meals, base, frac])

    # Phân phối số tiền dư
    remainder = total_meal_cost - sum_floor
    steps = int((remainder / Decimal("1000")).to_integral_value()
                ) if remainder > 0 else 0

    items.sort(key=lambda x: x[3], reverse=True)
    for i in range(steps):
        items[i % len(items)][2] += Decimal("1000")

    items.sort(key=lambda x: x[0].lower())

    # Tạo báo cáo
    lines = [f"📊 Tổng hợp tiền ăn tháng {current_month}/{current_year}"]
    lines.append(f"📅 Từ {start_day} đến {end_day}")
    lines.append(
        f"💰 Tổng tiền: {_format_vnd_thousands(int(total_meal_cost))} VND")
    lines.append(f"🍽️ Tổng số buổi: {total_sessions} buổi")
    lines.append(
        f"💵 Giá mỗi buổi: {_format_vnd_thousands(int(amount_per_session))} VND\n")

    # Thêm chi tiết từng người vào báo cáo chung
    for user, meals, amount, _ in items:
        lines.append(
            f"• {user}: {meals} bữa → {_format_vnd_thousands(int(amount))} VND"
        )

    report_text = "\n".join(lines)
    await update.message.reply_text(report_text)

    try:
        users = load_users()
        user_dict = {u["display_name"]: u["user_id"] for u in users}

        for user, meals, amount, _ in items:
            user_id = user_dict.get(user)
            print("User ID for", user, "is", user_id)
            if user_id:
                personal_report = (
                    f"📊 Báo cáo tiền ăn cá nhân - Tháng {current_month}/{current_year}\n"
                    f"📅 Từ {start_day} đến {end_day}\n"
                    f"💰 Tổng tiền: {_format_vnd_thousands(int(total_meal_cost))} VND\n\n"
                    f"👤 Họ tên: {user}\n"
                    f"🍽️ Số buổi ăn: {meals} buổi\n"
                    f"💵 Giá mỗi buổi: {_format_vnd_thousands(int(amount_per_session))} VND\n"
                    f"💰 Tổng tiền cần thanh toán: {_format_vnd_thousands(int(amount))} VND"
                )
                qr_string = generate_qr_code(amount, content="")
                qr_image_path = create_qr_image_file(qr_string)
                uploaded_url = upload_file_to_tmpfiles(qr_image_path)
                await context.bot.send_photo(chat_id=user_id, photo=uploaded_url, caption=personal_report)
    except Exception as e:
        logging.error(f"Lỗi khi gửi báo cáo cá nhân: {e}")


def _format_vnd_thousands(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _parse_date(d: str) -> datetime:
    return datetime.strptime(d, "%d/%m/%Y")


def _format_date(d: datetime) -> str:
    return d.strftime("%d/%m/%Y")


def register_all_handlers():
    """
    Trả về danh sách handler để đăng ký vào dispatcher
    """
    handlers = [
        CommandHandler("start", start),
        CommandHandler("help", help_command),
        CommandHandler("create_event", create_event),   # 1 sự kiện
        CommandHandler("create_events", create_events),  # nhiều sự kiện
        CommandHandler("summarize_meals", summarize_the_number_of_meals),
        CommandHandler("check", check_meal),
        CommandHandler("update", update_meal),
        MessageHandler(filters.TEXT & ~filters.COMMAND, echo)
    ]
    logging.info(
        "✅ Đã đăng ký các handler: /start, /help, /create_event, text message")
    return handlers
