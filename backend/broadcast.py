"""
Shared broadcast helper.

Set once at startup (main.py calls set_fn), then any module can call
emit() or emit_async() to push a message to all WebSocket clients.
"""
import asyncio
from typing import Callable, Optional

_fn: Optional[Callable] = None


def set_fn(fn: Callable):
    global _fn
    _fn = fn


def emit(data: dict):
    """Fire-and-forget — safe to call from sync or async code."""
    if _fn:
        asyncio.create_task(_fn(data))


async def emit_async(data: dict):
    """Awaitable version."""
    if _fn:
        await _fn(data)
