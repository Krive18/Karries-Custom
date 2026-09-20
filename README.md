# KARRIES 禾一斯 · 小红书智能运营工作台

面向小红书内容团队的一站式智能运营平台：用 AI 拆解爆款、生成脚本与图文，统一管理矩阵账号的定时发布，并内置会员计费、算力结算与交付审核工作流。

线上环境：https://hys-karries.com

## 三个端口

| 端 | 路径 | 面向角色 | 主要能力 |
|---|---|---|---|
| 用户端 | `/` | 客户公司运营员工 | Karries AI 创作、爆款解析、视频创作、产品知识库、AI 翻译、内容收藏/审核、发布计划、账号管理、每日签到与算力钱包 |
| 管理端 | `/manager/` | 客户公司负责人 | 运营总览、员工账号、算力充值与会员订阅（扫码支付+审核）、爆款解析记录、算力流水 |
| 开发者端 | `/developer/` | 平台运营方（内部） | 任务排查、视频交付、AI Provider 配置、告警事件、租户会员手动调整、充值/会员订单审核、审计日志 |

## 核心功能

- **爆款解析**：上传视频或粘贴链接，多模态大模型拆解开场钩子、结构、节奏与话术，反向生成可复用的 AI 视频提示词（大视频自动 ffmpeg 压缩后送解析）
- **Karries AI**：个性化画像 + 模板库的对话式创作助手，一键产出图文/脚本
- **矩阵发布**：多小红书账号扫码托管，图文/视频定时发布，独立 worker 执行队列，失败重试与安全策略
- **会员与算力**：四档会员方案（免费/Pro/Max/存储大），月度算力发放与次月清零、每日签到、到期自动回退免费版；租户级手动升降级
- **交付工作流**：视频剪辑多版本交付、返修、字幕/音频资源归档
- **界面体验**：亮/暗主题、界面缩放三档（紧凑/标准/大字）、备案页脚合规展示

## 技术栈

- **后端**：Python 3.12 + FastAPI + MySQL（自研连接池），uvicorn 运行，systemd 托管
- **前端**：React 19 + TypeScript + Vite 8，一套代码三端构建（customer/manager/developer）
- **桌面端**：Electron（内嵌后端可选）
- **AI 集成**：豆包（火山方舟）多模态、DeepSeek 等 OpenAI 兼容接口，按租户可配
- **浏览器自动化**：patchright（小红书扫码登录与发布）

## 生产架构

```
nginx (443/80)
 ├── /            → 用户端静态文件
 ├── /manager/    → 管理端静态文件
 ├── /developer/  → 开发者端静态文件
 └── /api/        → 127.0.0.1:8765 (uvicorn / FastAPI)
                      ├── MySQL（业务数据）
                      ├── karries-publish-worker（发布执行）
                      └── karries-backup.timer（每日备份）
```

部署与保数据升级见 `deploy/server/`（install.sh、upgrade-preserve-data.sh、smoke-test.sh）。

## 本地开发

```bash
# 后端三进程 + 前端三 dev server，一键启动（Windows PowerShell）
powershell -ExecutionPolicy Bypass -File scripts/start_local_portals.ps1
# 用户端 http://127.0.0.1:5174  管理端 :5175  开发者端 :5176
```

```bash
# 后端测试
cd backend && ../.venv/Scripts/python -m pytest -q
# 前端测试与类型检查
cd apps/desktop && npm run test && npm run typecheck
```

打生产升级包：`python scripts/build_server_delivery.py --output-root 交付文件 --release-name karries-server-<时间戳>-upgrade`

## 目录速览

```
backend/          FastAPI 后端（api / services / repositories / workers / integrations）
apps/desktop/     三端前端 + Electron
deploy/server/    服务器安装、升级、回滚、备份、HTTPS 脚本
web/              三端静态构建产物（由 apps/desktop 构建生成）
external/         小红书上传适配层
docs/             业务与设计文档
scripts/          交付打包与本地启动脚本
```

## 合规

- ICP 备案：粤ICP备2025511993号-3（页脚悬挂并链接至工信部备案查询页）
- 公安联网备案：办理中，编号下发后页脚同步展示
