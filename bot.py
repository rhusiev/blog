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
MAX_LENGTH = 6500


def sanitize_local_html(file_path, site_url):
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

    for math_tag in article.find_all(class_="arithmatex"):
        math_text = math_tag.get_text().strip()

        if math_text.startswith(r"\(") and math_text.endswith(r"\)"):
            math_text = math_text[2:-2].strip()

        elif math_text.startswith(r"\[") and math_text.endswith(r"\]"):
            math_text = math_text[2:-2].strip()

        if math_tag.name == "div":
            new_tag = soup.new_tag("pre")
        else:
            new_tag = soup.new_tag("code")

        new_tag.string = math_text
        math_tag.replace_with(new_tag)

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

    text = article.decode_contents().strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text, img_url


def post_to_telegram(title, text, link, img_url):
    message = f"<b>{title}</b>\n\n{text}\n<a href='{link}'>Читати в блозі</a>"

    if img_url and len(message) <= 1024:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        payload = {
            "chat_id": CHANNEL_ID,
            "photo": img_url,
            "caption": message,
            "parse_mode": "HTML",
        }
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            return True
        print(
            f"Photo post failed (Maybe image is inaccessible?). Telegram said: {response.text}"
        )
        print("Falling back to text-only message...")

    elif img_url:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={"chat_id": CHANNEL_ID, "photo": img_url},
        )

    if len(message) > MAX_LENGTH:
        message = message[:MAX_LENGTH] + f"...\n\n<a href='{link}'>Читати в блозі</a>"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    response = requests.post(url, data=payload)

    if response.status_code != 200:
        print(f"Text post failed! Telegram said: {response.text}")
        return False
    return True


def main():
    if not os.path.exists(RSS_FILE):
        return

    feed = feedparser.parse(RSS_FILE)
    posted = (
        set(open(STATE_FILE, "r").read().splitlines())
        if os.path.exists(STATE_FILE)
        else set()
    )
    new_posts = []

    for entry in reversed(feed.entries):
        link = entry.link
        if link in posted:
            continue

        title = entry.title

        parsed_link = urllib.parse.urlparse(link)
        parsed_site = urllib.parse.urlparse(SITE_URL)

        relative_path = urllib.parse.unquote(parsed_link.path)
        site_path = urllib.parse.unquote(parsed_site.path)

        if relative_path.startswith(site_path):
            relative_path = relative_path[len(site_path) :]

        local_file_path = os.path.join("site", relative_path.strip("/"), "index.html")

        if not os.path.exists(local_file_path):
            print(f"Warning: Could not find local HTML file for {link}")
            continue

        text, img_url = sanitize_local_html(local_file_path, SITE_URL)

        if post_to_telegram(title, text, link, img_url):
            new_posts.append(link)
            print(f"Successfully posted: {title}")

    if new_posts:
        with open(STATE_FILE, "a") as f:
            for post in new_posts:
                f.write(post + "\n")


if __name__ == "__main__":
    main()
