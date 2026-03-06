# Google Flow Skill

`Google Flow Skill` 是一个面向 Codex 的自动化技能，用持久化浏览器会话操作 [Google Flow](https://labs.google/fx/tools/flow)。

它延续了 `notebooklm-skill` 的整体结构：

- 一个统一运行入口
- 一个登录管理器
- 一个本地项目库
- 按工作流拆分的任务脚本

这个 skill 目前支持：

- 持久化保存和复用 Flow 登录态
- 同步最近访问的 Flow 项目到本地项目库
- 搜索、激活和管理项目
- 在现有项目中生成图片和视频
- 上传 ingredient 图片或视频首尾帧
- 列出项目里的图片和视频编辑地址
- 对已有图片执行裁剪、框选重绘、涂抹重绘、文本叠加和整图 prompt 编辑

## 环境要求

- Windows
- Python 3.10 或更高版本
- 已安装 Google Chrome
- 可访问 Google Flow 的 Google 账号

Python 依赖：

- `patchright==1.55.2`
- `python-dotenv==1.0.1`

## 目录结构

```text
google-flow/
├── SKILL.md
├── README.md
├── README.zh-CN.md
├── agents/
├── references/
└── scripts/
```

关键脚本：

- `scripts/run.py`：环境自举和统一入口
- `scripts/auth_manager.py`：登录态管理
- `scripts/project_manager.py`：项目库和 asset 列表
- `scripts/generate_media.py`：图片和视频生成
- `scripts/edit_image.py`：图片编辑
- `scripts/cleanup_manager.py`：本地清理

## 快速开始

1. 检查当前登录状态：

```bash
python scripts/run.py auth_manager.py status
```

2. 如果还没登录，执行：

```bash
python scripts/run.py auth_manager.py setup
```

3. 从 Flow 首页同步最近项目：

```bash
python scripts/run.py project_manager.py sync
python scripts/run.py project_manager.py list
```

4. 激活一个项目：

```bash
python scripts/run.py project_manager.py activate --id PROJECT_ID
```

5. 在该项目中继续生成或编辑媒体。

## 登录管理

skill 会把浏览器登录状态保存到 `data/browser_state/`，后续运行会自动复用。

常用命令：

```bash
python scripts/run.py auth_manager.py status
python scripts/run.py auth_manager.py setup
python scripts/run.py auth_manager.py validate
python scripts/run.py auth_manager.py reauth
python scripts/run.py auth_manager.py clear
```

## 项目管理

同步、搜索、激活、查看项目内容：

```bash
python scripts/run.py project_manager.py sync
python scripts/run.py project_manager.py list
python scripts/run.py project_manager.py search --query storyboard
python scripts/run.py project_manager.py activate --id PROJECT_ID
python scripts/run.py project_manager.py assets --id PROJECT_ID --kind image
python scripts/run.py project_manager.py assets --id PROJECT_ID --kind video
```

## 生成图片

生成一张竖图：

```bash
python scripts/run.py generate_media.py \
  --project-id PROJECT_ID \
  --mode image \
  --prompt "一只开心跳舞的小狗，皮克斯 3D 动画风格，暖色电影级灯光" \
  --model "Nano Banana 2" \
  --aspect-ratio portrait \
  --outputs 1
```

## 生成视频

纯文本生成视频：

```bash
python scripts/run.py generate_media.py \
  --project-id PROJECT_ID \
  --mode video \
  --video-mode ingredients \
  --prompt "镜头手持穿过下雨的霓虹小巷" \
  --model "Veo 3.1 - Fast" \
  --aspect-ratio landscape \
  --outputs 1
```

基于首尾帧生成视频：

```bash
python scripts/run.py generate_media.py \
  --project-id PROJECT_ID \
  --mode video \
  --video-mode frames \
  --prompt "保持同一角色设计，动作自然流畅，有电影感的连续运动" \
  --start-frame "C:/absolute/path/start.png" \
  --end-frame "C:/absolute/path/end.png" \
  --model "Veo 3.1 - Fast" \
  --aspect-ratio portrait \
  --outputs 1
```

## 编辑图片

先列出项目里的图片编辑地址：

```bash
python scripts/run.py project_manager.py assets --id PROJECT_ID --kind image
```

整图 prompt 编辑：

```bash
python scripts/run.py edit_image.py \
  --asset-url "https://labs.google/fx/zh/tools/flow/project/.../edit/..." \
  --tool full \
  --prompt "把整体氛围改成更有情绪的黄昏场景"
```

矩形框选重绘：

```bash
python scripts/run.py edit_image.py \
  --asset-url "https://labs.google/fx/zh/tools/flow/project/.../edit/..." \
  --tool select-box \
  --box "0.18,0.20,0.55,0.48" \
  --prompt "把这块区域替换成下雨的城市天际线"
```

矩形涂抹重绘：

```bash
python scripts/run.py edit_image.py \
  --asset-url "https://labs.google/fx/zh/tools/flow/project/.../edit/..." \
  --tool draw-rect \
  --box "0.12,0.58,0.38,0.86" \
  --prompt "去掉前景物体并恢复背景"
```

自由画笔重绘：

```bash
python scripts/run.py edit_image.py \
  --asset-url "https://labs.google/fx/zh/tools/flow/project/.../edit/..." \
  --tool draw-brush \
  --points "0.20,0.62;0.26,0.64;0.31,0.69;0.36,0.75" \
  --prompt "擦除这个物体并自然补全背景"
```

添加文字：

```bash
python scripts/run.py edit_image.py \
  --asset-url "https://labs.google/fx/zh/tools/flow/project/.../edit/..." \
  --tool text \
  --point "0.30,0.40" \
  --text-size 24 \
  --text "OPENING SOON"
```

裁剪：

```bash
python scripts/run.py edit_image.py \
  --asset-url "https://labs.google/fx/zh/tools/flow/project/.../edit/..." \
  --tool crop \
  --crop-preset square \
  --box "0.12,0.18,0.82,0.78"
```

坐标规则：

- `--box` 和 `--points` 使用 `0` 到 `1` 的归一化坐标
- `--point` 也使用同样的归一化坐标体系
- `--text` 目前建议单行
- `--text-size` 对应 Flow 文本工具里的字号滑杆，单位是 px

## 使用说明

- 一律通过 `python scripts/run.py ...` 调用脚本
- 优先执行 `project_manager.py sync`，不要先手动维护项目 URL
- 上传 ingredient 图片和视频帧时使用绝对路径
- 图片生成、视频生成和 prompt 编辑可能会消耗 Flow 点数

## 当前限制

- 还没有接入 SceneBuilder 自动化
- 还没有做下载自动化
- Flow 不同语言环境下文案可能略有差异，必要时需要调整选择器

## 参考资料

- 内部流程记录：`references/workflow.md`
- Flow 官网：<https://labs.google/fx/tools/flow>
- Flow 视频帮助：<https://support.google.com/labs/answer/16353334?hl=en>
- Flow 图片帮助：<https://support.google.com/labs/answer/16729550?hl=en>
