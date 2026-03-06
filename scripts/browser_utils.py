"""Browser helpers for the Google Flow skill."""

from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path
from typing import Iterable

from patchright.sync_api import BrowserContext, Page, Playwright

from config import (
    AUTH_SESSION_URL,
    BROWSER_ARGS,
    BROWSER_PROFILE_DIR,
    FILE_INPUT_SELECTOR,
    PAGE_LOAD_TIMEOUT_MS,
    PROMPT_EDITOR_SELECTOR,
    STATE_FILE,
    USER_AGENT,
)


class BrowserFactory:
    """Launch configured persistent browser contexts."""

    @staticmethod
    def launch_persistent_context(
        playwright: Playwright,
        *,
        headless: bool = True,
        user_data_dir: str | Path = BROWSER_PROFILE_DIR,
    ) -> BrowserContext:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            channel="chrome",
            headless=headless,
            no_viewport=True,
            ignore_default_args=["--enable-automation"],
            user_agent=USER_AGENT,
            args=BROWSER_ARGS,
        )
        BrowserFactory._inject_cookies(context)
        context.set_default_timeout(PAGE_LOAD_TIMEOUT_MS)
        context.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT_MS)
        return context

    @staticmethod
    def _inject_cookies(context: BrowserContext) -> None:
        if not STATE_FILE.exists():
            return
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return
        cookies = state.get("cookies") or []
        if cookies:
            try:
                context.add_cookies(cookies)
            except Exception:
                pass


class FlowBrowser:
    """High-level helpers around Playwright for Flow."""

    @staticmethod
    def normalize_text(value: str | None) -> str:
        return re.sub(r"\s+", " ", (value or "")).strip()

    @staticmethod
    def fetch_auth_session(page: Page) -> dict:
        try:
            session = page.evaluate(
                """async (url) => {
                    try {
                        const response = await fetch(url, { credentials: "include" });
                        return await response.json();
                    } catch (error) {
                        return { error: String(error) };
                    }
                }""",
                AUTH_SESSION_URL,
            )
        except Exception as exc:
            return {"error": str(exc)}
        return session if isinstance(session, dict) else {}

    @staticmethod
    def has_live_session(page: Page) -> bool:
        session = FlowBrowser.fetch_auth_session(page)
        return bool(session.get("user"))

    @staticmethod
    def wait_for_prompt_editor(page: Page, timeout_ms: int = PAGE_LOAD_TIMEOUT_MS) -> None:
        page.wait_for_selector(PROMPT_EDITOR_SELECTOR, state="visible", timeout=timeout_ms)

    @staticmethod
    def human_fill_prompt(page: Page, text: str) -> None:
        editor = page.locator(PROMPT_EDITOR_SELECTOR).first
        editor.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        for character in text:
            page.keyboard.type(character, delay=random.randint(15, 45))
            if random.random() < 0.03:
                time.sleep(random.uniform(0.05, 0.15))

    @staticmethod
    def find_button(page: Page, patterns: Iterable) -> object | None:
        buttons = page.get_by_role("button")
        count = buttons.count()
        for index in range(count):
            button = buttons.nth(index)
            try:
                if not button.is_visible():
                    continue
                name = FlowBrowser.normalize_text(button.get_attribute("aria-label") or button.inner_text())
            except Exception:
                continue
            for pattern in patterns:
                if pattern.search(name):
                    return button
        return None

    @staticmethod
    def find_text_target(page: Page, patterns: Iterable) -> object | None:
        nodes = page.locator("body *")
        count = nodes.count()
        for index in range(count):
            node = nodes.nth(index)
            try:
                if not node.is_visible():
                    continue
                text = FlowBrowser.normalize_text(node.inner_text())
            except Exception:
                continue
            if not text:
                continue
            for pattern in patterns:
                if pattern.search(text):
                    return node
        return None

    @staticmethod
    def dismiss_transient_ui(page: Page) -> None:
        for _ in range(3):
            try:
                page.keyboard.press("Escape")
            except Exception:
                return

    @staticmethod
    def visible_menus(page: Page) -> list:
        menus = page.get_by_role("menu")
        visible = []
        for index in range(menus.count()):
            menu = menus.nth(index)
            try:
                if menu.is_visible():
                    visible.append(menu)
            except Exception:
                continue
        return visible

    @staticmethod
    def latest_visible_menu(page: Page):
        visible = FlowBrowser.visible_menus(page)
        return visible[-1] if visible else None

    @staticmethod
    def set_file_input_files(page: Page, paths: list[str]) -> None:
        page.locator(FILE_INPUT_SELECTOR).first.set_input_files(paths)

    @staticmethod
    def canvas_bbox(page: Page, index: int = 0) -> dict:
        canvas = page.locator("canvas").nth(index)
        box = canvas.bounding_box()
        if not box:
            raise RuntimeError("Could not determine the Flow canvas bounding box")
        return box

    @staticmethod
    def canvas_fingerprint(page: Page) -> str:
        return page.evaluate(
            """() => {
                function quickHash(text) {
                    let hash = 0;
                    for (let i = 0; i < text.length; i += 97) {
                        hash = (hash * 31 + text.charCodeAt(i)) >>> 0;
                    }
                    return `${text.length}:${hash}`;
                }

                return Array.from(document.querySelectorAll('canvas')).map((canvas) => {
                    try {
                        return quickHash(canvas.toDataURL('image/png'));
                    } catch (error) {
                        return `${canvas.width}x${canvas.height}`;
                    }
                }).join('|');
            }"""
        )

    @staticmethod
    def normalized_point_to_canvas(page: Page, x: float, y: float, index: int = 0) -> tuple[float, float]:
        box = FlowBrowser.canvas_bbox(page, index=index)
        return box["x"] + box["width"] * x, box["y"] + box["height"] * y

    @staticmethod
    def drag(page: Page, start: tuple[float, float], end: tuple[float, float], steps: int = 12) -> None:
        page.mouse.move(start[0], start[1])
        page.mouse.down()
        page.mouse.move(end[0], end[1], steps=steps)
        page.mouse.up()

    @staticmethod
    def collect_project_urls(page: Page) -> list[str]:
        return page.evaluate(
            """() => Array.from(
                new Set(
                    Array.from(document.querySelectorAll('a[href*="/tools/flow/project/"]'))
                        .map((node) => node.href)
                        .filter((href) => href && !href.includes('/edit/'))
                )
            )"""
        )

    @staticmethod
    def collect_asset_urls(page: Page) -> list[str]:
        return page.evaluate(
            """() => Array.from(
                new Set(
                    Array.from(document.querySelectorAll('a[href*="/tools/flow/project/"][href*="/edit/"]'))
                        .map((node) => node.href)
                        .filter(Boolean)
                )
            )"""
        )

    @staticmethod
    def wait_for_project_shell(page: Page) -> None:
        FlowBrowser.wait_for_prompt_editor(page)

    @staticmethod
    def load_page(page: Page, url: str) -> None:
        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
