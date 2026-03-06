#!/usr/bin/env python3
"""Edit an existing Google Flow image asset."""

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
    DEFAULT_TIMEOUT_SECONDS,
    LANDSCAPE_TAB_PATTERNS,
    PORTRAIT_TAB_PATTERNS,
)
from project_manager import ProjectLibrary, build_asset_url, normalize_asset_url, normalize_project_url


CROP_TOOL_PATTERNS = [re.compile(r"crop.*(剪裁|crop)", re.I), re.compile(r"剪裁")]
SELECT_TOOL_PATTERNS = [re.compile(r"select.*(选择|select)", re.I), re.compile(r"选择")]
DRAW_TOOL_PATTERNS = [re.compile(r"draw.*(绘制|draw)", re.I), re.compile(r"绘制")]
DRAW_RECT_TOOL_PATTERNS = [re.compile(r"rectangle", re.I)]
DRAW_BRUSH_TOOL_PATTERNS = [re.compile(r"^draw$", re.I)]
DRAW_TEXT_TOOL_PATTERNS = [re.compile(r"text_fields", re.I), re.compile(r"\btext\b", re.I)]
SELECT_BOX_PATTERNS = [re.compile(r"方框"), re.compile(r"select", re.I)]

CROP_APPLY_PATTERNS = [re.compile(r"arrow_forward.*剪裁", re.I), re.compile(r"^剪裁$", re.I)]
CREATE_SUBMIT_PATTERNS = [re.compile(r"arrow_forward.*(创建|create|generate)", re.I)]
EDIT_SETTINGS_BUTTON_PATTERNS = [
    re.compile(r"(nano banana).*(crop_|arrow_drop_down|纵向|横向)", re.I),
]
MODEL_DROPDOWN_PATTERNS = [re.compile(r"arrow_drop_down", re.I)]
DONE_BUTTON_PATTERNS = [re.compile(r"^完成$"), re.compile(r"^done$", re.I)]
DISCARD_BUTTON_PATTERNS = [re.compile(r"^舍弃$"), re.compile(r"^discard$", re.I)]

CROP_PRESET_PATTERNS = {
    "landscape": [re.compile(r"横向"), re.compile(r"landscape", re.I), re.compile(r"16:9")],
    "portrait": [re.compile(r"纵向"), re.compile(r"portrait", re.I), re.compile(r"9:16")],
    "square": [re.compile(r"方形"), re.compile(r"square", re.I), re.compile(r"1:1")],
    "free": [re.compile(r"自由"), re.compile(r"free", re.I)],
}

CROP_HANDLE_PATTERNS = {
    "north_west": re.compile(r"north west drag handle", re.I),
    "south_east": re.compile(r"south east drag handle", re.I),
}


def parse_normalized_box(raw: str | None) -> tuple[float, float, float, float] | None:
    if not raw:
        return None
    parts = [float(part.strip()) for part in raw.split(",")]
    if len(parts) != 4:
        raise ValueError("--box must be x1,y1,x2,y2 using normalized values between 0 and 1")
    x1, y1, x2, y2 = parts
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        raise ValueError("--box must satisfy 0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1")
    return x1, y1, x2, y2


def parse_points(raw: str | None) -> list[tuple[float, float]]:
    if not raw:
        return []
    points = []
    for chunk in raw.split(";"):
        x_str, y_str = chunk.split(",", 1)
        x = float(x_str.strip())
        y = float(y_str.strip())
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise ValueError("--points values must stay between 0 and 1")
        points.append((x, y))
    if len(points) < 2:
        raise ValueError("--points requires at least two normalized coordinates")
    return points


def parse_normalized_point(raw: str | None) -> tuple[float, float] | None:
    if not raw:
        return None
    parts = [float(part.strip()) for part in raw.split(",")]
    if len(parts) != 2:
        raise ValueError("--point must be x,y using normalized values between 0 and 1")
    x, y = parts
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise ValueError("--point values must stay between 0 and 1")
    return x, y


