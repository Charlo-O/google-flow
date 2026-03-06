#!/usr/bin/env python3
"""Create and maintain the skill-local virtual environment."""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path


class SkillEnvironment:
    def __init__(self) -> None:
        self.skill_dir = Path(__file__).resolve().parent.parent
        self.venv_dir = self.skill_dir / ".venv"
        self.ready_file = self.venv_dir / ".flow-skill-ready"
        self.requirements_file = self.skill_dir / "requirements.txt"
        if os.name == "nt":
            self.venv_python = self.venv_dir / "Scripts" / "python.exe"
            self.venv_pip = self.venv_dir / "Scripts" / "pip.exe"
        else:
            self.venv_python = self.venv_dir / "bin" / "python"
            self.venv_pip = self.venv_dir / "bin" / "pip"

    def ensure(self) -> bool:
        if not self.venv_dir.exists():
            venv.create(self.venv_dir, with_pip=True)

        subprocess.run([str(self.venv_python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
        subprocess.run([str(self.venv_python), "-m", "pip", "install", "-r", str(self.requirements_file)], check=True)
        subprocess.run([str(self.venv_python), "-m", "patchright", "install", "chrome"], check=True)
        self.ready_file.write_text("ready\n", encoding="utf-8")
        return True


def main() -> int:
    env = SkillEnvironment()
    try:
        env.ensure()
    except subprocess.CalledProcessError as exc:
        print(f"Environment setup failed: {exc}")
        return exc.returncode or 1
    print(f"Environment ready: {env.venv_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
