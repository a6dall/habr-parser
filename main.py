import sys
import time
import json
import os
from typing import List, Dict
import requests
from requests.adapters import HTTPAdapter, Retry
from lxml import html
from bs4 import BeautifulSoup

HABR_URL = "https://habr.com/ru/all/"
JSON_FILE = "articles.json"


def make_session() -> requests.Session:
    """Создаёт сессию с ретраями и заголовками."""
    s = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD", "OPTIONS")
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "ru,en;q=0.9",
    })
    return s


def fetch_html(url: str, session: requests.Session) -> str:
    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text


def parse_main_page(page_html: str) -> List[Dict]:
    """Парсит список статей с главной страницы."""
    tree = html.fromstring(page_html)
    nodes = tree.xpath("//article//h2/a")
    results = []
    for a in nodes:
        title = (a.text_content() or "").strip()
        href = a.get("href") or ""
        if href.startswith("/"):
            href = "https://habr.com" + href
        if title and href:
            results.append({"title": title, "url": href})
    return results


def get_article_data(article_html: str) -> Dict:
    """Парсит текст, лайки и комментарии со страницы статьи."""
    soup = BeautifulSoup(article_html, "html.parser")

    # Текст статьи
    body_divs = soup.select("div.article-formatted-body")
    paragraphs = []
    for div in body_divs:
        for p in div.find_all(["p", "li"]):
            text = p.get_text(strip=True)
            if text:
                paragraphs.append(text)
    text_full = "\n".join(paragraphs)

    # Лайки
    likes_tag = soup.select_one("span[data-test-id='votes-meter-counter']") \
                 or soup.select_one("span[class*='vote']")
    likes = likes_tag.get_text(strip=True) if likes_tag else "0"

    # Комментарии
    comments_tag = soup.select_one("span[data-test-id='comments-counter']") \
                     or soup.select_one("span[class*='comment']")
    comments = comments_tag.get_text(strip=True) if comments_tag else "0"

    return {
        "text": text_full,
        "likes": likes,
        "comments": comments
    }


def load_existing_data() -> List[Dict]:
    """Загружает данные из JSON, если он есть."""
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_data(data: List[Dict]):
    """Сохраняет данные в JSON."""
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main(limit: int = 5):
    session = make_session()

    existing_data = load_existing_data()
    existing_urls = {item["url"] for item in existing_data}

    main_html = fetch_html(HABR_URL, session)
    articles = parse_main_page(main_html)[:limit]

    new_articles = []

    for art in articles:
        if art["url"] in existing_urls:
            print(f"⏩ Пропущено (уже есть): {art['title']}")
            continue

        try:
            print(f"📥 Парсим: {art['title']}")
            article_html = fetch_html(art["url"], session)
            extra_data = get_article_data(article_html)

            article_data = {
                "title": art["title"],
                "url": art["url"],
                "text": extra_data["text"],
                "likes": extra_data["likes"],
                "comments": extra_data["comments"]
            }
            new_articles.append(article_data)
        except Exception as e:
            print(f"❌ Ошибка при обработке {art['url']}: {e}")

        time.sleep(1)

    if new_articles:
        all_data = existing_data + new_articles
        save_data(all_data)
        print(f"✅ Добавлено новых статей: {len(new_articles)}")
    else:
        print("📭 Новых статей нет.")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    main(limit)
