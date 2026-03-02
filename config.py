import os

from dotenv import load_dotenv

# Load .env từ thư mục hiện tại
load_dotenv()


class Config:
    TOKEN = os.getenv(
        "ZALO_BOT_TOKEN",
        "4489921799064848982:jBTBaoVEbewjlYnnqmmKthcofNWHCMybWBvJKYIMsLBijAMXyQcwwQJixNEKnZph"
    )
    WEBHOOK_URL = os.getenv(
        "WEBHOOK_URL")
    print(WEBHOOK_URL)
    SECRET_TOKEN = os.getenv("SECRET_TOKEN", "your_secret_token_here")
    DEBUG = False
    PORT = 8443
