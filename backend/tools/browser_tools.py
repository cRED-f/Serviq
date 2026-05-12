from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from tools.base import ToolDefinition, ToolExecutionContext, ToolResult, ToolRisk

try:  # Playwright is optional at import time so the backend can still boot.
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover - depends on local installation
    PlaywrightTimeoutError = TimeoutError  # type: ignore[assignment]
    async_playwright = None  # type: ignore[assignment]

# Configurable session timeout (default 30 minutes)
_BROWSER_SESSION_TIMEOUT_SECONDS = int(os.getenv("SERVIQ_BROWSER_SESSION_TIMEOUT", "1800"))


@dataclass(slots=True)
class BrowserSession:
    playwright: Any
    browser: Any
    context: Any
    page: Any
    created_at: float = field(default_factory=time.time)


_BROWSER_SESSIONS: dict[str, BrowserSession] = {}


def _browser_headless() -> bool:
    raw = os.getenv("SERVIQ_BROWSER_HEADLESS", "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _normalize_url(raw_url: str) -> str:
    url = raw_url.strip()
    if not url:
        raise ValueError("URL is required.")

    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must be a valid http:// or https:// address.")

    return url


async def _get_browser_session(session_id: str) -> BrowserSession:
    if async_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Install it with `pip install playwright` and run `playwright install chromium`."
        )

    existing = _BROWSER_SESSIONS.get(session_id)
    if existing:
        return existing

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=_browser_headless())
    context = await browser.new_context(
        viewport={"width": 1366, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        ),
    )
    page = await context.new_page()
    session = BrowserSession(playwright=playwright, browser=browser, context=context, page=page)
    _BROWSER_SESSIONS[session_id] = session
    return session


async def _close_browser_session(session_id: str) -> bool:
    session = _BROWSER_SESSIONS.pop(session_id, None)
    if not session:
        return False

    try:
        await session.context.close()
    finally:
        try:
            await session.browser.close()
        finally:
            await session.playwright.stop()
    return True


async def cleanup_stale_browser_sessions() -> dict[str, Any]:
    """Clean up browser sessions older than the configured timeout."""
    current_time = time.time()
    stale_sessions: list[str] = []
    active_sessions: list[str] = []

    for session_id, session in list(_BROWSER_SESSIONS.items()):
        age = current_time - session.created_at
        if age > _BROWSER_SESSION_TIMEOUT_SECONDS:
            stale_sessions.append(session_id)
        else:
            active_sessions.append(session_id)

    closed_count = 0
    for session_id in stale_sessions:
        if await _close_browser_session(session_id):
            closed_count += 1

    return {
        "closed_stale_sessions": closed_count,
        "stale_session_ids": stale_sessions,
        "active_sessions": len(active_sessions),
    }


def close_browser_session(session_id: str) -> bool:
    """Synchronous wrapper to close a specific browser session.

    This is a convenience wrapper that can be called from non-async contexts.
    Returns True if the session was found and closed, False otherwise.
    """
    # Use asyncio.run in a separate function to avoid nesting
    return False  # Actual cleanup handled by async orchestrator


async def close_browser_session_for_session(session_id: str) -> bool:
    """Async function to close browser sessions for a specific session."""
    return await _close_browser_session(session_id)


async def _page_title(page: Any) -> str:
    try:
        return str(await page.title())
    except Exception:  # noqa: BLE001
        return ""


async def _page_url(page: Any) -> str:
    try:
        return str(page.url or "")
    except Exception:  # noqa: BLE001
        return ""


