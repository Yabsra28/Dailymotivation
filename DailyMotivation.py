import streamlit as st
import requests
import json
import logging
import schedule
import time
from datetime import datetime, timedelta, timezone
import uuid
import os
from typing import Dict, Optional, List
import random
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import textwrap
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pytz
import threading
from dotenv import load_dotenv

# Configuration
CLIENT_ID = "a48031889838a6c03a2ad322803be799a734cd15"
CLIENT_SECRET = "b1b01192191e46b51f699d444e01b7fa9ba1cf94"
REDIRECT_URI = "http://localhost:8000/oauth/callback"
BASE_URL = "https://3.basecampapi.com"
USED_QUOTES_FILE = "used_quotes.json"
REQUEST_TIMEOUT = 10
USER_AGENT = "MotivationalPoster (yabsrafekadu28@gmail.com)"
QUOTABLE_API_URL = "https://api.quotable.io/random?tags=leadership|success|wisdom||development|resilience|intelligence"
ZENQUOTES_API_URL = "https://zenquotes.io/api/quotes"
EAT_TZ = pytz.timezone("Africa/Nairobi")
ACCOUNT_ID = YOUR_ACCOUNT_ID  # Replace with your Basecamp account ID
PROJECT_ID = YOUR_PROJECT_ID  # Replace with your project ID
MESSAGE_BOARD_ID = YOUR_MESSAGE_BOARD_ID  # Replace with your message board ID
SCHEDULE_TIME = "06:00"  # Default schedule time (EAT)

# Fallback quotes
FALLBACK_QUOTES = [
    {"quote": "Great leaders don’t create followers; they inspire others to become leaders.", "author": "John Quincy Adams"},
    {"quote": "Resilience is not about avoiding obstacles, but about navigating through them with courage.", "author": "Sheryl Sandberg"},
    {"quote": "Success is not the absence of challenges, but the courage to push through them.", "author": "Oprah Winfrey"},
    {"quote": "Intelligence is the ability to adapt to change and learn from failure.", "author": "Stephen Hawking"},
    {"quote": "The greatest development comes from embracing challenges and learning from them.", "author": "Carol Dweck"}
]

# Logging setup
logging.basicConfig(filename="motivational_poster.log", level=logging.DEBUG,
                    format="%(asctime)s - %(levelname)s - %(message)s", filemode="a")

# Quote tracking
def load_used_quotes() -> List[Dict]:
    try:
        if os.path.exists(USED_QUOTES_FILE):
            with open(USED_QUOTES_FILE, "r", encoding="utf-8") as f:
                quotes = json.load(f)
                return quotes if isinstance(quotes, list) else []
        return []
    except Exception as e:
        logging.error(f"Failed to load used quotes: {e}")
        return []

def save_used_quote(quote: str, author: str):
    try:
        used_quotes = load_used_quotes()
        used_quotes.append({"quote": quote, "author": author})
        with open(USED_QUOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(used_quotes, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save used quote: {e}")

# HTTP retry
def retry_request(method_func, url, **kwargs):
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    try:
        response = session.request(method_func.__name__.split('.')[-1].upper(), url, **kwargs)
        return response
    except Exception as e:
        logging.error(f"Retry request failed for {url}: {e}")
        return None

# Token management
def save_access_token(access_token: str, refresh_token: str, expiry: datetime):
    try:
        st.secrets["BASECAMP_ACCESS_TOKEN"] = access_token
        st.secrets["BASECAMP_REFRESH_TOKEN"] = refresh_token
        st.secrets["BASECAMP_TOKEN_EXPIRY"] = expiry.isoformat()
        logging.info("Tokens saved to st.secrets")
    except Exception as e:
        logging.error(f"Failed to save tokens: {e}")
        st.error(f"Failed to save tokens: {e}")

def load_access_token() -> Optional[Dict]:
    try:
        if "BASECAMP_ACCESS_TOKEN" in st.secrets and "BASECAMP_TOKEN_EXPIRY" in st.secrets:
            expiry = datetime.fromisoformat(st.secrets["BASECAMP_TOKEN_EXPIRY"].replace('Z', '+00:00'))
            return {
                "access_token": st.secrets["BASECAMP_ACCESS_TOKEN"],
                "refresh_token": st.secrets.get("BASECAMP_REFRESH_TOKEN", ""),
                "expiry": expiry
            }
        return None
    except Exception as e:
        logging.error(f"Failed to load tokens: {e}")
        return None

def get_access_token() -> Optional[str]:
    token_data = load_access_token()
    if token_data and token_data.get("access_token"):
        if datetime.now(timezone.utc) < token_data["expiry"]:
            logging.debug("Using existing access token")
            return token_data["access_token"]
        elif token_data.get("refresh_token"):
            try:
                response = requests.post(
                    "https://launchpad.37signals.com/authorization/token.json",
                    data={
                        "type": "web_server",
                        "client_id": CLIENT_ID,
                        "client_secret": CLIENT_SECRET,
                        "redirect_uri": REDIRECT_URI,
                        "grant_type": "refresh_token",
                        "refresh_token": token_data["refresh_token"]
                    },
                    timeout=REQUEST_TIMEOUT
                )
                if response.ok:
                    token_data = response.json()
                    access_token = token_data.get("access_token")
                    refresh_token = token_data.get("refresh_token", token_data["refresh_token"])
                    expiry = datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 1209600))  # Default 14 days
                    save_access_token(access_token, refresh_token, expiry)
                    logging.info("Access token refreshed successfully")
                    return access_token
                else:
                    logging.error(f"Token refresh failed: {response.text}")
                    st.error("Token refresh failed. Please re-authenticate.")
            except Exception as e:
                logging.error(f"Error refreshing token: {e}")
                st.error(f"Error refreshing token: {e}")
    st.warning("No valid token. Please authenticate manually.")
    return None

