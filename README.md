# Google Flow Skill

[![GitHub](https://img.shields.io/badge/github-Charlo--O%2Fgoogle--flow-181717?logo=github)](https://github.com/Charlo-O/google-flow)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D4?logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![Flow](https://img.shields.io/badge/target-Google%20Flow-4285F4)](https://labs.google/fx/tools/flow)

Google Flow Skill is a Codex skill for automating [Google Flow](https://labs.google/fx/tools/flow) with a persistent browser session.

It follows the same architecture as `notebooklm-skill`:

- one bootstrap runner
- one authentication manager
- one local project library
- one task script per workflow

This skill can:

- keep a reusable Flow login session
- sync recent Flow projects into a local library
- activate and search projects
- generate images and videos in an existing Flow project
- upload ingredient images or start/end frames
- list image and video asset edit URLs inside a project
- edit existing Flow images with crop, selection masks, draw masks, text overlays, and prompt-based revisions

## Navigation

- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Implemented Workflows](#implemented-workflows)
- [Generate Images](#generate-images)
- [Generate Videos](#generate-videos)
- [Edit Images](#edit-images)
- [Public Repo Notes](#public-repo-notes)
- [Current Limitations](#current-limitations)

## Implemented Workflows

| Workflow | Status | Notes |
| --- | --- | --- |
| Flow authentication | Ready | Persistent browser session stored locally |
| Recent project sync | Ready | Scrapes recent projects from the signed-in Flow home page |
| Local project activation/search | Ready | Keeps a local project library for repeat runs |
| Image generation | Ready | Supports model, aspect ratio, and output count |
| Video generation | Ready | Supports `ingredients` and `frames` modes |
| Ingredient uploads | Ready | Uses absolute local file paths |
| Existing image edits | Ready | Full edit, select-box, draw-rect, draw-brush, crop, text |
| SceneBuilder automation | Not included | Still out of scope |

## Requirements

- Windows with Python 3.10+
- Google Chrome installed
- A Google account with access to Flow

Python dependencies:

- `patchright==1.55.2`
- `python-dotenv==1.0.1`

## Layout

```text
google-flow/
├── SKILL.md
├── README.md
├── README.zh-CN.md
├── agents/
├── references/
└── scripts/
```

Key scripts:

- `scripts/run.py`: environment bootstrap and entrypoint
- `scripts/auth_manager.py`: persistent login state
- `scripts/project_manager.py`: local project library and asset listing
- `scripts/generate_media.py`: image and video generation
- `scripts/edit_image.py`: image editing workflows
- `scripts/cleanup_manager.py`: local cleanup helper

## Quick Start

1. Check authentication:

```bash
python scripts/run.py auth_manager.py status
```

2. If needed, sign in to Flow:

```bash
python scripts/run.py auth_manager.py setup
```

3. Sync recent projects from the signed-in Flow home page:

```bash
python scripts/run.py project_manager.py sync
python scripts/run.py project_manager.py list
```

4. Activate a project:

```bash
python scripts/run.py project_manager.py activate --id PROJECT_ID
```

5. Generate or edit media inside that project.

## Authentication

The skill stores browser state in `data/browser_state/` and reuses it on later runs.

Useful commands:

```bash
python scripts/run.py auth_manager.py status
python scripts/run.py auth_manager.py setup
python scripts/run.py auth_manager.py validate
python scripts/run.py auth_manager.py reauth
python scripts/run.py auth_manager.py clear
```

## Project Management

Sync, search, activate, and inspect projects:

```bash
python scripts/run.py project_manager.py sync
python scripts/run.py project_manager.py list
python scripts/run.py project_manager.py search --query storyboard
python scripts/run.py project_manager.py activate --id PROJECT_ID
python scripts/run.py project_manager.py assets --id PROJECT_ID --kind image
python scripts/run.py project_manager.py assets --id PROJECT_ID --kind video
```

## Generate Images

Create one portrait image:

```bash
python scripts/run.py generate_media.py \
  --project-id PROJECT_ID \
  --mode image \
  --prompt "A small dog dancing joyfully, Pixar-style 3D character, warm cinematic light" \
  --model "Nano Banana 2" \
  --aspect-ratio portrait \
  --outputs 1
```

## Generate Videos

Generate a video from text:

```bash
python scripts/run.py generate_media.py \
  --project-id PROJECT_ID \
  --mode video \
  --video-mode ingredients \
  --prompt "A handheld tracking shot through a rainy neon alley" \
  --model "Veo 3.1 - Fast" \
  --aspect-ratio landscape \
  --outputs 1
```

Generate a video from frames:

```bash
python scripts/run.py generate_media.py \
  --project-id PROJECT_ID \
  --mode video \
  --video-mode frames \
  --prompt "The same character moves naturally with smooth cinematic motion" \
  --start-frame "C:/absolute/path/start.png" \
  --end-frame "C:/absolute/path/end.png" \
  --model "Veo 3.1 - Fast" \
  --aspect-ratio portrait \
  --outputs 1
```

## Edit Images

List available image edit URLs first:

```bash
python scripts/run.py project_manager.py assets --id PROJECT_ID --kind image
```

Full-image prompt edit:

```bash
python scripts/run.py edit_image.py \
  --asset-url "https://labs.google/fx/zh/tools/flow/project/.../edit/..." \
  --tool full \
  --prompt "Turn this into a moody dusk scene"
```

Selection mask edit:

```bash
python scripts/run.py edit_image.py \
  --asset-url "https://labs.google/fx/zh/tools/flow/project/.../edit/..." \
  --tool select-box \
  --box "0.18,0.20,0.55,0.48" \
  --prompt "Replace this area with a rainy city skyline"
```

Rectangle mask edit:

```bash
python scripts/run.py edit_image.py \
  --asset-url "https://labs.google/fx/zh/tools/flow/project/.../edit/..." \
  --tool draw-rect \
  --box "0.12,0.58,0.38,0.86" \
  --prompt "Remove the foreground object"
```

Brush mask edit:

```bash
python scripts/run.py edit_image.py \
  --asset-url "https://labs.google/fx/zh/tools/flow/project/.../edit/..." \
  --tool draw-brush \
  --points "0.20,0.62;0.26,0.64;0.31,0.69;0.36,0.75" \
  --prompt "Erase this object and blend the background naturally"
```

Text overlay:

```bash
python scripts/run.py edit_image.py \
  --asset-url "https://labs.google/fx/zh/tools/flow/project/.../edit/..." \
  --tool text \
  --point "0.30,0.40" \
  --text-size 24 \
  --text "OPENING SOON"
```

Crop:

```bash
python scripts/run.py edit_image.py \
  --asset-url "https://labs.google/fx/zh/tools/flow/project/.../edit/..." \
  --tool crop \
  --crop-preset square \
  --box "0.12,0.18,0.82,0.78"
```

Coordinate rules:

- `--box` and `--points` use normalized values from `0` to `1`
- `--point` uses the same normalized coordinate system
- `--text` should be single-line
- `--text-size` maps to Flow's text-size slider in px

## Notes

- Always run scripts through `python scripts/run.py ...`
- Prefer syncing recent projects before adding project URLs manually
- Use absolute file paths for ingredient images and video frames
- Generation and prompt-based edits may consume Flow credits

## Public Repo Notes

This public repository contains only the skill source code and documentation.

It does not publish:

- browser login state
- Flow cookies or session files
- downloaded media assets
- local virtual environments
- `.env` files

Those runtime files are excluded by `.gitignore`, especially `data/`, `.venv/`, and `.env`.

## Current Limitations

- SceneBuilder automation is not included
- Download automation is not included
- Flow UI labels may vary by locale and can require selector updates

## References

- Internal workflow notes: `references/workflow.md`
- Official Flow landing page: <https://labs.google/fx/tools/flow>
- Flow video help: <https://support.google.com/labs/answer/16353334?hl=en>
- Flow image help: <https://support.google.com/labs/answer/16729550?hl=en>
