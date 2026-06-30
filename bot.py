import os
import urllib.parse
import feedparser
import requests
from bs4 import BeautifulSoup
import re

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
SITE_URL = os.environ["SITE_URL"]

RSS_FILE = "site/feed_rss_created.xml"
STATE_FILE = "posted.txt"


def sanitize_local_html(file_path, site_url):
    """Reads the actual built HTML file instead of the RSS summary."""
    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    article = soup.find("article", class_="md-content__inner")
    if not article:
        return "", None

    img_url = None
    img = article.find("img")
    if img:
        img_url = urllib.parse.urljoin(site_url, img.get("src"))
        img.decompose()

    h1 = article.find("h1")
    if h1:
        h1.decompose()

    for br in article.find_all("br"):
        br.replace_with("\n")
    for p in article.find_all("p"):
        p.append("\n\n")
        p.unwrap()

    for a in article.find_all("a"):
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
    for tag in article.find_all(True):
        if tag.name not in allowed_tags:
            tag.unwrap()

    text = str(article).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text, img_url


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

        parsed_link = urllib.parse.urlparse(link)
        parsed_site = urllib.parse.urlparse(SITE_URL)

        relative_path = parsed_link.path
        if relative_path.startswith(parsed_site.path):
            relative_path = relative_path[len(parsed_site.path) :]

        relative_path = relative_path.strip("/")

        local_file_path = os.path.join("site", relative_path, "index.html")

        if not os.path.exists(local_file_path):
            print(f"Warning: Could not find local HTML file for {link}")
            continue

        text, img_url = sanitize_local_html(local_file_path, SITE_URL)

        message = f"<b>{title}</b>\n\n{text}\n<a href='{link}'>Read on Vault</a>"

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