def resolve_project_url(args) -> tuple[str, str]:
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
        raise ValueError("No project specified and no active project is set")
    return normalize_project_url(active["url"])


def resolve_asset_url(args, show_browser: bool) -> tuple[str, str, str]:
    library = ProjectLibrary()
    if args.asset_url:
        return normalize_asset_url(args.asset_url)

    if args.latest_image:
        project_url, _ = resolve_project_url(args)
        assets = library.list_project_assets(
            project_url=project_url,
            kind="image",
            limit=1,
            headless=not show_browser,
        )
        if not assets:
            raise ValueError("No image assets found in the selected project")
        return normalize_asset_url(assets[0]["url"])

    if args.asset_id:
        project_url, project_id = resolve_project_url(args)
        return normalize_asset_url(build_asset_url(project_url, args.asset_id))

    raise ValueError("Provide --asset-url, or use --asset-id / --latest-image with a project")


def find_role(scope, role: str, patterns: list[re.Pattern]):
    items = scope.get_by_role(role)
    for index in range(items.count()):
        item = items.nth(index)
        try:
            if not item.is_visible():
                continue
            text = (item.get_attribute("aria-label") or item.inner_text() or "").strip()
        except Exception:
            continue
        for pattern in patterns:
            if pattern.search(text):
                return item
    return None


