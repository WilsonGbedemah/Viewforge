"""
Session warm-up module.
Every session must begin with realistic browsing before targeting the campaign URL.
No fixed order or timing — intentionally unpredictable.
"""
import asyncio
import random
from playwright.async_api import Page

from automation.interaction import (
    scroll_feed, hover_element, think_pause, long_pause, micro_pause,
    move_mouse_to, scroll_page
)


YOUTUBE_HOME = "https://www.youtube.com"
YOUTUBE_TRENDING = "https://www.youtube.com/feed/trending"


async def warmup_session(page: Page, logger=None) -> bool:
    """
    Perform a realistic warm-up browsing session.
    Returns True if warm-up completed successfully.
    """
    def log(msg):
        if logger:
            logger(msg)

    try:
        # Navigate to YouTube home
        log("Warm-up: navigating to YouTube home")
        await page.goto(YOUTUBE_HOME, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(random.uniform(1.5, 3.5))

        # Pick a random warm-up sequence
        actions = _random_warmup_sequence()
        for action in actions:
            await action(page, log)
            await asyncio.sleep(random.uniform(0.8, 2.5))

        log("Warm-up: complete")
        return True

    except Exception as e:
        log(f"Warm-up error: {e}")
        return False


def _random_warmup_sequence():
    """Build a randomized warm-up action list."""
    pool = [
        _browse_home_feed,
        _hover_thumbnails,
        _open_and_close_video,
        _visit_channel_page,
        _scroll_and_idle,
    ]
    # Pick 2–4 actions in random order, no duplicates
    count = random.randint(2, 4)
    return random.sample(pool, min(count, len(pool)))


async def _browse_home_feed(page: Page, log):
    log("Warm-up: browsing home feed")
    await scroll_feed(page, scrolls=random.randint(2, 5))


async def _hover_thumbnails(page: Page, log):
    log("Warm-up: hovering thumbnails")
    try:
        thumbnails = await page.query_selector_all("ytd-rich-item-renderer, ytd-compact-video-renderer")
        if not thumbnails:
            return
        sample = random.sample(thumbnails, min(len(thumbnails), random.randint(2, 5)))
        for thumb in sample:
            try:
                box = await thumb.bounding_box()
                if box:
                    tx = box["x"] + box["width"] * random.uniform(0.2, 0.8)
                    ty = box["y"] + box["height"] * random.uniform(0.2, 0.8)
                    await move_mouse_to(page, tx, ty)
                    await asyncio.sleep(random.uniform(0.5, 2.0))
            except Exception:
                pass
    except Exception:
        pass


async def _open_and_close_video(page: Page, log):
    """Briefly open a random video then go back."""
    log("Warm-up: briefly opening a video")
    try:
        links = await page.query_selector_all("a#video-title, a.ytd-rich-grid-media")
        if not links:
            return

        link = random.choice(links[:10])
        href = await link.get_attribute("href")
        if href and "/watch" in href:
            await link.click()
            watch_time = random.uniform(4, 18)  # just a brief peek
            await asyncio.sleep(watch_time)
            await page.go_back()
            await asyncio.sleep(random.uniform(1.0, 2.5))
    except Exception:
        pass


async def _visit_channel_page(page: Page, log):
    """Navigate to a channel page without interacting."""
    log("Warm-up: visiting a channel page")
    try:
        channel_links = await page.query_selector_all("a.yt-simple-endpoint[href*='/@'], a.yt-simple-endpoint[href*='/channel/']")
        if not channel_links:
            return
        link = random.choice(channel_links[:8])
        href = await link.get_attribute("href")
        if href:
            if not href.startswith("http"):
                href = "https://www.youtube.com" + href
            await page.goto(href, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(random.uniform(3.0, 8.0))
            await scroll_feed(page, scrolls=random.randint(1, 3))
            await page.go_back()
            await asyncio.sleep(random.uniform(1.0, 2.0))
    except Exception:
        pass


async def _scroll_and_idle(page: Page, log):
    """Scroll down and just sit idle — simulating a distracted user."""
    log("Warm-up: idle scrolling")
    await scroll_page(page, "down", random.randint(300, 700))
    await asyncio.sleep(random.uniform(4.0, 10.0))
    # Maybe scroll back up
    if random.random() < 0.4:
        await scroll_page(page, "up", random.randint(200, 400))
