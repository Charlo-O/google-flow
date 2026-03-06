#!/usr/bin/env python3
"""Universal runner for Google Flow skill scripts."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def get_venv_python() -> Path:
    skill_dir = Path(__file__).resolve().parent.parent
    venv_dir = skill_dir / ".venv"
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def ensure_venv() -> Path:
    skill_dir = Path(__file__).resolve().parent.parent
    venv_dir = skill_dir / ".venv"
    ready_file = venv_dir / ".flow-skill-ready"
    setup_script = skill_dir / "scripts" / "setup_environment.py"
    if not venv_dir.exists() or not ready_file.exists():
        result = subprocess.run([sys.executable, str(setup_script)])
        if result.returncode != 0:
            raise SystemExit(result.returncode)
    return get_venv_python()


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/run.py <script_name> [args...]")
        print("Available scripts: auth_manager.py, project_manager.py, generate_media.py, edit_image.py, cleanup_manager.py")
        return 1

    script_name = sys.argv[1]
    script_args = sys.argv[2:]
    if script_name.startswith("scripts/"):
        script_name = script_name[8:]
    if not script_name.endswith(".py"):
        script_name += ".py"

    skill_dir = Path(__file__).resolve().parent.parent
    script_path = skill_dir / "scripts" / script_name
    if not script_path.exists():
        print(f"Script not found: {script_name}")
        return 1

    venv_python = ensure_venv()
    result = subprocess.run([str(venv_python), str(script_path), *script_args])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