# Quote and image functions
def get_random_quote() -> Dict:
    used_quotes = load_used_quotes()
    used_quote_set = {(q["quote"], q["author"]) for q in used_quotes}
    max_attempts = 5
    attempt = 0
    while attempt < max_attempts:
        try:
            response = retry_request(requests.get, QUOTABLE_API_URL, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
            if response.ok:
                data = response.json()
                quote = data.get("content")
                author = data.get("author")
                if quote and author and (quote, author) not in used_quote_set:
                    return {"quote": quote, "author": author}
            attempt += 1
        except Exception as e:
            logging.error(f"Error fetching quote from Quotable: {e}")
            attempt += 1
    try:
        response = retry_request(requests.get, ZENQUOTES_API_URL, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        if response.ok:
            data = response.json()
            available_quotes = [
                {"quote": q["q"], "author": q["a"]}
                for q in data
                if q.get("q") and q.get("a") and (q["q"], q["a"]) not in used_quote_set
            ]
            if available_quotes:
                return random.choice(available_quotes)
    except Exception as e:
        logging.error(f"Error fetching quote from ZenQuotes: {e}")
    available_fallbacks = [q for q in FALLBACK_QUOTES if (q["quote"], q["author"]) not in used_quote_set]
    if available_fallbacks:
        return random.choice(available_fallbacks)
    with open(USED_QUOTES_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)
    return random.choice(FALLBACK_QUOTES)

def get_random_photo_with_quote() -> Dict:
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    quote_data = get_random_quote()
    quote = quote_data["quote"]
    author = quote_data["author"]
    queries = ["river", "mountain", "waterfall", "forest", "lake"]
    query = random.choice(queries)
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=80&orientation=landscape"
    headers = {"Authorization": st.secrets["PEXELS_API_KEY"]}
    try:
        response = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.ok:
            data = response.json()
            photos = data.get("photos", [])
            nature_photos = [
                photo for photo in photos
                if photo.get("alt") and not any(keyword in photo["alt"].lower() for keyword in ["person", "people", "human", "crowd", "portrait"])
            ]
            if nature_photos:
                photo = random.choice(nature_photos)
                image_url = photo["src"]["large"]
                image_response = session.get(image_url, timeout=REQUEST_TIMEOUT)
                if image_response.ok:
                    image = Image.open(io.BytesIO(image_response.content)).convert("RGBA")
                    image = image.resize((800, 400), Image.LANCZOS)
                    overlay = Image.new("RGBA", image.size, (0, 0, 0, 128))
                    image = Image.alpha_composite(image, overlay)
                    draw = ImageDraw.Draw(image)
                    try:
                        font = ImageFont.truetype("Roboto-Bold.ttf", 30)
                        author_font = ImageFont.truetype("Roboto-Bold.ttf", 24)
                    except Exception:
                        font = ImageFont.load_default()
                        author_font = ImageFont.load_default()
                    wrapped_quote = textwrap.wrap(quote, width=25)
                    line_height = 40
                    total_text_height = len(wrapped_quote) * line_height + 30
                    y = (400 - total_text_height) // 2
                    for line in wrapped_quote:
                        text_width = draw.textlength(line, font=font)
                        x = (800 - text_width) // 2
                        draw.text((x + 2, y + 2), line, fill=(0, 0, 0, 200), font=font)
                        draw.text((x, y), line, fill="white", font=font)
                        y += line_height
                    author_text = f"- {author}"
                    author_width = draw.textlength(author_text, font=author_font)
                    x_author = (800 - author_width) // 2
                    draw.text((x_author + 2, y + 12), author_text, fill=(0, 0, 0, 200), font=author_font)
                    draw.text((x_author, y + 10), author_text, fill="white", font=author_font)
                    temp_image_path = f"temp_quote_image_{uuid.uuid4().hex}.png"
                    image.save(temp_image_path, "PNG", optimize=True, quality=85)
                    with open(temp_image_path, "rb") as f:
                        image_base64 = base64.b64encode(f.read()).decode()
                    return {"url": temp_image_path, "base64": image_base64, "quote": quote, "author": author}
        logging.error(f"Failed to fetch image from Pexels: {response.status_code}")
        st.error(f"Failed to fetch image from Pexels: {response.status_code}")
    except Exception as e:
        logging.error(f"Error fetching image from Pexels: {e}")
        st.error(f"Error fetching image from Pexels: {e}")
    return {"url": "https://via.placeholder.com/800x400?text=Famous+Quote", "base64": None, "quote": quote, "author": author}

def validate_image(image_path: str) -> bool:
    try:
        with Image.open(image_path) as img:
            img.verify()
        with Image.open(image_path) as img:
            img.load()
        file_size = os.path.getsize(image_path)
        if file_size > 5 * 1024 * 1024 or file_size == 0:
            return False
        return True
    except Exception as e:
        logging.error(f"Invalid image file {image_path}: {e}")
        return False

def upload_image_to_basecamp(account_id: int, access_token: str, image_path: str) -> Optional[str]:
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=3, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    if not validate_image(image_path):
        return None
    try:
        file_size = os.path.getsize(image_path)
        file_name = "quote_image.png"
        url = f"{BASE_URL}/{account_id}/attachments.json?name={urllib.parse.quote(file_name)}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": USER_AGENT,
            "Content-Type": "image/png",
            "Content-Length": str(file_size)
        }
        with open(image_path, "rb") as image_file:
            response = session.post(url, headers=headers, data=image_file.read(), timeout=REQUEST_TIMEOUT)
        if response.status_code == 201:
            data = response.json()
            return data.get("attachable_sgid")
        logging.error(f"Failed to upload image: {response.status_code} - {response.text[:500]}")
        return None
    except Exception as e:
        logging.error(f"Error uploading image: {e}")
        return None
    finally:
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                logging.error(f"Failed to clean up image {image_path}: {e}")

def post_message(account_id: int, project_id: int, message_board_id: int, access_token: str, image_url: Optional[str] = None, quote: Optional[str] = None, author: Optional[str] = None, test_mode: bool = False) -> bool:
    headers = {"Authorization": f"Bearer {access_token}", "User-Agent": USER_AGENT, "Content-Type": "application/json"}
    url = f"{BASE_URL}/{account_id}/buckets/{project_id}/message_boards/{message_board_id}/messages.json"
    temp_image_path = None
    try:
        if image_url and quote and author:
            final_image_url = image_url
            final_quote = quote
            final_author = author
        else:
            image_data = get_random_photo_with_quote()
            final_image_url = image_data["url"]
            final_quote = image_data["quote"]
            final_author = image_data["author"]
        attachable_sgid = None
        if final_image_url.startswith("temp_quote_image_"):
            temp_image_path = final_image_url
            attachable_sgid = upload_image_to_basecamp(account_id, access_token, final_image_url)
        if attachable_sgid:
            caption = f"{final_quote} - {final_author}"
            payload = {
                "subject": "Daily Inspiration",
                "content": f"<p>Selam Team,</p><bc-attachment sgid=\"{attachable_sgid}\" caption=\"{caption}\"></bc-attachment>",
                "status": "active"
            }
        else:
            payload = {
                "subject": "Daily Inspiration",
                "content": f"<p>Selam Team,</p><p>{final_quote} - {final_author}</p>",
                "status": "active"
            }
        response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        if response.status_code == 401:
            logging.error("Access token expired, attempting refresh")
            new_token = get_access_token()
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                response = requests.post(url, headers=headers, json=payload, timeout=10)
            else:
                logging.error("Failed to refresh token")
                return False
        if response.ok:
            save_used_quote(final_quote, final_author)
            logging.info("Message posted successfully")
            return True
        logging.error(f"Failed to post message: {response.status_code} - {response.text[:200]}")
        return False
    except Exception as e:
        logging.error(f"Error posting message: {str(e)}")
        return False
    finally:
        if temp_image_path and os.path.exists(temp_image_path):
            try:
                os.remove(temp_image_path)
            except:
                logging.error(f"Failed to remove temp image: {temp_image_path}")

def schedule_daily_post(account_id: int, project_id: int, message_board_id: int, schedule_time: str):
    schedule.clear()
    def job():
        if datetime.now(EAT_TZ).weekday() >= 5:
            logging.info(f"Skipping post on {datetime.now(EAT_TZ).strftime('%A')} (weekend)")
            return
        access_token = get_access_token()
        if access_token:
            post_message(account_id, project_id, message_board_id, access_token)
        else:
            logging.error("No valid token for scheduled post")
    try:
        datetime.strptime(schedule_time, "%H:%M")
        schedule.every().day.at(schedule_time).do(job)
        logging.info(f"Scheduled daily post at {schedule_time} EAT")
    except ValueError:
        logging.error(f"Invalid time format for scheduling: {schedule_time}")

# Streamlit App
def main():
    st.set_page_config(page_title="Basecamp Inspirational Quote Poster", layout="wide")
    st.markdown("""
    <style>
    .navbar { background-color: #1a73e8; padding: 15px; color: white; font-size: 24px; font-weight: bold; text-align: center; margin-bottom: 20px; border-radius: 8px; }
    .preview-box { border: 1px solid #e0e0e0; padding: 15px; border-radius: 8px; margin-bottom: 10px; background-color: #ffffff; }
    </style>
    <div class="navbar">Basecamp Inspirational Quote Poster</div>
    """, unsafe_allow_html=True)
    st.write("Automate daily inspirational quotes to your Basecamp message board.")

    # Initialize session state
    if 'scheduler_running' not in st.session_state:
        st.session_state.scheduler_running = False
    if 'preview_data' not in st.session_state:
        st.preview_data = None

    # Sidebar: Manual token input for testing
    st.sidebar.header("Settings")
    access_token_input = st.sidebar.text_input("Enter Basecamp Access Token (for testing)", type="password")
    refresh_token_input = st.sidebar.text_input("Enter Basecamp Refresh Token (for testing)", type="password")
    if st.sidebar.button("Save Tokens"):
        if access_token_input and refresh_token_input:
            save_access_token(access_token_input, refresh_token_input, datetime.now(timezone.utc) + timedelta(days=14))
            st.sidebar.success("Tokens saved. Scheduler will use these tokens.")

    # Test Post
    st.subheader("Test Post")
    if st.button("Test Post"):
        with st.spinner("Posting test message..."):
            access_token = get_access_token()
            if access_token:
                image_data = get_random_photo_with_quote()
                success = post_message(
                    ACCOUNT_ID, PROJECT_ID, MESSAGE_BOARD_ID,
                    access_token,
                    image_data["url"],
                    quote=image_data["quote"],
                    author=image_data["author"],
                    test_mode=True
                )
                if success:
                    st.success("Test post successful")
                    st.session_state.preview_data = {
                        "image_url": image_data["url"],
                        "base64": image_data["base64"],
                        "quote": image_data["quote"],
                        "author": image_data["author"]
                    }
                else:
                    st.error("Test post failed")
            else:
                st.error("No valid access token for for test test post")
    # Preview Post
    if st.session_state.preview_data:
        st.subheader("Post Preview")
        if st.session_state.preview_data["base64"]:
            st.markdown(f"""
            <div class="preview-box">
                <strong>Message:</strong> Selam Team,<br>
                <strong>Image:</strong><br>
                <img src="data:image/png;base64,{st.session_state.preview_data['base64']}" alt="Quote Image" style="max-width:100%;">
            </div>
            """, unsafe_html=True)
        else:
            st.markdown(f"""
            <div class="preview-box">
                <strong>Message:</strong> Selam Team,<br>
                <strong>Image:</strong><br>
                <img src="{st.session_state.preview_data['image_url']}" alt="Quote Image" style="max-width:100%;">
            </div>
            """, unsafe_allow_html=True)

    # Scheduler
    st.subheader("Daily Scheduler")
    if not st.session_state.scheduler_running:
        access_token = get_access_token()
        if access_token:
            try:
                datetime.strptime(SCHEDULE_TIME, "%H:%M")
                st.info(f"Starting scheduler at {SCHEDULE_TIME} EAT (Mon–Fri)")
                scheduler_thread = threading.Thread(
                    target=schedule_daily_post,
                    args=(ACCOUNT_ID, PROJECT_ID, MESSAGE_BOARD_ID, SCHEDULE_TIME),
                    daemon=True
                )
                scheduler_thread.start()
                st.session_state.scheduler_running = True
                logging.info("Scheduler started")
            except ValueError:
                st.error(f"Invalid time format: {SCHEDULE_TIME}")
                logging.error(f"Invalid time format: {SCHEDULE_TIME}")
        else:
            st.error("No valid access token. Please save tokens in settings.")
            logging.error("No valid token for scheduler")
    else:
        st.info(f"Scheduler running at {SCHEDULE_TIME} EAT")

if __name__ == "__main__":
    main()
