#!/usr/bin/env python3
"""Preview or clear local Google Flow skill data."""

from __future__ import annotations

import argparse
import json
import shutil

from config import AUTH_INFO_FILE, DATA_DIR, PROJECT_LIBRARY_FILE, STATE_FILE


def preview() -> dict:
    return {
        "data_dir": str(DATA_DIR),
        "exists": DATA_DIR.exists(),
        "files": {
            "project_library": str(PROJECT_LIBRARY_FILE) if PROJECT_LIBRARY_FILE.exists() else None,
            "state_file": str(STATE_FILE) if STATE_FILE.exists() else None,
            "auth_info_file": str(AUTH_INFO_FILE) if AUTH_INFO_FILE.exists() else None,
        },
    }


def clear_data(preserve_library: bool) -> None:
    if not DATA_DIR.exists():
        return
    if preserve_library and PROJECT_LIBRARY_FILE.exists():
        library_bytes = PROJECT_LIBRARY_FILE.read_bytes()
        shutil.rmtree(DATA_DIR)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        PROJECT_LIBRARY_FILE.write_bytes(library_bytes)
        return
    shutil.rmtree(DATA_DIR)


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or clear Google Flow skill data")
    parser.add_argument("--confirm", action="store_true", help="Actually delete the data directory")
    parser.add_argument("--preserve-library", action="store_true")
    args = parser.parse_args()

    if not args.confirm:
        print(json.dumps(preview(), indent=2))
        return 0

    clear_data(preserve_library=args.preserve_library)
    print(json.dumps({"cleared": True, "preserve_library": args.preserve_library}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
