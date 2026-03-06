# Google Flow Workflow Notes

Use this file when the UI drifts and the selectors in `scripts/config.py` need to be updated.

## Observed URLs

- Home: `https://labs.google/fx/tools/flow`
- Project: `https://labs.google/fx/<locale>/tools/flow/project/<project-id>`
- Asset edit page: `https://labs.google/fx/<locale>/tools/flow/project/<project-id>/edit/<asset-id>`
- Auth session endpoint: `https://labs.google/fx/api/auth/session`

## Observed UI On March 6, 2026

Authenticated home screen:
- A visible `New project` / `新建项目` button exists.
- Recent projects are rendered as links whose `href` contains `/tools/flow/project/` and does not contain `/edit/`.

Project screen:
- The prompt editor is a contenteditable `div` with `role="textbox"`.
- The composer row contains three buttons:
  - left: `add_2 Create` / `add_2 创建`
  - middle: settings button containing the current mode, aspect ratio, and output count
  - right: `arrow_forward Create` / `arrow_forward 创建`
- The settings popover exposes:
  - media type tabs: `Image`, `Video`
  - video sub-tabs: `Frames`, `Ingredients`
  - aspect ratio tabs: landscape and portrait
  - output count tabs: `x1` through `x4`
  - model dropdowns such as `Nano Banana 2` and `Veo 3.1 - Fast`

Frames mode:
- Start and end frame drop zones are visible as `Start` / `起始` and `End` / `结束`.
- A hidden `input[type=file]` with `accept="image/*"` is present.

Ingredient picker:
- Opening the left composer button exposes a dialog with search, upload, and project asset browsing.
- The same hidden `input[type=file]` is used for uploading prompt assets.

Asset edit page:
- Toolbar buttons include `Crop`, `Select`, and `Draw`.
- The edit prompt editor is the same contenteditable `div`.
- The top-right controls include `Download`, `Hide history`, and `Done`.
- `Crop` exposes preset ratios and keyboard-accessible corner handles.
- `Select` exposes at least `Rectangle` and `Lasso`.
- `Draw` exposes `Brush`, `Text`, and `Rectangle`, plus stroke width and undo/redo controls.
- `Draw -> Text` creates a temporary `textarea` on click. Fill it, then press `Enter` to commit the overlay onto the image. `Escape` cancels it.
- The text-size slider is keyboard-accessible with `aria-valuemin="1"`, `aria-valuemax="50"`, and observed default `aria-valuenow="18"`.
- Editing an existing asset stays on the same `/edit/<asset-id>` URL and appends history; do not wait for a new asset URL the way project-level generation does.

## Official Help Articles Used

- `Create videos in Flow`: https://support.google.com/labs/answer/16353334?hl=en
- `Create & edit images in Flow`: https://support.google.com/labs/answer/16729550?hl=en
- Flow landing page and FAQ:
  - https://labs.google/fx/tools/flow
  - https://labs.google/fx/tools/flow/faq

## Implementation Guidance

- Prefer URL pattern matching over brittle CSS class names.
- Prefer role- and text-based Playwright locators where the accessible name includes both icon text and visible label.
- Keep auth validation tied to `/fx/api/auth/session`; it is a stronger signal than landing-page redirects.
- When patching file upload behavior, inspect `input[type=file]` first before adding more complex element targeting.
