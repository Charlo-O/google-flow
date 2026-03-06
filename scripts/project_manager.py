#!/usr/bin/env python3
"""Local library management for Google Flow projects."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from patchright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_manager import AuthManager
from browser_utils import BrowserFactory, FlowBrowser
from config import FLOW_HOME_URL, FLOW_PROJECT_URL_RE, PROJECT_DATE_RE, PROJECT_LIBRARY_FILE, DATA_DIR


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_project_url(url: str) -> tuple[str, str]:
    match = FLOW_PROJECT_URL_RE.match(url.strip())
    if not match or match.group("asset_id"):
        raise ValueError(f"Invalid Flow project URL: {url}")
    project_id = match.group("project_id")
    return url.strip(), project_id


def normalize_asset_url(url: str) -> tuple[str, str, str]:
    match = FLOW_PROJECT_URL_RE.match(url.strip())
    if not match or not match.group("asset_id"):
        raise ValueError(f"Invalid Flow asset URL: {url}")
    return url.strip(), match.group("project_id"), match.group("asset_id")


def build_asset_url(project_url: str, asset_id: str) -> str:
    normalized_project_url, _ = normalize_project_url(project_url)
    return f"{normalized_project_url.rstrip('/')}/edit/{asset_id}"


class ProjectLibrary:
    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.path = PROJECT_LIBRARY_FILE
        self.projects: dict[str, dict[str, Any]] = {}
        self.active_project_id: str | None = None
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._save()
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        self.projects = data.get("projects", {})
        self.active_project_id = data.get("active_project_id")

    def _save(self) -> None:
        payload = {
            "projects": self.projects,
            "active_project_id": self.active_project_id,
            "updated_at": utc_now(),
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def add_project(
        self,
        *,
        url: str,
        name: str,
        description: str = "",
        tags: Iterable[str] | None = None,
        source: str = "manual",
    ) -> dict[str, Any]:
        normalized_url, project_id = normalize_project_url(url)
        record = {
            "id": project_id,
            "url": normalized_url,
            "name": name.strip() or project_id,
            "description": description.strip(),
            "tags": sorted({tag.strip() for tag in (tags or []) if tag.strip()}),
            "source": source,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "last_seen_at": utc_now(),
        }
        if project_id in self.projects:
            current = self.projects[project_id]
            current.update(
                {
                    "url": record["url"],
                    "name": record["name"] or current["name"],
                    "description": record["description"] or current.get("description", ""),
                    "tags": sorted(set(current.get("tags", [])) | set(record["tags"])),
                    "source": source,
                    "updated_at": utc_now(),
                    "last_seen_at": utc_now(),
                }
            )
        else:
            self.projects[project_id] = record
        if not self.active_project_id:
            self.active_project_id = project_id
        self._save()
        return self.projects[project_id]

    def list_projects(self) -> list[dict[str, Any]]:
        return list(self.projects.values())

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        return self.projects.get(project_id)

    def get_active_project(self) -> dict[str, Any] | None:
        if not self.active_project_id:
            return None
        return self.projects.get(self.active_project_id)

    def activate(self, project_id: str) -> dict[str, Any]:
        if project_id not in self.projects:
            raise ValueError(f"Unknown project: {project_id}")
        self.active_project_id = project_id
        self._save()
        return self.projects[project_id]

    def remove(self, project_id: str) -> bool:
        if project_id not in self.projects:
            return False
        del self.projects[project_id]
        if self.active_project_id == project_id:
            self.active_project_id = next(iter(self.projects), None)
        self._save()
        return True

    def search(self, query: str) -> list[dict[str, Any]]:
        needle = query.lower()
        results = []
        for project in self.projects.values():
            haystacks = [
                project.get("id", ""),
                project.get("name", ""),
                project.get("description", ""),
                " ".join(project.get("tags", [])),
            ]
            if any(needle in value.lower() for value in haystacks):
                results.append(project)
        return results

    def sync_recent(self, limit: int = 25, headless: bool = True) -> list[dict[str, Any]]:
        auth = AuthManager()
        if not auth.validate_auth():
            raise RuntimeError("Flow authentication is required before syncing projects")

        playwright = None
        context = None
        try:
            playwright = sync_playwright().start()
            context = BrowserFactory.launch_persistent_context(playwright, headless=headless)
            page = context.new_page()
            FlowBrowser.load_page(page, FLOW_HOME_URL)
            page.wait_for_timeout(2500)
            discovered = page.evaluate(
                """(maxItems) => {
                    const anchors = Array.from(document.querySelectorAll('a[href*="/tools/flow/project/"]'))
                        .filter((node) => !node.href.includes('/edit/'));
                    const seen = new Set();
                    const rows = [];
                    for (const anchor of anchors) {
                        if (seen.has(anchor.href)) continue;
                        seen.add(anchor.href);
                        const card = anchor.closest('a')?.parentElement?.parentElement || anchor.parentElement;
                        const raw = ((card && card.innerText) || anchor.innerText || '')
                            .split(/\\n+/)
                            .map((line) => line.trim())
                            .filter(Boolean);
                        rows.push({ url: anchor.href, lines: raw.slice(0, 5) });
                        if (rows.length >= maxItems) break;
                    }
                    return rows;
                }""",
                limit,
            )
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

        synced = []
        for item in discovered or []:
            try:
                normalized_url, project_id = normalize_project_url(item["url"])
            except ValueError:
                continue
            lines = item.get("lines") or []
            name = derive_project_name(lines, project_id)
            description = " | ".join(line for line in lines if line != name)
            record = self.add_project(
                url=normalized_url,
                name=name,
                description=description,
                source="sync",
            )
            synced.append(record)
        return synced

    def list_project_assets(
        self,
        *,
        project_url: str,
        kind: str = "all",
        limit: int = 20,
        headless: bool = True,
    ) -> list[dict[str, Any]]:
        auth = AuthManager()
        if not auth.validate_auth():
            raise RuntimeError("Flow authentication is required before listing project assets")

        playwright = None
        context = None
        try:
            playwright = sync_playwright().start()
            context = BrowserFactory.launch_persistent_context(playwright, headless=headless)
            page = context.new_page()
            FlowBrowser.load_page(page, project_url)
            FlowBrowser.wait_for_project_shell(page)
            page.wait_for_timeout(1500)
            assets = page.evaluate(
                """(desiredKind, maxItems) => {
                    const anchors = Array.from(document.querySelectorAll('a[href*="/tools/flow/project/"][href*="/edit/"]'));
                    const rows = [];
                    const seen = new Set();

                    for (const anchor of anchors) {
                        if (seen.has(anchor.href)) continue;
                        seen.add(anchor.href);

                        const card = anchor.closest('button') || anchor.parentElement;
                        const raw = ((card && card.innerText) || anchor.innerText || '')
                            .split(/\\n+/)
                            .map((line) => line.trim())
                            .filter(Boolean);

                        const flattened = raw.join(' | ');
                        const kind = /(play_circle|视频|video)/i.test(flattened) ? 'video' : 'image';
                        if (desiredKind !== 'all' && desiredKind !== kind) continue;

                        rows.push({
                            url: anchor.href,
                            kind,
                            label: flattened,
                        });

                        if (rows.length >= maxItems) break;
                    }
                    return rows;
                }""",
                kind,
                limit,
            )
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

        payload = []
        for item in assets or []:
            try:
                url, project_id, asset_id = normalize_asset_url(item["url"])
            except ValueError:
                continue
            payload.append(
                {
                    "project_id": project_id,
                    "asset_id": asset_id,
                    "url": url,
                    "kind": item.get("kind", "image"),
                    "label": item.get("label", ""),
                }
            )
        return payload


def derive_project_name(lines: list[str], project_id: str) -> str:
    for line in lines:
        if PROJECT_DATE_RE.match(line):
            continue
        if "edit" in line.lower() or "delete" in line.lower():
            continue
        if "修改项目" in line or "删除项目" in line:
            continue
        return line
    return lines[0] if lines else project_id


def print_projects(projects: list[dict[str, Any]], active_project_id: str | None) -> None:
    payload = []
    for project in projects:
        payload.append(
            {
                **project,
                "active": project.get("id") == active_project_id,
            }
        )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage a local Google Flow project library")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add a Flow project URL manually")
    add_parser.add_argument("--url", required=True)
    add_parser.add_argument("--name", required=True)
    add_parser.add_argument("--description", default="")
    add_parser.add_argument("--tags", default="")

    subparsers.add_parser("list", help="List saved projects")

    search_parser = subparsers.add_parser("search", help="Search saved projects")
    search_parser.add_argument("--query", required=True)

    activate_parser = subparsers.add_parser("activate", help="Set the active project")
    activate_parser.add_argument("--id", required=True)

    remove_parser = subparsers.add_parser("remove", help="Remove a saved project")
    remove_parser.add_argument("--id", required=True)

    sync_parser = subparsers.add_parser("sync", help="Import recent projects from Flow home")
    sync_parser.add_argument("--limit", type=int, default=25)
    sync_parser.add_argument("--show-browser", action="store_true")

    assets_parser = subparsers.add_parser("assets", help="List asset edit URLs in a project")
    assets_parser.add_argument("--id", help="Saved project id")
    assets_parser.add_argument("--url", help="Explicit project URL")
    assets_parser.add_argument("--kind", choices=["all", "image", "video"], default="all")
    assets_parser.add_argument("--limit", type=int, default=20)
    assets_parser.add_argument("--show-browser", action="store_true")

    args = parser.parse_args()
    library = ProjectLibrary()

    if args.command == "add":
        tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]
        project = library.add_project(url=args.url, name=args.name, description=args.description, tags=tags)
        print(json.dumps(project, indent=2, ensure_ascii=False))
        return 0
    if args.command == "list":
        print_projects(library.list_projects(), library.active_project_id)
        return 0
    if args.command == "search":
        print_projects(library.search(args.query), library.active_project_id)
        return 0
    if args.command == "activate":
        print(json.dumps(library.activate(args.id), indent=2, ensure_ascii=False))
        return 0
    if args.command == "remove":
        removed = library.remove(args.id)
        print(json.dumps({"removed": removed, "id": args.id}, indent=2))
        return 0 if removed else 1
    if args.command == "sync":
        synced = library.sync_recent(limit=args.limit, headless=not args.show_browser)
        print_projects(synced, library.active_project_id)
        return 0
    if args.command == "assets":
        if args.url:
            project_url, _ = normalize_project_url(args.url)
        elif args.id:
            project = library.get_project(args.id)
            if not project:
                raise SystemExit(f"Unknown project id: {args.id}")
            project_url = project["url"]
        else:
            active = library.get_active_project()
            if not active:
                raise SystemExit("No project specified and no active project is set")
            project_url = active["url"]
        assets = library.list_project_assets(
            project_url=project_url,
            kind=args.kind,
            limit=args.limit,
            headless=not args.show_browser,
        )
        print(json.dumps(assets, indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
