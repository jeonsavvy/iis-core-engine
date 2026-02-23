import os
import time
import httpx
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Try loading .env from parent directory if running from scripts/
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(env_path)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
LOCAL_WEBHOOK_URL = os.environ.get("LOCAL_WEBHOOK_URL", "http://127.0.0.1:8000/api/v1/telegram/webhook")

if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN is not set.")
    exit(1)

def run_polling():
    offset = None
    logger.info(f"Starting Telegram long-polling. Forwarding updates to {LOCAL_WEBHOOK_URL}")
    
    with httpx.Client(timeout=60.0) as client:
        while True:
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
                params = {"timeout": 30, "allowed_updates": ["message", "edited_message"]}
                if offset:
                    params["offset"] = offset

                response = client.get(url, params=params)
                if response.status_code >= 500:
                    logger.error(f"Telegram server error: {response.status_code}")
                    time.sleep(5)
                    continue
                
                data = response.json()
                if not data.get("ok"):
                    logger.error(f"Telegram API error: {data}")
                    time.sleep(5)
                    continue

                for update in data.get("result", []):
                    update_id = update["update_id"]
                    offset = update_id + 1
                    
                    headers = {"Content-Type": "application/json"}
                    if TELEGRAM_WEBHOOK_SECRET:
                        headers["X-Telegram-Bot-Api-Secret-Token"] = TELEGRAM_WEBHOOK_SECRET
                        
                    logger.info(f"Forwarding update {update_id} to {LOCAL_WEBHOOK_URL}")
                    
                    try:
                        res = client.post(LOCAL_WEBHOOK_URL, json=update, headers=headers)
                        if res.status_code >= 400:
                            logger.error(f"Failed to forward update {update_id}. Status: {res.status_code} Body: {res.text}")
                        else:
                            logger.info(f"Update {update_id} successfully forwarded. Response: {res.json()}")
                    except Exception as he:
                        logger.error(f"Could not reach local webhook ({LOCAL_WEBHOOK_URL}): {he}")
                        
            except httpx.ReadTimeout:
                # Expected when no new messages arrive during the timeout period
                pass
            except Exception as e:
                logger.error(f"Polling error: {e}")
                time.sleep(5)

if __name__ == "__main__":
    run_polling()
