from __future__ import annotations

from urllib.parse import urlparse

import requests
import trafilatura
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

import json
from datetime import datetime

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/154.0.0.0 Safari/537.36"
)

def extract_metadata(soup: BeautifulSoup) -> dict:
    """
    Extract author, publication date, modified date,
    and publisher using common metadata standards.
    """

    author = []
    published_at = None
    modified_at = None
    publisher = None

    # --------------------------------
    # 1. JSON-LD structured metadata
    # --------------------------------

    for script in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"}
    ):
        try:
            data = json.loads(
                script.string or script.get_text()
            )

            # Some sites return a list or @graph
            objects = data if isinstance(data, list) else [data]

            for obj in objects:

                if isinstance(obj, dict) and "@graph" in obj:
                    objects.extend(
                        x for x in obj["@graph"]
                        if isinstance(x, dict)
                    )

                if not isinstance(obj, dict):
                    continue

                # Author
                obj_author = obj.get("author")

                if isinstance(obj_author, dict):
                    name = obj_author.get("name")
                    if name:
                        author.append(name)

                elif isinstance(obj_author, list):
                    for a in obj_author:
                        if isinstance(a, dict):
                            name = a.get("name")
                            if name:
                                author.append(name)
                        elif isinstance(a, str):
                            author.append(a)

                elif isinstance(obj_author, str):
                    author.append(obj_author)

                # Publication date
                if not published_at:
                    published_at = (
                        obj.get("datePublished")
                        or obj.get("dateCreated")
                    )

                # Modified date
                if not modified_at:
                    modified_at = obj.get("dateModified")

                # Publisher
                obj_publisher = obj.get("publisher")

                if isinstance(obj_publisher, dict):
                    publisher = obj_publisher.get("name")

                elif isinstance(obj_publisher, str):
                    publisher = obj_publisher

        except (json.JSONDecodeError, TypeError):
            continue

    # --------------------------------
    # 2. Meta tags fallback
    # --------------------------------

    if not author:

        for selector in [
            ("name", "author"),
            ("property", "article:author"),
        ]:

            tag = soup.find(
                "meta",
                attrs={selector[0]: selector[1]}
            )

            if tag and tag.get("content"):
                author.append(
                    tag["content"].strip()
                )

    if not published_at:

        for key in [
            "article:published_time",
            "datePublished",
            "publishdate",
        ]:

            tag = soup.find(
                "meta",
                attrs={
                    "property": key
                }
            ) or soup.find(
                "meta",
                attrs={
                    "name": key
                }
            )

            if tag and tag.get("content"):
                published_at = tag["content"].strip()
                break

    if not modified_at:

        for key in [
            "article:modified_time",
            "dateModified",
        ]:

            tag = soup.find(
                "meta",
                attrs={
                    "property": key
                }
            ) or soup.find(
                "meta",
                attrs={
                    "name": key
                }
            )

            if tag and tag.get("content"):
                modified_at = tag["content"].strip()
                break

    # --------------------------------
    # 3. Remove duplicate authors
    # --------------------------------

    author = list(dict.fromkeys(
        a.strip()
        for a in author
        if a and a.strip()
    ))

    return {
        "author": author,
        "published_at": published_at,
        "modified_at": modified_at,
        "publisher": publisher,
    }

def extract_article(html: str, final_url: str) -> dict:
    """
    Extract structured article information from HTML.
    """

    soup = BeautifulSoup(html, "html.parser")
    
    metadata = extract_metadata(soup)

    # Remove obvious noise
    for tag in soup([
        "script",
        "style",
        "noscript",
        "svg",
        "iframe",
    ]):
        tag.decompose()

    # -----------------------------
    # TITLE
    # -----------------------------

    title = ""

    og_title = soup.find(
        "meta",
        attrs={"property": "og:title"}
    )

    if og_title and og_title.get("content"):
        title = og_title["content"].strip()

    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)

    # -----------------------------
    # DESCRIPTION
    # -----------------------------

    description = ""

    meta_description = soup.find(
        "meta",
        attrs={"name": "description"}
    )

    if meta_description and meta_description.get("content"):
        description = meta_description["content"].strip()

    if not description:
        og_description = soup.find(
            "meta",
            attrs={"property": "og:description"}
        )

        if og_description and og_description.get("content"):
            description = og_description["content"].strip()

    # -----------------------------
    # ARTICLE TEXT
    # -----------------------------

    article_text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
        output_format="txt",
    )

    # Fallback to paragraph extraction
    if not article_text:

        paragraphs = []

        for p in soup.find_all("p"):

            text = p.get_text(" ", strip=True)

            if len(text) >= 30:
                paragraphs.append(text)

        article_text = "\n\n".join(paragraphs)

    article_text = (article_text or "").strip()

    # -----------------------------
    # IMAGE
    # -----------------------------

    image = None

    og_image = soup.find(
        "meta",
        attrs={"property": "og:image"}
    )

    if og_image and og_image.get("content"):
        image = og_image["content"].strip()

    # -----------------------------
    # DOMAIN
    # -----------------------------

    domain = urlparse(final_url).netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    return {
    "url": final_url,
    "domain": domain,
    "title": title,
    "description": description,

    "author": metadata["author"],
    "published_at": metadata["published_at"],
    "modified_at": metadata["modified_at"],
    "publisher": metadata["publisher"],

    "article_text": article_text,
    "image": image,
    "word_count": len(article_text.split()),
}


def fetch_with_requests(url: str) -> tuple[str, str]:
    """
    First attempt: normal HTTP request.
    """

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,image/avif,"
            "image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=15,
        allow_redirects=True,
    )

    response.raise_for_status()

    return response.text, response.url


def fetch_with_browser(url: str) -> tuple[str, str]:
    """
    Fallback: real Chromium browser using Playwright.
    """

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            user_agent=USER_AGENT,
            locale="en-US",
            viewport={
                "width": 1366,
                "height": 768,
            },
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        page = context.new_page()

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        # Give JS-rendered pages a moment to populate
        page.wait_for_timeout(2000)

        html = page.content()
        final_url = page.url

        browser.close()

        return html, final_url


def scrape_article(url: str) -> dict:

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must use http or https")

    if not parsed.netloc:
        raise ValueError("Invalid URL")

    # -----------------------------------
    # ATTEMPT 1: NORMAL HTTP
    # -----------------------------------

    try:

        html, final_url = fetch_with_requests(url)

        article = extract_article(
            html,
            final_url,
        )

        # If extraction was successful, return it
        if article["article_text"]:
            article["fetch_method"] = "requests"
            return article

    except requests.RequestException:
        pass

    # -----------------------------------
    # ATTEMPT 2: REAL BROWSER
    # -----------------------------------

    try:

        html, final_url = fetch_with_browser(url)

        article = extract_article(
            html,
            final_url,
        )

        if article["article_text"]:

            article["fetch_method"] = "playwright"

            return article

    except Exception as exc:

        raise RuntimeError(
            f"Browser extraction failed: {exc}"
        ) from exc

    raise RuntimeError(
        "The page was fetched, but no article content "
        "could be extracted."
    )