"""
Watch-time and dwell-time controller.
Handles actual viewing behavior once a video is open.
Supports: standard videos, Shorts, livestreams, and livestream replays.
Weighted distribution: most views short, some medium, very few long.
"""
import asyncio
import random
import re
import time
from playwright.async_api import Page

from automation.interaction import (
    scroll_page, scroll_feed, move_mouse_to
)

# Weighted view-length tiers (short/medium/long)
_WATCH_WEIGHTS = [0.55, 0.30, 0.15]


def pick_watch_duration(min_sec: int, max_sec: int, style: str = "random") -> float:
    """
    Pick a watch duration using weighted tiers.
    style: 'short', 'medium', 'long', or 'random' (weighted).
    Some sessions skip or exit very early regardless of style.
    """
    # 8% chance of skipping entirely
    if random.random() < 0.08:
        return 0

    # 10% chance of a very brief peek (2–8s)
    if random.random() < 0.10:
        return random.uniform(2, 8)

    if style == "short":
        tier = "short"
    elif style == "medium":
        tier = "medium"
    elif style == "long":
        tier = "long"
    else:
        tier = random.choices(["short", "medium", "long"], weights=_WATCH_WEIGHTS)[0]

    span = max_sec - min_sec
    if tier == "short":
        return min_sec + span * random.uniform(0.05, 0.35)
    elif tier == "medium":
        return min_sec + span * random.uniform(0.35, 0.70)
    else:
        return min_sec + span * random.uniform(0.70, 1.0)


def _is_shorts_url(url: str) -> bool:
    return "/shorts/" in url


# ── Navigation ────────────────────────────────────────────────────────────────

async def navigate_to_video(
    page: Page,
    url: str,
    entry_path: str = "direct",
    search_keywords: str = None,
    logger=None,
) -> bool:
    """
    Navigate to the target video using the specified entry path.
    Returns True on success.
    """
    def log(msg):
        if logger:
            logger(msg)

    try:
        if entry_path == "home":
            await _navigate_via_home(page, url, log)

        elif entry_path == "search":
            if search_keywords:
                await _navigate_via_search(page, url, search_keywords, log)
            else:
                log("Search entry path selected but no keywords — navigating directly")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        elif entry_path == "suggested":
            await _navigate_via_suggested(page, url, log)

        elif entry_path == "channel":
            await _navigate_via_channel(page, url, log)

        elif entry_path == "playlist":
            await _navigate_via_playlist(page, url, log)

        elif entry_path == "notification":
            await _navigate_via_notification(page, url, log)

        else:
            log(f"Navigating directly to: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        await asyncio.sleep(random.uniform(1.5, 3.5))
        await _scroll_past_and_return(page)
        return True

    except Exception as e:
        log(f"Navigation error: {e}")
        return False


async def _scroll_past_and_return(page: Page):
    """Scroll past the video, pause, scroll back — simulates natural landing."""
    await asyncio.sleep(random.uniform(0.5, 1.5))
    if random.random() < 0.6:
        await scroll_page(page, "down", random.randint(150, 300))
        await asyncio.sleep(random.uniform(0.8, 2.0))
        await scroll_page(page, "up", random.randint(100, 250))
        await asyncio.sleep(random.uniform(0.3, 0.8))


async def _navigate_via_search(page: Page, target_url: str, keywords: str, log):
    """
    Go to YouTube search results for the given keywords,
    scroll through results, then click the target video if found.
    Falls back to direct navigation if the video isn't visible in results.
    """
    log(f"Entry path: search — '{keywords}'")
    encoded = keywords.replace(" ", "+")
    await page.goto(
        f"https://www.youtube.com/results?search_query={encoded}",
        wait_until="domcontentloaded",
        timeout=30000,
    )
    await asyncio.sleep(random.uniform(1.5, 3.0))

    # Scroll results as a human would scan them
    await scroll_feed(page, scrolls=random.randint(2, 4))
    await asyncio.sleep(random.uniform(0.8, 2.0))

    # Try to click the exact video from results
    clicked = await _click_target_in_page(page, target_url, log)
    if not clicked:
        log("Target not found in search results — navigating directly")
        await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)


