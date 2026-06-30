import os
import urllib.parse
import feedparser
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
SITE_URL = os.environ["SITE_URL"]
RSS_FILE = "site/feed_rss_created.xml"
STATE_FILE = "posted.txt"


def sanitize_html(html_content, site_url):
    """Converts standard HTML into Telegram-supported HTML and extracts images."""
    soup = BeautifulSoup(html_content, "html.parser")

    img_url = None
    img = soup.find("img")
    if img:
        img_url = urllib.parse.urljoin(site_url, img.get("src"))
        img.decompose()

    for a in soup.find_all("a"):
        if a.get("href"):
            a["href"] = urllib.parse.urljoin(site_url, a["href"])

    allowed_tags = [
        "b",
        "strong",
        "i",
        "em",
        "u",
        "ins",
        "s",
        "strike",
        "del",
        "a",
        "code",
        "pre",
    ]
    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            tag.unwrap()

    return str(soup).strip(), img_url


def main():
    if not os.path.exists(RSS_FILE):
        print("RSS feed not found. Skipping bot execution.")
        return

    feed = feedparser.parse(RSS_FILE)

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            posted = set(f.read().splitlines())
    else:
        posted = set()

    new_posts = []

    for entry in reversed(feed.entries):
        link = entry.link
        if link in posted:
            continue

        title = entry.title
        html_content = entry.summary

        text, img_url = sanitize_html(html_content, SITE_URL)

        message = f"<b>{title}</b>\n\n{text}\n\n<a href='{link}'>Read on Vault</a>"

        try:
            if img_url and len(message) <= 1024:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
                payload = {
                    "chat_id": CHANNEL_ID,
                    "photo": img_url,
                    "caption": message,
                    "parse_mode": "HTML",
                }
                r = requests.post(url, data=payload)
            else:
                if img_url:
                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                        data={"chat_id": CHANNEL_ID, "photo": img_url},
                    )

                if len(message) > 4000:
                    message = (
                        message[:4000] + f"...\n\n<a href='{link}'>Read on Vault</a>"
                    )

                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                payload = {
                    "chat_id": CHANNEL_ID,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                }
                r = requests.post(url, data=payload)

            r.raise_for_status()
            new_posts.append(link)
            print(f"Successfully posted: {title}")
        except Exception as e:
            print(f"Failed to post {link}: {e}")

    if new_posts:
        with open(STATE_FILE, "a") as f:
            for post in new_posts:
                f.write(post + "\n")


if __name__ == "__main__":
    main()