class FlowImageEditor:
    def __init__(self, *, show_browser: bool, timeout_seconds: int) -> None:
        self.show_browser = show_browser
        self.timeout_seconds = timeout_seconds

    def run(self, args) -> dict:
        auth = AuthManager()
        if not auth.validate_auth():
            raise RuntimeError("Flow authentication is required. Run auth_manager.py setup first.")

        asset_url, project_id, asset_id = resolve_asset_url(args, self.show_browser)
        box = parse_normalized_box(args.box)
        points = parse_points(args.points)
        point = parse_normalized_point(args.point)

        if args.tool in {"select-box", "draw-rect"} and not box:
            raise ValueError(f"{args.tool} requires --box x1,y1,x2,y2")
        if args.tool == "draw-brush" and not points:
            raise ValueError("draw-brush requires --points x1,y1;x2,y2;...")
        if args.tool == "text" and not point:
            raise ValueError("text requires --point x,y")
        if args.tool == "text" and not args.text:
            raise ValueError("text requires --text")
        if args.text_size is not None and args.tool != "text":
            raise ValueError("--text-size is only supported with --tool text")
        if args.text_size is not None and args.text_size <= 0:
            raise ValueError("--text-size must be a positive integer")
        if args.text and ("\n" in args.text or "\r" in args.text):
            raise ValueError("--text must be single-line for Flow text overlays")
        if args.tool in {"full", "select-box", "draw-rect", "draw-brush"} and not args.prompt:
            raise ValueError("Non-crop image edits require --prompt")

        playwright = None
        context = None
        try:
            playwright = sync_playwright().start()
            context = BrowserFactory.launch_persistent_context(playwright, headless=not self.show_browser)
            page = context.new_page()
            FlowBrowser.load_page(page, asset_url)
            FlowBrowser.wait_for_prompt_editor(page)
            FlowBrowser.dismiss_transient_ui(page)

            if args.tool == "crop":
                self._run_crop(page, crop_preset=args.crop_preset, box=box)
                status = "cropped"
            elif args.tool == "text":
                self._insert_text_overlay(page, point=point, text=args.text, text_size=args.text_size)
                status = "text_added"
            else:
                self._configure_edit_settings(page, aspect_ratio=args.aspect_ratio, model=args.model)
                self._apply_edit_tool(page, tool=args.tool, box=box, points=points)
                FlowBrowser.wait_for_prompt_editor(page)
                FlowBrowser.human_fill_prompt(page, args.prompt)
                baseline = FlowBrowser.canvas_fingerprint(page)
                self._submit_ai_edit(page)
                if not args.no_wait:
                    self._wait_for_canvas_change(page, baseline)
                status = "completed" if not args.no_wait else "submitted"

            if args.click_done:
                self._click_done(page)

            return {
                "project_id": project_id,
                "asset_id": asset_id,
                "asset_url": asset_url,
                "tool": args.tool,
                "model": args.model,
                "aspect_ratio": args.aspect_ratio,
                "text": args.text,
                "text_size": args.text_size,
                "status": status,
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

    def _configure_edit_settings(self, page, *, aspect_ratio: str | None, model: str | None) -> None:
        if not aspect_ratio and not model:
            return

        settings_button = find_role(page, "button", EDIT_SETTINGS_BUTTON_PATTERNS)
        if not settings_button:
            raise RuntimeError("Could not find the Flow image-edit settings button")
        settings_button.click()
        menu = FlowBrowser.latest_visible_menu(page)
        if not menu:
            raise RuntimeError("Could not find the Flow image-edit settings menu")

        if aspect_ratio == "landscape":
            self._click_matching(menu, "tab", LANDSCAPE_TAB_PATTERNS)
        elif aspect_ratio == "portrait":
            self._click_matching(menu, "tab", PORTRAIT_TAB_PATTERNS)

        if model:
            dropdown = find_role(menu, "button", MODEL_DROPDOWN_PATTERNS)
            if not dropdown:
                raise RuntimeError("Could not find the Flow image-edit model dropdown")
            dropdown.click()
            active_menu = FlowBrowser.latest_visible_menu(page)
            if not active_menu:
                raise RuntimeError("Could not find the Flow image-edit model option menu")
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
                    break
            else:
                raise RuntimeError(f"Could not find model option containing: {model}")

        FlowBrowser.dismiss_transient_ui(page)

    def _run_crop(self, page, *, crop_preset: str | None, box: tuple[float, float, float, float] | None) -> None:
        crop_button = find_role(page, "button", CROP_TOOL_PATTERNS)
        if not crop_button:
            raise RuntimeError("Could not find the Flow crop tool")
        crop_button.click()

        if crop_preset:
            menu = FlowBrowser.latest_visible_menu(page)
            if not menu:
                raise RuntimeError("Could not find the crop preset menu")
            self._click_matching(menu, "menuitem", CROP_PRESET_PATTERNS[crop_preset])
            page.wait_for_timeout(300)

        if box:
            self._set_crop_box(page, box)

        baseline = FlowBrowser.canvas_fingerprint(page)
        apply_button = find_role(page, "button", CROP_APPLY_PATTERNS)
        if not apply_button:
            raise RuntimeError("Could not find the apply-crop button")
        apply_button.click()
        self._wait_for_canvas_change(page, baseline)

    def _set_crop_box(self, page, box: tuple[float, float, float, float]) -> None:
        x1, y1, x2, y2 = box
        nw_target = FlowBrowser.normalized_point_to_canvas(page, x1, y1)
        se_target = FlowBrowser.normalized_point_to_canvas(page, x2, y2)

        nw_handle = page.get_by_role("button", name=CROP_HANDLE_PATTERNS["north_west"]).first
        se_handle = page.get_by_role("button", name=CROP_HANDLE_PATTERNS["south_east"]).first

        nw_box = nw_handle.bounding_box()
        se_box = se_handle.bounding_box()
        if not nw_box or not se_box:
            raise RuntimeError("Could not determine crop handle positions")

        FlowBrowser.drag(
            page,
            (nw_box["x"] + nw_box["width"] / 2, nw_box["y"] + nw_box["height"] / 2),
            nw_target,
        )
        page.wait_for_timeout(200)
        FlowBrowser.drag(
            page,
            (se_box["x"] + se_box["width"] / 2, se_box["y"] + se_box["height"] / 2),
            se_target,
        )
        page.wait_for_timeout(200)

    def _apply_edit_tool(
        self,
        page,
        *,
        tool: str,
        box: tuple[float, float, float, float] | None,
        points: list[tuple[float, float]],
    ) -> None:
        if tool == "full":
            return
        if tool == "select-box":
            self._open_select_box(page)
            self._drag_box_on_canvas(page, box)
            return
        if tool == "draw-rect":
            self._open_draw_tool(page, subtool="rectangle")
            self._drag_box_on_canvas(page, box)
            return
        if tool == "draw-brush":
            self._open_draw_tool(page, subtool="draw")
            self._draw_path(page, points)
            return
        if tool == "text":
            return
        raise RuntimeError(f"Unsupported tool: {tool}")

    def _open_select_box(self, page) -> None:
        select_button = find_role(page, "button", SELECT_TOOL_PATTERNS)
        if not select_button:
            raise RuntimeError("Could not find the Flow select tool")
        select_button.click()
        menu = FlowBrowser.latest_visible_menu(page)
        if not menu:
            raise RuntimeError("Could not find the Flow select menu")
        self._click_matching(menu, "menuitem", SELECT_BOX_PATTERNS)
        FlowBrowser.dismiss_transient_ui(page)

    def _open_draw_tool(self, page, *, subtool: str) -> None:
        draw_button = find_role(page, "button", DRAW_TOOL_PATTERNS)
        if not draw_button:
            raise RuntimeError("Could not find the Flow draw tool")
        draw_button.click()
        menu = FlowBrowser.latest_visible_menu(page)
        if not menu:
            raise RuntimeError("Could not find the Flow draw tool menu")
        if subtool == "rectangle":
            patterns = DRAW_RECT_TOOL_PATTERNS
        elif subtool == "text_fields":
            patterns = DRAW_TEXT_TOOL_PATTERNS
        else:
            patterns = DRAW_BRUSH_TOOL_PATTERNS
        self._click_matching(menu, "button", patterns)
        page.wait_for_timeout(300)

    def _insert_text_overlay(self, page, *, point: tuple[float, float], text: str, text_size: int | None) -> None:
        self._open_draw_tool(page, subtool="text_fields")
        if text_size is not None:
            self._set_visible_slider_value(page, text_size)
        target = FlowBrowser.normalized_point_to_canvas(page, point[0], point[1])
        page.mouse.click(target[0], target[1])

        textbox = self._wait_for_visible_canvas_textbox(page)
        textbox.click()
        textbox.fill(text)
        if textbox.input_value() != text:
            raise RuntimeError("Flow did not accept the requested text overlay content")

        textbox.press("Enter")
        self._wait_for_textbox_to_close(page, textbox)
        page.wait_for_timeout(300)

    def _drag_box_on_canvas(self, page, box: tuple[float, float, float, float]) -> None:
        x1, y1, x2, y2 = box
        start = FlowBrowser.normalized_point_to_canvas(page, x1, y1)
        end = FlowBrowser.normalized_point_to_canvas(page, x2, y2)
        FlowBrowser.drag(page, start, end)
        page.wait_for_timeout(300)

    def _draw_path(self, page, points: list[tuple[float, float]]) -> None:
        absolute = [FlowBrowser.normalized_point_to_canvas(page, x, y) for x, y in points]
        first, rest = absolute[0], absolute[1:]
        page.mouse.move(first[0], first[1])
        page.mouse.down()
        for point in rest:
            page.mouse.move(point[0], point[1], steps=6)
        page.mouse.up()
        page.wait_for_timeout(300)

    def _submit_ai_edit(self, page) -> None:
        submit_button = find_role(page, "button", CREATE_SUBMIT_PATTERNS)
        if not submit_button:
            raise RuntimeError("Could not find the Flow image-edit create button")
        submit_button.click()

    def _wait_for_canvas_change(self, page, baseline: str) -> None:
        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline:
            current = FlowBrowser.canvas_fingerprint(page)
            if current != baseline:
                return
            page.wait_for_timeout(1500)
        raise TimeoutError("Timed out waiting for the edited image canvas to change")

    def _click_done(self, page) -> None:
        done_button = find_role(page, "button", DONE_BUTTON_PATTERNS)
        if done_button:
            done_button.click()

    def _wait_for_visible_canvas_textbox(self, page):
        deadline = time.time() + min(self.timeout_seconds, 10)
        textboxes = page.locator("textarea")
        while time.time() < deadline:
            for index in range(textboxes.count()):
                textbox = textboxes.nth(index)
                try:
                    if textbox.is_visible() and textbox.bounding_box():
                        return textbox
                except Exception:
                    continue
            page.wait_for_timeout(100)
        raise RuntimeError("Could not find the temporary Flow text overlay editor")

    def _wait_for_textbox_to_close(self, page, textbox) -> None:
        deadline = time.time() + min(self.timeout_seconds, 10)
        while time.time() < deadline:
            try:
                if not textbox.is_visible():
                    return
            except Exception:
                return
            page.wait_for_timeout(100)
        raise TimeoutError("Timed out waiting for the Flow text overlay editor to close")

    def _set_visible_slider_value(self, page, target: int) -> None:
        slider = self._wait_for_visible_slider(page)
        current = self._slider_value(slider, "aria-valuenow")
        minimum = self._slider_value(slider, "aria-valuemin")
        maximum = self._slider_value(slider, "aria-valuemax")

        if target < minimum or target > maximum:
            raise ValueError(f"--text-size must stay between {minimum} and {maximum}")

        slider.click()
        key = "ArrowRight" if target > current else "ArrowLeft"
        for _ in range(abs(target - current)):
            page.keyboard.press(key)

        final_value = self._slider_value(slider, "aria-valuenow")
        if final_value != target:
            raise RuntimeError(f"Flow text size slider stopped at {final_value}px instead of {target}px")

    def _wait_for_visible_slider(self, page):
        deadline = time.time() + min(self.timeout_seconds, 10)
        sliders = page.get_by_role("slider")
        while time.time() < deadline:
            for index in range(sliders.count()):
                slider = sliders.nth(index)
                try:
                    if slider.is_visible():
                        return slider
                except Exception:
                    continue
            page.wait_for_timeout(100)
        raise RuntimeError("Could not find the Flow text size slider")

    def _slider_value(self, slider, name: str) -> int:
        raw = slider.get_attribute(name)
        if raw is None:
            raise RuntimeError(f"Flow text size slider is missing {name}")
        return int(raw)

    def _click_matching(self, scope, role: str, patterns: list[re.Pattern]) -> None:
        target = find_role(scope, role, patterns)
        if not target:
            raise RuntimeError(f"Could not find expected {role} matching {patterns}")
        target.click()


def main() -> int:
    parser = argparse.ArgumentParser(description="Edit an existing Google Flow image asset")
    parser.add_argument("--asset-url")
    parser.add_argument("--asset-id")
    parser.add_argument("--latest-image", action="store_true")
    parser.add_argument("--project-url")
    parser.add_argument("--project-id")
    parser.add_argument("--tool", choices=["full", "crop", "select-box", "draw-rect", "draw-brush", "text"], default="full")
    parser.add_argument("--prompt")
    parser.add_argument("--text")
    parser.add_argument("--text-size", type=int, help="Text overlay size in px")
    parser.add_argument("--model")
    parser.add_argument("--aspect-ratio", choices=["landscape", "portrait"])
    parser.add_argument("--crop-preset", choices=["landscape", "portrait", "square", "free"])
    parser.add_argument("--box", help="Normalized region x1,y1,x2,y2")
    parser.add_argument("--point", help="Normalized text insertion point x,y")
    parser.add_argument("--points", help="Normalized draw-brush points x1,y1;x2,y2;...")
    parser.add_argument("--show-browser", action="store_true")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument("--click-done", action="store_true")

    args = parser.parse_args()
    if args.no_wait and args.click_done:
        print(json.dumps({"error": "--click-done requires waiting for the edit to finish"}, indent=2, ensure_ascii=False))
        return 1
    editor = FlowImageEditor(show_browser=args.show_browser, timeout_seconds=args.timeout)

    try:
        result = editor.run(args)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, indent=2, ensure_ascii=False))
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