async def _navigate_via_suggested(page: Page, target_url: str, log):
    """
    Simulate arriving via a suggested/related video:
    1. Open a random video from home.
    2. Watch briefly.
    3. Look for the target in the related sidebar; click it if found.
    4. Otherwise navigate directly (simulates clicking a notification/direct link).
    """
    log("Entry path: suggested — browsing home feed first")
    await page.goto("https://www.youtube.com", wait_until="domcontentloaded", timeout=20000)
    await asyncio.sleep(random.uniform(2.0, 4.0))
    await scroll_feed(page, scrolls=random.randint(1, 3))
    await asyncio.sleep(random.uniform(0.8, 2.0))

    opened = await _open_random_home_video(page, target_url, log)
    if opened:
        # Watch the intermediate video briefly, as if browsing
        await asyncio.sleep(random.uniform(8, 22))

        # Look for target in the related sidebar
        clicked = await _click_target_in_page(page, target_url, log)
        if clicked:
            log("Clicked target from related/suggested sidebar")
            return

    log("Target not in suggestions — navigating directly")
    await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)


async def _navigate_via_home(page: Page, target_url: str, log):
    """
    Arrive at the target video from the YouTube home feed.
    Browse the feed naturally, then click the target if it appears.
    If the target isn't in the feed (most of the time it won't be),
    navigate directly — simulating a user who was on the home page
    and then typed or clicked a link to the video.
    """
    log("Entry path: home feed")
    await page.goto("https://www.youtube.com", wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(random.uniform(2.0, 4.5))

    # Browse the feed — scroll, pause, look around
    await scroll_feed(page, scrolls=random.randint(2, 5))
    await asyncio.sleep(random.uniform(1.0, 2.5))

    # Try to find and click the target video from the feed
    clicked = await _click_target_in_page(page, target_url, log)
    if not clicked:
        # Not on the home feed — navigate directly after having browsed the feed
        log("Target not on home feed — navigating directly after browsing")
        await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)


async def _navigate_via_playlist(page: Page, target_url: str, log):
    """
    Arrive at the target video via a playlist.
    If the URL already contains a playlist (?list=), navigate there directly,
    scroll the playlist panel, then let autoplay or a click land on the video.
    Otherwise, go to the YouTube home feed, find a playlist in the grid,
    browse it briefly, then navigate to the target.
    """
    log("Entry path: playlist")

    # Case 1: target URL is itself a playlist or includes a list param
    if "list=" in target_url:
        await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(random.uniform(1.5, 3.0))
        # Scroll the playlist panel on the right
        try:
            panel = await page.query_selector("#secondary ytd-playlist-panel-renderer, #playlist")
            if panel:
                box = await panel.bounding_box()
                if box:
                    await page.mouse.move(
                        box["x"] + box["width"] * 0.5,
                        box["y"] + box["height"] * 0.5,
                    )
                    for _ in range(random.randint(2, 4)):
                        await page.mouse.wheel(0, random.randint(100, 250))
                        await asyncio.sleep(random.uniform(0.3, 0.8))
        except Exception:
            pass
        return

    # Case 2: land on YouTube home, find a playlist tile, browse it, then target
    await page.goto("https://www.youtube.com", wait_until="domcontentloaded", timeout=20000)
    await asyncio.sleep(random.uniform(2.0, 4.0))
    await scroll_feed(page, scrolls=random.randint(1, 3))
    await asyncio.sleep(random.uniform(0.8, 2.0))

    # Click a playlist tile from the home grid (they have an overlay count badge)
    try:
        playlist_tiles = await page.query_selector_all(
            "ytd-rich-item-renderer ytd-thumbnail-overlay-side-panel-renderer, "
            "ytd-playlist-renderer, a[href*='&list=']"
        )
        if playlist_tiles:
            tile = random.choice(playlist_tiles[:6])
            await tile.click()
            await asyncio.sleep(random.uniform(2.0, 4.5))
            await scroll_feed(page, scrolls=random.randint(1, 2))
    except Exception:
        pass

    # Now try to find the target in whatever page we're on
    clicked = await _click_target_in_page(page, target_url, log)
    if not clicked:
        log("Target not found in playlist — navigating directly")
        await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)


