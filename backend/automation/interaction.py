"""
Human-like interaction engine.
Simulates realistic mouse movement, scrolling, pauses, and typing.
Imperfect by design — real humans aren't smooth or consistent.
"""
import asyncio
import random
import math
from playwright.async_api import Page


# ── Mouse Movement ────────────────────────────────────────────────────────────

def _bezier_points(x0: float, y0: float, x1: float, y1: float, steps: int = 20):
    """
    Generate points along a quadratic bezier curve between two coordinates.
    Control point is randomly offset from the midpoint to create natural curves.
    """
    mid_x = (x0 + x1) / 2 + random.uniform(-80, 80)
    mid_y = (y0 + y1) / 2 + random.uniform(-60, 60)
    points = []
    for i in range(steps + 1):
        t = i / steps
        # Quadratic bezier formula
        px = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * mid_x + t ** 2 * x1
        py = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * mid_y + t ** 2 * y1
        points.append((px, py))
    return points


async def move_mouse_to(page: Page, x: float, y: float):
    """
    Move mouse to (x, y) along a curved path with micro-pauses and slight overshoot.
    """
    current = await page.evaluate("() => ({ x: window._mouseX || 0, y: window._mouseY || 0 })")
    cx, cy = current.get("x", 0), current.get("y", 0)

    # Occasionally overshoot and correct
    overshoot = random.random() < 0.3
    if overshoot:
        ox = x + random.uniform(-15, 15)
        oy = y + random.uniform(-10, 10)
        points = _bezier_points(cx, cy, ox, oy, steps=random.randint(15, 25))
        for px, py in points:
            await page.mouse.move(px, py)
            if random.random() < 0.1:
                await asyncio.sleep(random.uniform(0.01, 0.04))
        await asyncio.sleep(random.uniform(0.05, 0.12))
        # Correct to target
        points = _bezier_points(ox, oy, x, y, steps=random.randint(5, 10))
    else:
        points = _bezier_points(cx, cy, x, y, steps=random.randint(15, 30))

    for px, py in points:
        await page.mouse.move(px, py)
        if random.random() < 0.08:
            await asyncio.sleep(random.uniform(0.008, 0.025))

    # Track mouse position in page context
    await page.evaluate(f"() => {{ window._mouseX = {x}; window._mouseY = {y}; }}")


async def click_element(page: Page, selector: str, timeout: int = 5000):
    """Click an element with human-like mouse movement and small position jitter."""
    try:
        el = await page.wait_for_selector(selector, timeout=timeout)
        if not el:
            return False
        box = await el.bounding_box()
        if not box:
            return False

        # Click slightly off-center
        tx = box["x"] + box["width"] * random.uniform(0.2, 0.8)
        ty = box["y"] + box["height"] * random.uniform(0.2, 0.8)

        await move_mouse_to(page, tx, ty)
        await asyncio.sleep(random.uniform(0.08, 0.25))
        await page.mouse.click(tx, ty)
        return True
    except Exception:
        return False


async def hover_element(page: Page, selector: str, duration: float = None):
    """Hover over an element and pause."""
    try:
        el = await page.wait_for_selector(selector, timeout=3000)
        if not el:
            return
        box = await el.bounding_box()
        if not box:
            return
        tx = box["x"] + box["width"] * random.uniform(0.3, 0.7)
        ty = box["y"] + box["height"] * random.uniform(0.3, 0.7)
        await move_mouse_to(page, tx, ty)
        pause = duration if duration else random.uniform(0.5, 2.5)
        await asyncio.sleep(pause)
    except Exception:
        pass


# ── Scrolling ─────────────────────────────────────────────────────────────────

async def scroll_page(page: Page, direction: str = "down", amount: int = None, variable: bool = True):
    """
    Scroll the page. Amount is in pixels.
    Variable mode adds random pauses and speed changes mid-scroll.
    """
    if amount is None:
        amount = random.randint(200, 600)

    delta = amount if direction == "down" else -amount
    steps = random.randint(3, 8)
    step_size = delta / steps

    for _ in range(steps):
        jitter = random.uniform(0.7, 1.3) if variable else 1.0
        await page.mouse.wheel(0, step_size * jitter)
        await asyncio.sleep(random.uniform(0.05, 0.25))

        # Occasional micro-pause mid-scroll
        if variable and random.random() < 0.15:
            await asyncio.sleep(random.uniform(0.3, 1.2))


async def scroll_feed(page: Page, scrolls: int = None):
    """
    Scroll a feed (home, search results) with realistic behavior:
    - Variable speed
    - Occasional reverse scroll
    - Pauses to "read"
    """
    count = scrolls if scrolls else random.randint(3, 8)
    for i in range(count):
        await scroll_page(page, "down", random.randint(250, 500))
        await asyncio.sleep(random.uniform(0.4, 1.8))

        # Occasionally scroll back up a bit
        if random.random() < 0.2:
            await scroll_page(page, "up", random.randint(80, 200))
            await asyncio.sleep(random.uniform(0.3, 0.8))

        # Longer pause to "read" occasionally
        if random.random() < 0.25:
            await asyncio.sleep(random.uniform(1.5, 4.0))


# ── Pauses ────────────────────────────────────────────────────────────────────

async def think_pause():
    """Short thinking pause between actions."""
    await asyncio.sleep(random.uniform(0.3, 1.2))


async def long_pause():
    """Longer pause simulating distraction or reading."""
    await asyncio.sleep(random.uniform(2.0, 7.0))


async def micro_pause():
    """Very short pause within an action sequence."""
    await asyncio.sleep(random.uniform(0.05, 0.2))


# ── Typing ────────────────────────────────────────────────────────────────────

async def type_text(page: Page, selector: str, text: str):
    """Type text with variable speed and occasional typo correction."""
    try:
        await click_element(page, selector)
        await asyncio.sleep(random.uniform(0.2, 0.5))
        for char in text:
            await page.keyboard.type(char, delay=random.uniform(60, 180))
            # Rare extra pause between words
            if char == " " and random.random() < 0.1:
                await asyncio.sleep(random.uniform(0.2, 0.5))
    except Exception:
        pass