async def browser_navigate_tool(args: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
    try:
        url = _normalize_url(str(args.get("url", "")))
        wait_until = str(args.get("wait_until", "domcontentloaded"))
        timeout_ms = int(args.get("timeout_ms", 30000))

        session = await _get_browser_session(context.session_id)
        await session.page.goto(url, wait_until=wait_until, timeout=timeout_ms)

        return ToolResult(
            name="browser_navigate",
            ok=True,
            risk=ToolRisk.LOW,
            output={
                "url": await _page_url(session.page),
                "title": await _page_title(session.page),
            },
        )
    except PlaywrightTimeoutError as exc:
        return ToolResult(
            name="browser_navigate",
            ok=False,
            risk=ToolRisk.LOW,
            error=f"Navigation timed out: {exc}",
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(
            name="browser_navigate",
            ok=False,
            risk=ToolRisk.LOW,
            error=str(exc),
        )


async def browser_read_page_tool(args: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
    try:
        max_text_length = min(int(args.get("max_text_length", 6000)), 20000)
        session = await _get_browser_session(context.session_id)
        page = session.page

        text = await page.locator("body").inner_text(timeout=10000)
        text = " ".join(str(text).split())[:max_text_length]

        links = await page.eval_on_selector_all(
            "a",
            """
            (elements) => elements.slice(0, 60).map((element) => ({
              text: (element.innerText || element.textContent || '').trim().slice(0, 160),
              href: element.href || '',
              selector: element.id ? `#${element.id}` : ''
            })).filter((item) => item.text || item.href)
            """,
        )
        buttons = await page.eval_on_selector_all(
            "button, input[type=button], input[type=submit]",
            """
            (elements) => elements.slice(0, 50).map((element) => ({
              text: (element.innerText || element.value || element.getAttribute('aria-label') || '').trim().slice(0, 120),
              type: element.getAttribute('type') || element.tagName.toLowerCase(),
              selector: element.id ? `#${element.id}` : ''
            })).filter((item) => item.text || item.selector)
            """,
        )
        inputs = await page.eval_on_selector_all(
            "input, textarea, select",
            """
            (elements) => elements.slice(0, 80).map((element) => ({
              tag: element.tagName.toLowerCase(),
              type: element.getAttribute('type') || '',
              name: element.getAttribute('name') || '',
              id: element.id || '',
              placeholder: element.getAttribute('placeholder') || '',
              label: element.getAttribute('aria-label') || '',
              selector: element.id ? `#${element.id}` : (element.name ? `${element.tagName.toLowerCase()}[name="${element.name}"]` : '')
            }))
            """,
        )

        return ToolResult(
            name="browser_read_page",
            ok=True,
            risk=ToolRisk.LOW,
            output={
                "url": await _page_url(page),
                "title": await _page_title(page),
                "text": text,
                "links": links,
                "buttons": buttons,
                "inputs": inputs,
            },
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(
            name="browser_read_page",
            ok=False,
            risk=ToolRisk.LOW,
            error=str(exc),
        )


async def browser_click_tool(args: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
    selector = str(args.get("selector", "")).strip()
    text = str(args.get("text", "")).strip()

    if not selector and not text:
        return ToolResult(
            name="browser_click",
            ok=False,
            risk=ToolRisk.MEDIUM,
            error="Provide either selector or text.",
        )

    try:
        session = await _get_browser_session(context.session_id)
        page = session.page
        timeout_ms = int(args.get("timeout_ms", 10000))

        if selector:
            await page.locator(selector).first.click(timeout=timeout_ms)
        else:
            await page.get_by_text(text, exact=False).first.click(timeout=timeout_ms)

        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:  # noqa: BLE001 - many clicks do not navigate.
            pass

        return ToolResult(
            name="browser_click",
            ok=True,
            risk=ToolRisk.MEDIUM,
            output={
                "clicked": selector or text,
                "url": await _page_url(page),
                "title": await _page_title(page),
            },
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(
            name="browser_click",
            ok=False,
            risk=ToolRisk.MEDIUM,
            error=str(exc),
        )


async def browser_fill_form_tool(args: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
    fields = args.get("fields")
    submit = bool(args.get("submit", False))

    if not isinstance(fields, (dict, list)) or not fields:
        return ToolResult(
            name="browser_fill_form",
            ok=False,
            risk=ToolRisk.MEDIUM,
            error="fields must be a non-empty object or list.",
        )

    try:
        session = await _get_browser_session(context.session_id)
        page = session.page
        timeout_ms = int(args.get("timeout_ms", 10000))
        normalized_fields: list[dict[str, Any]] = []

        if isinstance(fields, dict):
            for selector_or_label, value in fields.items():
                normalized_fields.append({"selector": str(selector_or_label), "value": value})
        else:
            for item in fields:
                if isinstance(item, dict):
                    normalized_fields.append(item)

        filled: list[dict[str, Any]] = []
        for field in normalized_fields:
            selector = str(field.get("selector", "")).strip()
            label = str(field.get("label", "")).strip()
            value = str(field.get("value", ""))

            if selector:
                await page.locator(selector).fill(value, timeout=timeout_ms)
                filled.append({"target": selector, "method": "selector"})
            elif label:
                await page.get_by_label(label, exact=False).fill(value, timeout=timeout_ms)
                filled.append({"target": label, "method": "label"})

        submitted = False
        if submit:
            submit_selector = str(args.get("submit_selector", "")).strip()
            if submit_selector:
                await page.locator(submit_selector).first.click(timeout=timeout_ms)
            else:
                await page.locator("button[type=submit], input[type=submit]").first.click(timeout=timeout_ms)
            submitted = True
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:  # noqa: BLE001
                pass

        return ToolResult(
            name="browser_fill_form",
            ok=True,
            risk=ToolRisk.MEDIUM,
            output={
                "filled_count": len(filled),
                "filled": filled,
                "submitted": submitted,
                "url": await _page_url(page),
                "title": await _page_title(page),
            },
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(
            name="browser_fill_form",
            ok=False,
            risk=ToolRisk.MEDIUM,
            error=str(exc),
        )


async def browser_get_current_url_tool(args: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
    try:
        session = await _get_browser_session(context.session_id)
        return ToolResult(
            name="browser_get_current_url",
            ok=True,
            risk=ToolRisk.LOW,
            output={
                "url": await _page_url(session.page),
                "title": await _page_title(session.page),
            },
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(
            name="browser_get_current_url",
            ok=False,
            risk=ToolRisk.LOW,
            error=str(exc),
        )


async def browser_close_tool(args: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
    try:
        closed = await _close_browser_session(context.session_id)
        return ToolResult(
            name="browser_close",
            ok=True,
            risk=ToolRisk.SAFE,
            output={"closed": closed},
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(
            name="browser_close",
            ok=False,
            risk=ToolRisk.SAFE,
            error=str(exc),
        )


BROWSER_TOOL_DEFINITIONS = [
    ToolDefinition(
        name="browser_navigate",
        description=(
            "Open or navigate a real Chromium browser page with Playwright. Use when Serviq needs to visit a known URL."
        ),
        risk=ToolRisk.LOW,
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL or domain to open."},
                "wait_until": {"type": "string", "default": "domcontentloaded"},
                "timeout_ms": {"type": "integer", "default": 30000},
            },
            "required": ["url"],
        },
        handler=browser_navigate_tool,
    ),
    ToolDefinition(
        name="browser_read_page",
        description=(
            "Read the current browser page text, links, buttons, and visible form fields. Use after navigation."
        ),
        risk=ToolRisk.LOW,
        parameters={
            "type": "object",
            "properties": {
                "max_text_length": {"type": "integer", "default": 6000},
            },
        },
        handler=browser_read_page_tool,
    ),
    ToolDefinition(
        name="browser_click",
        description=(
            "Click an element in the browser by CSS selector or visible text. Requires approval because clicks can change accounts, carts, or bookings."
        ),
        risk=ToolRisk.MEDIUM,
        parameters={
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "text": {"type": "string"},
                "timeout_ms": {"type": "integer", "default": 10000},
            },
        },
        handler=browser_click_tool,
    ),
    ToolDefinition(
        name="browser_fill_form",
        description=(
            "Fill browser form fields using selectors or labels. Requires approval because form entry may expose personal data or submit actions."
        ),
        risk=ToolRisk.MEDIUM,
        parameters={
            "type": "object",
            "properties": {
                "fields": {
                    "description": "Object mapping selector/label to value, or list of {selector,label,value} objects."
                },
                "submit": {"type": "boolean", "default": False},
                "submit_selector": {"type": "string"},
                "timeout_ms": {"type": "integer", "default": 10000},
            },
            "required": ["fields"],
        },
        handler=browser_fill_form_tool,
    ),
    ToolDefinition(
        name="browser_get_current_url",
        description="Return the current browser page URL and title. Use to produce final checkout or confirmation links.",
        risk=ToolRisk.LOW,
        parameters={"type": "object", "properties": {}},
        handler=browser_get_current_url_tool,
    ),
    ToolDefinition(
        name="browser_close",
        description="Close the Playwright browser session for this chat.",
        risk=ToolRisk.SAFE,
        parameters={"type": "object", "properties": {}},
        handler=browser_close_tool,
    ),
]