async def _navigate_via_channel(page: Page, target_url: str, log):
    """Navigate via the channel page: land on channel, scroll videos, then click target."""
    log("Entry path: channel")
    await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(random.uniform(2.0, 4.0))
    await scroll_feed(page, scrolls=random.randint(1, 2))


async def _navigate_via_notification(page: Page, target_url: str, log):
    """
    Simulate arriving from a YouTube push notification.
    Notifications deep-link the user directly to the video from outside YouTube
    (another tab, the OS notification tray, etc.).
    Behaviour: optionally idle on a neutral page first to mimic switching from
    another context, then land directly on the target URL.
    """
    log("Entry path: notification click — direct deep-link from outside YouTube")

    # ~50%: user was on a different page and clicked the notification
    if random.random() < 0.50:
        neutral_pages = [
            "https://www.google.com",
            "https://www.reddit.com",
            "https://twitter.com",
        ]
        try:
            await page.goto(
                random.choice(neutral_pages),
                wait_until="domcontentloaded",
                timeout=15000,
            )
            # Brief idle — the user notices the notification and clicks it
            await asyncio.sleep(random.uniform(1.5, 5.0))
        except Exception:
            pass  # neutral page failed, proceed directly

    # Land on the target — no search, no browse, straight to video
    await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)


async def _click_target_in_page(page: Page, target_url: str, log) -> bool:
    """
    Scan the current page for any link containing the target video ID and click it.
    Returns True if the video was clicked.
    """
    video_id_match = re.search(r"v=([^&]+)", target_url)
    if not video_id_match:
        return False
    video_id = video_id_match.group(1)

    try:
        links = await page.query_selector_all(f'a[href*="v={video_id}"]')
        if not links:
            return False
        link = links[0]
        box = await link.bounding_box()
        if box:
            tx = box["x"] + box["width"] * random.uniform(0.3, 0.7)
            ty = box["y"] + box["height"] * random.uniform(0.3, 0.7)
            await move_mouse_to(page, tx, ty)
            await asyncio.sleep(random.uniform(0.3, 0.8))
            await link.click()
            log("Clicked target video link on page")
            return True
    except Exception:
        pass
    return False


async def _open_random_home_video(page: Page, exclude_url: str, log) -> bool:
    """
    Click a random non-target video from the YouTube home feed.
    Returns True if a video was successfully opened.
    """
    video_id_match = re.search(r"v=([^&]+)", exclude_url)
    exclude_id = video_id_match.group(1) if video_id_match else None

    try:
        links = await page.query_selector_all("a#video-title, a.ytd-rich-grid-media")
        eligible = []
        for link in links[:15]:
            href = await link.get_attribute("href")
            if href and "/watch" in href:
                if exclude_id and exclude_id in href:
                    continue
                eligible.append(link)

        if not eligible:
            return False

        link = random.choice(eligible[:8])
        await link.click()
        await asyncio.sleep(random.uniform(1.5, 3.0))
        log("Opened intermediate video from home feed")
        return True
    except Exception:
        return False


# ── Watching ──────────────────────────────────────────────────────────────────

