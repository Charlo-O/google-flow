#!/usr/bin/env python3
"""Generate images or videos inside a Google Flow project."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from patchright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_manager import AuthManager
from browser_utils import BrowserFactory, FlowBrowser
from config import (
    COMPOSER_ADD_BUTTON_PATTERNS,
    COMPOSER_SUBMIT_BUTTON_PATTERNS,
    DEFAULT_TIMEOUT_SECONDS,
    END_FRAME_PATTERNS,
    FRAMES_TAB_PATTERNS,
    IMAGE_TAB_PATTERNS,
    INGREDIENTS_TAB_PATTERNS,
    LANDSCAPE_TAB_PATTERNS,
    PORTRAIT_TAB_PATTERNS,
    SETTINGS_BUTTON_PATTERNS,
    START_FRAME_PATTERNS,
    VIDEO_TAB_PATTERNS,
    FLOW_PROJECT_URL_RE,
)
from project_manager import ProjectLibrary, normalize_project_url


def resolve_project(args) -> tuple[str, str]:
    library = ProjectLibrary()
    if args.project_url:
        return normalize_project_url(args.project_url)
    if args.project_id:
        project = library.get_project(args.project_id)
        if not project:
            raise ValueError(f"Unknown project id: {args.project_id}")
        return normalize_project_url(project["url"])
    active = library.get_active_project()
    if not active:
        raise ValueError("No project provided and no active project is set")
    return normalize_project_url(active["url"])


def ensure_paths_exist(paths: list[str]) -> list[str]:
    resolved = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Missing file: {path}")
        resolved.append(str(path))
    return resolved


class FlowGenerator:
    def __init__(self, *, show_browser: bool, timeout_seconds: int) -> None:
        self.show_browser = show_browser
        self.timeout_seconds = timeout_seconds

    def run(self, args) -> dict:
        auth = AuthManager()
        if not auth.validate_auth():
            raise RuntimeError("Flow authentication is required. Run auth_manager.py setup first.")

        project_url, project_id = resolve_project(args)
        ingredient_paths = ensure_paths_exist(args.ingredient_paths or [])
        start_frame = ensure_paths_exist([args.start_frame])[0] if args.start_frame else None
        end_frame = ensure_paths_exist([args.end_frame])[0] if args.end_frame else None

        if args.video_mode == "frames" and not (start_frame or end_frame):
            raise ValueError("Frames mode requires --start-frame, --end-frame, or both")

        playwright = None
        context = None
        try:
            playwright = sync_playwright().start()
            context = BrowserFactory.launch_persistent_context(playwright, headless=not self.show_browser)
            page = context.new_page()
            FlowBrowser.load_page(page, project_url)
            FlowBrowser.wait_for_project_shell(page)
            FlowBrowser.dismiss_transient_ui(page)

            existing_assets = set(FlowBrowser.collect_asset_urls(page))

            self._fill_prompt(page, args.prompt)
            self._configure_generation(
                page,
                mode=args.mode,
                video_mode=args.video_mode,
                aspect_ratio=args.aspect_ratio,
                outputs=args.outputs,
                model=args.model,
            )

            if args.mode == "video" and args.video_mode == "frames":
                self._attach_frames(page, start_frame=start_frame, end_frame=end_frame)
            elif ingredient_paths:
                self._attach_prompt_assets(page, ingredient_paths)

            self._submit(page)

            if args.no_wait:
                return {
                    "project_id": project_id,
                    "project_url": project_url,
                    "mode": args.mode,
                    "video_mode": args.video_mode,
                    "model": args.model,
                    "outputs": args.outputs,
                    "status": "submitted",
                }

            asset_url = self._wait_for_new_asset(page, existing_assets)
            return {
                "project_id": project_id,
                "project_url": project_url,
                "mode": args.mode,
                "video_mode": args.video_mode,
                "model": args.model,
                "outputs": args.outputs,
                "asset_url": asset_url,
                "status": "completed" if asset_url else "timeout",
            }
        finally:
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            if playwright:
                try:
                    playwright.stop()
                except Exception:
                    pass

    def _fill_prompt(self, page, prompt: str) -> None:
        FlowBrowser.wait_for_prompt_editor(page)
        FlowBrowser.human_fill_prompt(page, prompt)

    def _configure_generation(
        self,
        page,
        *,
        mode: str,
        video_mode: str,
        aspect_ratio: str,
        outputs: int,
        model: str,
    ) -> None:
        settings_button = FlowBrowser.find_button(page, SETTINGS_BUTTON_PATTERNS)
        if not settings_button:
            raise RuntimeError("Could not find the Flow generation settings button")
        settings_button.click()

        if mode == "image":
            self._click_first_matching_tab(page, IMAGE_TAB_PATTERNS)
        else:
            self._click_first_matching_tab(page, VIDEO_TAB_PATTERNS)
            if video_mode == "frames":
                self._click_first_matching_tab(page, FRAMES_TAB_PATTERNS)
            else:
                self._click_first_matching_tab(page, INGREDIENTS_TAB_PATTERNS)

        if aspect_ratio == "landscape":
            self._click_first_matching_tab(page, LANDSCAPE_TAB_PATTERNS)
        else:
            self._click_first_matching_tab(page, PORTRAIT_TAB_PATTERNS)

        output_tab = page.get_by_role("tab", name=re.compile(fr"^x{outputs}$", re.I)).first
        output_tab.click()

        self._select_model(page, model)
        FlowBrowser.dismiss_transient_ui(page)

    def _select_model(self, page, model: str) -> None:
        menu = FlowBrowser.latest_visible_menu(page)
        if not menu:
            raise RuntimeError("Could not find the Flow settings menu")

        dropdown = None
        buttons = menu.get_by_role("button")
        for index in range(buttons.count()):
            button = buttons.nth(index)
            try:
                text = (button.get_attribute("aria-label") or button.inner_text() or "").strip()
            except Exception:
                continue
            if "arrow_drop_down" in text or any(token in text for token in ("Veo", "Nano Banana", "video", "Video", "image", "Image")):
                dropdown = button
        if not dropdown:
            raise RuntimeError("Could not find the Flow model dropdown")

        dropdown.click()
        active_menu = FlowBrowser.latest_visible_menu(page)
        if not active_menu:
            raise RuntimeError("Could not find the Flow model option menu")
        buttons = active_menu.get_by_role("button")
        wanted = model.lower()
        for index in range(buttons.count()):
            button = buttons.nth(index)
            try:
                if not button.is_visible():
                    continue
                text = (button.get_attribute("aria-label") or button.inner_text() or "").strip().lower()
            except Exception:
                continue
            if wanted in text:
                button.click()
                return
        raise RuntimeError(f"Could not find model option containing: {model}")

    def _click_first_matching_tab(self, page, patterns) -> None:
        tabs = page.get_by_role("tab")
        for index in range(tabs.count()):
            tab = tabs.nth(index)
            try:
                if not tab.is_visible():
                    continue
                text = (tab.get_attribute("aria-label") or tab.inner_text() or "").strip()
            except Exception:
                continue
            for pattern in patterns:
                if pattern.search(text):
                    tab.click()
                    return
        raise RuntimeError(f"Could not find expected Flow tab for patterns: {patterns}")

    def _attach_prompt_assets(self, page, paths: list[str]) -> None:
        add_button = FlowBrowser.find_button(page, COMPOSER_ADD_BUTTON_PATTERNS)
        if not add_button:
            raise RuntimeError("Could not find the Flow add-to-prompt button")
        add_button.click()
        page.wait_for_timeout(500)
        FlowBrowser.set_file_input_files(page, paths)
        page.wait_for_timeout(1500)
        FlowBrowser.dismiss_transient_ui(page)

    def _attach_frames(self, page, *, start_frame: str | None, end_frame: str | None) -> None:
        if start_frame:
            start_target = FlowBrowser.find_text_target(page, START_FRAME_PATTERNS)
            if not start_target:
                raise RuntimeError("Could not find the start-frame drop zone")
            start_target.click()
            FlowBrowser.set_file_input_files(page, [start_frame])
            page.wait_for_timeout(1000)
        if end_frame:
            end_target = FlowBrowser.find_text_target(page, END_FRAME_PATTERNS)
            if not end_target:
                raise RuntimeError("Could not find the end-frame drop zone")
            end_target.click()
            FlowBrowser.set_file_input_files(page, [end_frame])
            page.wait_for_timeout(1000)

    def _submit(self, page) -> None:
        submit_button = FlowBrowser.find_button(page, COMPOSER_SUBMIT_BUTTON_PATTERNS)
        if not submit_button:
            raise RuntimeError("Could not find the Flow generate button")
        submit_button.click()

    def _wait_for_new_asset(self, page, existing_assets: set[str]) -> str | None:
        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline:
            current_url = page.url
            match = FLOW_PROJECT_URL_RE.match(current_url)
            if match and match.group("asset_id") and current_url not in existing_assets:
                return current_url

            assets = set(FlowBrowser.collect_asset_urls(page))
            new_assets = [url for url in assets if url not in existing_assets]
            if new_assets:
                return new_assets[-1]

            page.wait_for_timeout(2000)

        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Flow media inside an existing project")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--project-url")
    parser.add_argument("--project-id")
    parser.add_argument("--mode", choices=["image", "video"], required=True)
    parser.add_argument("--video-mode", choices=["frames", "ingredients"], default="ingredients")
    parser.add_argument("--aspect-ratio", choices=["landscape", "portrait"], default="landscape")
    parser.add_argument("--outputs", type=int, choices=[1, 2, 3, 4], default=1)
    parser.add_argument("--model", required=True)
    parser.add_argument("--ingredient-paths", nargs="*")
    parser.add_argument("--start-frame")
    parser.add_argument("--end-frame")
    parser.add_argument("--show-browser", action="store_true")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--no-wait", action="store_true")

    args = parser.parse_args()
    generator = FlowGenerator(show_browser=args.show_browser, timeout_seconds=args.timeout)

    try:
        result = generator.run(args)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, indent=2, ensure_ascii=False))
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
