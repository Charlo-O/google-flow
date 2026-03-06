"""Shared configuration for the Google Flow skill."""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

SKILL_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = SKILL_DIR / "data"
BROWSER_STATE_DIR = DATA_DIR / "browser_state"
BROWSER_PROFILE_DIR = BROWSER_STATE_DIR / "browser_profile"
STATE_FILE = BROWSER_STATE_DIR / "state.json"
AUTH_INFO_FILE = DATA_DIR / "auth_info.json"
PROJECT_LIBRARY_FILE = DATA_DIR / "project_library.json"

load_dotenv(SKILL_DIR / ".env")

FLOW_HOME_URL = os.getenv("FLOW_HOME_URL", "https://labs.google/fx/tools/flow")
AUTH_SESSION_URL = os.getenv("FLOW_AUTH_SESSION_URL", "https://labs.google/fx/api/auth/session")
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("FLOW_DEFAULT_TIMEOUT_SECONDS", "600"))
PAGE_LOAD_TIMEOUT_MS = int(os.getenv("FLOW_PAGE_LOAD_TIMEOUT_MS", "45000"))
LOGIN_TIMEOUT_MINUTES = float(os.getenv("FLOW_LOGIN_TIMEOUT_MINUTES", "10"))

BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-first-run",
    "--no-default-browser-check",
]

USER_AGENT = os.getenv(
    "FLOW_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
)

PROMPT_EDITOR_SELECTOR = '[contenteditable="true"][role="textbox"]'
FILE_INPUT_SELECTOR = 'input[type="file"]'

ENTRY_BUTTON_PATTERNS = [
    re.compile(r"create with flow", re.I),
    re.compile(r"get started", re.I),
    re.compile(r"new project", re.I),
    re.compile(r"create", re.I),
    re.compile(r"新建项目"),
    re.compile(r"创建"),
]

COMPOSER_ADD_BUTTON_PATTERNS = [
    re.compile(r"add_2.*(create|创建)", re.I),
]

COMPOSER_SUBMIT_BUTTON_PATTERNS = [
    re.compile(r"arrow_forward.*(create|创建|generate)", re.I),
]

SETTINGS_BUTTON_PATTERNS = [
    re.compile(r"(nano banana|veo).*(crop_|x[1-4])", re.I),
    re.compile(r"^(image|video|图片|视频).*(crop_|x[1-4])", re.I),
]

IMAGE_TAB_PATTERNS = [re.compile(r"\bimage\b", re.I), re.compile(r"图片")]
VIDEO_TAB_PATTERNS = [re.compile(r"\bvideo\b", re.I), re.compile(r"视频")]
FRAMES_TAB_PATTERNS = [re.compile(r"\bframes\b", re.I), re.compile(r"帧")]
INGREDIENTS_TAB_PATTERNS = [re.compile(r"\bingredients\b", re.I), re.compile(r"素材"), re.compile(r"成分")]

LANDSCAPE_TAB_PATTERNS = [re.compile(r"landscape", re.I), re.compile(r"横向")]
PORTRAIT_TAB_PATTERNS = [re.compile(r"portrait", re.I), re.compile(r"纵向")]

START_FRAME_PATTERNS = [re.compile(r"^start$", re.I), re.compile(r"^起始$")]
END_FRAME_PATTERNS = [re.compile(r"^end$", re.I), re.compile(r"^结束$")]

FLOW_PROJECT_URL_RE = re.compile(
    r"^https://labs\.google/fx(?:/[a-z]{2})?/tools/flow/project/(?P<project_id>[^/?#]+?)"
    r"(?:/edit/(?P<asset_id>[^/?#]+))?/?(?:[?#].*)?$",
    re.I,
)

PROJECT_DATE_RE = re.compile(r"^[A-Z][a-z]{2}\s+\d{2}\s+-\s+\d{2}:\d{2}$")
