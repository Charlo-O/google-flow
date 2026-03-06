#!/usr/bin/env python3
"""Authentication management for Google Flow."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from patchright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))

from browser_utils import BrowserFactory, FlowBrowser
from config import (
    AUTH_INFO_FILE,
    BROWSER_STATE_DIR,
    DATA_DIR,
    ENTRY_BUTTON_PATTERNS,
    FLOW_HOME_URL,
    LOGIN_TIMEOUT_MINUTES,
    STATE_FILE,
)


class AuthManager:
    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        BROWSER_STATE_DIR.mkdir(parents=True, exist_ok=True)

    def is_authenticated(self) -> bool:
        return STATE_FILE.exists()

    def get_auth_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "authenticated": self.is_authenticated(),
            "state_file": str(STATE_FILE),
            "state_exists": STATE_FILE.exists(),
        }
        if AUTH_INFO_FILE.exists():
            try:
                info.update(json.loads(AUTH_INFO_FILE.read_text(encoding="utf-8")))
            except Exception:
                pass
        if STATE_FILE.exists():
            info["state_age_hours"] = (time.time() - STATE_FILE.stat().st_mtime) / 3600
        return info

    def setup_auth(self, timeout_minutes: float = LOGIN_TIMEOUT_MINUTES, headless: bool = False) -> bool:
        playwright = None
        context = None
        try:
            playwright = sync_playwright().start()
            context = BrowserFactory.launch_persistent_context(playwright, headless=headless)
            page = context.new_page()
            FlowBrowser.load_page(page, FLOW_HOME_URL)

            if FlowBrowser.has_live_session(page):
                self._save_state(context)
                self._save_auth_info(page)
                return True

            entry_button = FlowBrowser.find_button(page, ENTRY_BUTTON_PATTERNS)
            if entry_button:
                entry_button.click()

            deadline = time.time() + timeout_minutes * 60
            while time.time() < deadline:
                if "labs.google" in page.url and FlowBrowser.has_live_session(page):
                    self._save_state(context)
                    self._save_auth_info(page)
                    return True
                time.sleep(2)
            return False
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

    def validate_auth(self) -> bool:
        if not self.is_authenticated():
            return False

        playwright = None
        context = None
        try:
            playwright = sync_playwright().start()
            context = BrowserFactory.launch_persistent_context(playwright, headless=True)
            page = context.new_page()
            FlowBrowser.load_page(page, FLOW_HOME_URL)
            return FlowBrowser.has_live_session(page)
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

    def clear_auth(self) -> bool:
        try:
            if STATE_FILE.exists():
                STATE_FILE.unlink()
            if AUTH_INFO_FILE.exists():
                AUTH_INFO_FILE.unlink()
            if BROWSER_STATE_DIR.exists():
                shutil.rmtree(BROWSER_STATE_DIR)
            BROWSER_STATE_DIR.mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False

    def reauth(self, timeout_minutes: float = LOGIN_TIMEOUT_MINUTES) -> bool:
        self.clear_auth()
        return self.setup_auth(timeout_minutes=timeout_minutes, headless=False)

    def _save_state(self, context) -> None:
        context.storage_state(path=str(STATE_FILE))

    def _save_auth_info(self, page) -> None:
        session = FlowBrowser.fetch_auth_session(page)
        payload = {
            "authenticated_at": time.time(),
            "authenticated_at_iso": time.strftime("%Y-%m-%d %H:%M:%S"),
            "user_email": (session.get("user") or {}).get("email"),
            "user_name": (session.get("user") or {}).get("name"),
            "session_expires": session.get("expires"),
        }
        AUTH_INFO_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Google Flow authentication")
    subparsers = parser.add_subparsers(dest="command")

    setup_parser = subparsers.add_parser("setup", help="Open a browser and sign into Flow")
    setup_parser.add_argument("--timeout", type=float, default=LOGIN_TIMEOUT_MINUTES)
    setup_parser.add_argument("--headless", action="store_true")

    subparsers.add_parser("status", help="Show saved auth state")
    subparsers.add_parser("validate", help="Validate the saved auth state against Flow")
    subparsers.add_parser("clear", help="Clear saved auth state")

    reauth_parser = subparsers.add_parser("reauth", help="Clear and re-create auth state")
    reauth_parser.add_argument("--timeout", type=float, default=LOGIN_TIMEOUT_MINUTES)

    args = parser.parse_args()
    manager = AuthManager()

    if args.command == "setup":
        ok = manager.setup_auth(timeout_minutes=args.timeout, headless=args.headless)
        print("Authentication setup complete" if ok else "Authentication setup failed")
        return 0 if ok else 1
    if args.command == "status":
        print(json.dumps(manager.get_auth_info(), indent=2))
        return 0
    if args.command == "validate":
        ok = manager.validate_auth()
        print("Authentication is valid" if ok else "Authentication is invalid")
        return 0 if ok else 1
    if args.command == "clear":
        ok = manager.clear_auth()
        print("Authentication cleared" if ok else "Authentication clear failed")
        return 0 if ok else 1
    if args.command == "reauth":
        ok = manager.reauth(timeout_minutes=args.timeout)
        print("Re-authentication complete" if ok else "Re-authentication failed")
        return 0 if ok else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
