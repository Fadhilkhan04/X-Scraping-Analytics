
import argparse
import re
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright


DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CDP_URL = "http://127.0.0.1:9222"


def parse_count(value):
    if not value:
        return None

    match = re.search(r"([\d,.]+)\s*([KMB]?)", value, re.I)

    if not match:
        return None

    number = float(match.group(1).replace(",", ""))
    suffix = match.group(2).upper()

    multiplier = {
        "": 1,
        "K": 1000,
        "M": 1000000,
        "B": 1000000000
    }

    return int(number * multiplier[suffix])


def get_metric(article, testids):

    for testid in testids:
        try:
            button = article.locator(
                f'[data-testid="{testid}"]'
            ).first

            if button.count() == 0:
                continue

            label = button.get_attribute("aria-label") or ""
            text = button.inner_text(timeout=1500) or ""

            value = parse_count(label)

            if value is None:
                value = parse_count(text)

            if value is not None:
                return value

        except Exception:
            continue

    return None


def extract_post(article, username):

    try:
        # Extract actual post text
        text_element = article.locator(
            '[data-testid="tweetText"]'
        ).first

        if text_element.count() > 0:
            text = text_element.inner_text().strip()
        else:
            # Fallback for different X page layouts
            candidates = article.locator("div[lang]")

            if candidates.count() == 0:
                return None

            text = candidates.first.inner_text().strip()

        if not text:
            return None

        # Extract post URL and ID
        links = article.locator(
            'a[href*="/status/"]'
        ).evaluate_all(
            "(els) => els.map(e => e.href)"
        )

        post_url = next(
            (
                link.split("?")[0]
                for link in links
                if "/status/" in link
            ),
            None
        )

        if not post_url:
            return None

        match = re.search(r"/status/(\d+)", post_url)

        if not match:
            return None

        post_id = match.group(1)

        # Extract timestamp
        created_at = None

        time_element = article.locator("time").first

        if time_element.count() > 0:
            created_at = time_element.get_attribute("datetime")

        # Extract engagement
        likes = get_metric(article, ["like", "unlike"])
        reposts = get_metric(article, ["retweet", "unretweet"])
        replies = get_metric(article, ["reply"])
        quotes = get_metric(article, ["quoteTweet"])
        views = get_metric(article, ["analytics"])

        return {
            "post_id": post_id,
            "username": username,
            "text": text,
            "created_at": created_at,
            "likes": likes,
            "reposts": reposts,
            "replies": replies,
            "quotes": quotes,
            "views": views,
            "post_url": post_url
        }

    except Exception as error:
        print("Extraction error:", repr(error))
        return None


def collect_profile(username, max_posts=100):

    username = username.strip().lstrip("@")

    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", username):
        raise ValueError("Invalid X username.")

    collected = {}

    with sync_playwright() as p:

        print("\nConnecting to existing Chrome...")

        browser = p.chromium.connect_over_cdp(CDP_URL)

        if not browser.contexts:
            raise RuntimeError("No Chrome browser context found.")

        context = browser.contexts[0]

        # Find an existing X tab
        page = None

        for tab in context.pages:
            if "x.com" in tab.url:
                page = tab
                break

        if page is None:
            page = context.new_page()

        target_url = f"https://x.com/{username}"

        print("Opening:", target_url)

        page.goto(
            target_url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(5000)

        print("Page title:", page.title())
        print("Current URL:", page.url)

        # Verify that the requested profile is open
        if f"x.com/{username.lower()}" not in page.url.lower():
            raise RuntimeError(
                "The requested profile did not load. "
                "Check the browser and try again later."
            )

        # =================================
        # COLLECT POSTS
        # =================================

        attempt = 0
        no_new_posts = 0

        while (
            len(collected) < max_posts
            and no_new_posts < 8
        ):

            previous_count = len(collected)

            articles = page.locator("article")

            for i in range(articles.count()):

                post = extract_post(
                    articles.nth(i),
                    username
                )

                if post:
                    collected[post["post_id"]] = post

                if len(collected) >= max_posts:
                    break

            current_count = len(collected)
            attempt += 1

            print(
                f"Scroll {attempt}: "
                f"{current_count}/{max_posts} posts collected"
            )

            if current_count == previous_count:
                no_new_posts += 1
            else:
                no_new_posts = 0

            if current_count >= max_posts:
                break

            # Scroll the timeline
            page.mouse.move(800, 650)
            page.mouse.wheel(0, 1400)

            page.wait_for_timeout(3000)

        # Do not close the connected Chrome browser.
        # The user's existing session must remain open.

    # =====================================
    # SAVE CSV
    # =====================================

    if not collected:
        raise RuntimeError(
            "No posts collected. Check whether X rendered "
            "the timeline and whether access is restricted."
        )

    df = pd.DataFrame(list(collected.values()))

    df["created_at"] = pd.to_datetime(
        df["created_at"],
        errors="coerce",
        utc=True
    )

    filename = DATA_DIR / f"{username}_posts.csv"

    df.to_csv(
        filename,
        index=False,
        encoding="utf-8-sig"
    )

    print("\n========== COLLECTION REPORT ==========")

    print("Username:", username)
    print("Posts collected:", len(df))
    print("Valid timestamps:", df["created_at"].notna().sum())

    for column in ["likes", "reposts", "replies", "quotes", "views"]:
        print(
            f"{column}: "
            f"{df[column].notna().sum()}/{len(df)} available"
        )

    print("\nSaved:", filename)

    print("\nPreview:")

    print(
        df[
            [
                "post_id",
                "created_at",
                "text",
                "likes",
                "reposts",
                "replies"
            ]
        ].head(10).to_string(index=False)
    )

    return filename


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="X Analytics Collector"
    )

    parser.add_argument(
        "username",
        help="X username without @"
    )

    parser.add_argument(
        "--max-posts",
        type=int,
        default=100
    )

    args = parser.parse_args()

    collect_profile(
        args.username,
        args.max_posts
    )