async def watch_video(page: Page, watch_seconds: float, campaign, logger=None) -> dict:
    """
    Dispatch to the correct watch handler based on content type / URL.
    Returns a result dict with what happened during the session.
    """
    def log(msg):
        if logger:
            logger(msg)

    result = {
        "watch_seconds": 0,
        "dwell_seconds": 0.0,
        "liked": False,
        "commented": False,
        "theater_mode": False,
        "seeked": False,
    }

    if watch_seconds < 2:
        log("Skipping video (very short watch time)")
        return result

    target_url = getattr(campaign, "target_url", "")
    target_type = getattr(campaign, "target_type", "video")

    try:
        if _is_shorts_url(target_url):
            result = await _watch_short(page, watch_seconds, campaign, result, log)
        elif target_type == "livestream":
            result = await _watch_livestream(page, watch_seconds, campaign, result, log)
        elif target_type == "channel":
            result = await _dwell_channel(page, watch_seconds, campaign, result, log)
        elif target_type == "playlist":
            result = await _dwell_playlist(page, watch_seconds, campaign, result, log)
        else:
            result = await _watch_standard(page, watch_seconds, campaign, result, log)

        # Rare rewatch (~3%): reload and watch a few more seconds
        if random.random() < 0.03:
            rewatch = random.uniform(5, 20)
            log(f"Rewatching briefly for {rewatch:.0f}s")
            try:
                await page.reload(wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(rewatch)
                result["watch_seconds"] = result["watch_seconds"] + rewatch
            except Exception:
                pass

    except Exception as e:
        log(f"Watch error: {e}")

    return result


async def _watch_standard(page: Page, watch_seconds: float, campaign, result: dict, log) -> dict:
    """Standard long-form video: seek, comments, theater/fullscreen, random pauses."""
    await page.wait_for_selector("video", timeout=15000)
    log(f"Watching for {watch_seconds:.0f}s")

    # Theater mode (~15%) or fullscreen (~5%)
    mode_roll = random.random()
    if mode_roll < 0.05:
        try:
            await page.keyboard.press("f")
            result["theater_mode"] = True
            await asyncio.sleep(random.uniform(0.3, 0.8))
        except Exception:
            pass
    elif mode_roll < 0.20:
        try:
            await page.click("button.ytp-size-button", timeout=3000)
            result["theater_mode"] = True
            await asyncio.sleep(random.uniform(0.3, 0.8))
        except Exception:
            pass

    elapsed = 0.0
    segment_size = random.uniform(8, 25)

    while elapsed < watch_seconds:
        remaining = watch_seconds - elapsed
        sleep_time = min(segment_size, remaining)
        await asyncio.sleep(sleep_time)
        elapsed += sleep_time

        if elapsed >= watch_seconds:
            break

        action = random.random()
        if action < 0.12:
            log("Scrolling comments")
            dwell_start = time.monotonic()
            await scroll_page(page, "down", random.randint(200, 400))
            await asyncio.sleep(random.uniform(2.0, 5.0))
            await scroll_page(page, "up", random.randint(150, 350))
            result["dwell_seconds"] += time.monotonic() - dwell_start
        elif action < 0.20:
            log("Seeking in video")
            await _seek_video(page)
            result["seeked"] = True
        elif action < 0.25:
            await move_mouse_to(
                page, random.uniform(300, 900), random.uniform(200, 500)
            )

        segment_size = random.uniform(8, 25)

    result["watch_seconds"] = elapsed

    if campaign.enable_likes and random.random() < 0.08:
        liked = await _like_video(page)
        result["liked"] = liked
        if liked:
            log("Liked the video")

    if campaign.enable_comments and campaign.comment_phrases and random.random() < 0.03:
        phrase = random.choice(campaign.comment_phrases)
        commented = await _post_comment(page, phrase)
        result["commented"] = commented
        if commented:
            log(f"Commented: {phrase}")

    return result


async def _watch_short(page: Page, watch_seconds: float, campaign, result: dict, log) -> dict:
    """
    YouTube Shorts — vertical scroll-based player.
    No seek bar; scrolling simulates swiping to next Short and back.
    """
    log(f"Watching Short for {watch_seconds:.0f}s")
    try:
        await page.wait_for_selector("video", timeout=10000)
    except Exception:
        pass

    elapsed = 0.0
    segment = random.uniform(4, 12)

    while elapsed < watch_seconds:
        remaining = watch_seconds - elapsed
        sleep_time = min(segment, remaining)
        await asyncio.sleep(sleep_time)
        elapsed += sleep_time

        if elapsed >= watch_seconds:
            break

        # ~15%: swipe to the next Short and back (simulates browsing Shorts feed)
        if random.random() < 0.15:
            await scroll_page(page, "down", random.randint(600, 900))
            await asyncio.sleep(random.uniform(1.0, 3.0))
            await scroll_page(page, "up", random.randint(600, 900))
            await asyncio.sleep(random.uniform(0.5, 1.5))

        segment = random.uniform(4, 12)

    result["watch_seconds"] = elapsed

    if campaign.enable_likes and random.random() < 0.06:
        liked = await _like_video(page)
        result["liked"] = liked
        if liked:
            log("Liked the Short")

    return result


async def _watch_livestream(page: Page, watch_seconds: float, campaign, result: dict, log) -> dict:
    """
    Livestream / replay — no seeking.
    Occasionally scrolls the live chat panel to simulate engagement.
    """
    log(f"Watching livestream for {watch_seconds:.0f}s")
    try:
        await page.wait_for_selector("video", timeout=15000)
    except Exception:
        pass

    elapsed = 0.0
    segment = random.uniform(15, 40)

    while elapsed < watch_seconds:
        remaining = watch_seconds - elapsed
        sleep_time = min(segment, remaining)
        await asyncio.sleep(sleep_time)
        elapsed += sleep_time

        if elapsed >= watch_seconds:
            break

        # ~20%: scroll live chat
        if random.random() < 0.20:
            try:
                dwell_start = time.monotonic()
                await scroll_page(page, "down", random.randint(80, 200))
                await asyncio.sleep(random.uniform(1.0, 3.0))
                result["dwell_seconds"] += time.monotonic() - dwell_start
            except Exception:
                pass

        # ~8%: move mouse around player area
        if random.random() < 0.08:
            await move_mouse_to(
                page, random.uniform(300, 900), random.uniform(200, 450)
            )

        segment = random.uniform(15, 40)

    result["watch_seconds"] = elapsed

    if campaign.enable_likes and random.random() < 0.05:
        liked = await _like_video(page)
        result["liked"] = liked
        if liked:
            log("Liked the livestream")

    return result


# ── Channel / Playlist dwell ──────────────────────────────────────────────────

async def _dwell_channel(page: Page, dwell_seconds: float, campaign, result: dict, log) -> dict:
    """
    Channel page — no continuous playback.
    Dwell time is measured as time spent browsing the channel's video grid.
    Spec: dwell time applies to channel pages separately from watch time.
    """
    log(f"Dwelling on channel page for {dwell_seconds:.0f}s")
    t_start = time.monotonic()

    # Scroll the channel's videos grid
    await scroll_feed(page, scrolls=random.randint(2, 4))
    await asyncio.sleep(random.uniform(1.5, 3.5))

    # ~50%: open one video briefly then go back
    elapsed = time.monotonic() - t_start
    if random.random() < 0.50 and elapsed < dwell_seconds - 15:
        try:
            links = await page.query_selector_all(
                "a#video-title, ytd-grid-video-renderer a#video-title-link"
            )
            if links:
                link = random.choice(links[:8])
                await link.click()
                await asyncio.sleep(random.uniform(1.5, 3.0))
                budget = dwell_seconds - (time.monotonic() - t_start) - 5
                brief = min(random.uniform(6, 20), max(0, budget))
                if brief > 0:
                    await asyncio.sleep(brief)
                    result["watch_seconds"] = brief
                await page.go_back()
                await asyncio.sleep(random.uniform(1.0, 2.5))
        except Exception:
            pass

    # Fill remaining dwell with more scrolling / idle
    remaining = dwell_seconds - (time.monotonic() - t_start)
    if remaining > 3:
        await scroll_feed(page, scrolls=random.randint(1, 3))
        await asyncio.sleep(random.uniform(1.0, min(remaining, 8.0)))

    result["dwell_seconds"] = time.monotonic() - t_start
    return result


async def _dwell_playlist(page: Page, dwell_seconds: float, campaign, result: dict, log) -> dict:
    """
    Playlist page — dwell time measured as time spent reviewing the playlist.
    Spec: dwell time applies to playlists separately from watch time.
    May open one or two videos from the list briefly.
    """
    log(f"Dwelling on playlist for {dwell_seconds:.0f}s")
    t_start = time.monotonic()

    # Scroll through playlist entries
    await scroll_feed(page, scrolls=random.randint(2, 5))
    await asyncio.sleep(random.uniform(1.0, 3.0))

    # ~60%: open a video from the playlist
    elapsed = time.monotonic() - t_start
    if random.random() < 0.60 and elapsed < dwell_seconds - 15:
        try:
            links = await page.query_selector_all(
                "ytd-playlist-video-renderer a#video-title, "
                "ytd-playlist-panel-video-renderer a"
            )
            if links:
                link = random.choice(links[:6])
                await link.click()
                await asyncio.sleep(random.uniform(1.5, 3.0))
                budget = dwell_seconds - (time.monotonic() - t_start) - 5
                brief = min(random.uniform(10, 35), max(0, budget))
                if brief > 0:
                    await asyncio.sleep(brief)
                    result["watch_seconds"] = brief
                await page.go_back()
                await asyncio.sleep(random.uniform(1.0, 2.0))
        except Exception:
            pass

    # Fill any remaining dwell
    remaining = dwell_seconds - (time.monotonic() - t_start)
    if remaining > 3:
        await scroll_feed(page, scrolls=random.randint(1, 2))
        await asyncio.sleep(random.uniform(1.0, min(remaining, 6.0)))

    result["dwell_seconds"] = time.monotonic() - t_start
    return result


# ── Player actions ────────────────────────────────────────────────────────────

async def _seek_video(page: Page):
    """Click a random position on the video progress bar."""
    try:
        bar = await page.query_selector(".ytp-progress-bar")
        if bar:
            box = await bar.bounding_box()
            if box:
                tx = box["x"] + box["width"] * random.uniform(0.1, 0.9)
                ty = box["y"] + box["height"] * 0.5
                await move_mouse_to(page, tx, ty)
                await asyncio.sleep(random.uniform(0.2, 0.5))
                await page.mouse.click(tx, ty)
    except Exception:
        pass


async def _like_video(page: Page) -> bool:
    """Click the like button."""
    try:
        like_btn = await page.query_selector(
            "button[aria-label*='like this video'], "
            "ytd-toggle-button-renderer:has(yt-icon[icon='like'])"
        )
        if like_btn:
            await like_btn.click()
            await asyncio.sleep(random.uniform(0.5, 1.2))
            return True
    except Exception:
        pass
    return False


async def _post_comment(page: Page, text: str) -> bool:
    """Post a short predefined comment on the video."""
    try:
        comment_box = await page.query_selector(
            "#simplebox-placeholder, #contenteditable-root"
        )
        if comment_box:
            await comment_box.click()
            await asyncio.sleep(random.uniform(0.5, 1.0))
            await page.keyboard.type(text, delay=random.uniform(80, 160))
            await asyncio.sleep(random.uniform(0.5, 1.5))
            submit = await page.query_selector("ytd-button-renderer#submit-button")
            if submit:
                await submit.click()
                return True
    except Exception:
        pass
    return False
