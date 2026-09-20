# AI 视觉识图与 DeepSeek 文案生成设计

## 背景

当前桌面端已经能上传本地图片、调用后端 `/api/ai/image-copy` 生成小红书标题、正文和标签。但后端 `DeepSeekImageCopyClient` 仍是稳定草稿返回，没有真正联网；同时 DeepSeek 不适合作为图片识别主力。后续要采用“双模型链路”：视觉模型负责识图，DeepSeek 负责小红书文案二次改写。

## 目标

第一版增强实现以下能力：

- 在系统配置中分别保存“视觉识图模型”和“文案生成模型”的 Key、接口地址、模型名。
- 视觉识图模型优先按豆包/火山方舟兼容 OpenAI 调用形态设计，后续填入豆包 Key 后可开启真实识图。
- DeepSeek 保留为文案生成模型，负责把视觉识别结果改写成小红书种草风格标题、正文和标签。
- `/api/ai/image-copy` 从单步假生成升级为两段式流程：图片素材 -> 视觉分析 -> 文案生成。
- 未配置视觉 Key 或 DeepSeek Key 时，系统仍可用本地 fallback 返回草稿，但响应内容要明确来自本地素材信息，不伪装成真实识图。

## 非目标

- 不在本阶段实现视频解析。
- 不在本阶段接入剪映或视频剪辑。
- 不强制绑定某一家视觉厂商，豆包作为默认推荐 provider，接口抽象保留 GPT/Gemini 扩展空间。
- 不在测试中发起真实外网调用，所有联网行为通过 mock 验证请求结构。

## 推荐架构

### 1. 设置持久化

新增后端设置能力，基于已有 SQLite `app_setting` 表保存 AI 配置。

设置分为两个槽位：

- `vision`：负责图片识别，默认 provider 为 `doubao`。
- `copywriting`：负责文案生成，默认 provider 为 `deepseek`。

每个槽位保存：

- `provider`
- `api_key`
- `base_url`
- `model`
- `enabled`

API 返回配置时不返回完整 Key，只返回：

- `has_key`
- `masked_key`
- `provider`
- `base_url`
- `model`
- `enabled`

第一版本地单机版可先把 Key 存在 SQLite；后续正式交付可升级为 Windows DPAPI 或凭据管理器。

### 2. AI 调用链路

后端新增三个边界：

- `VisionAnalysisClient`：输入图片路径，输出结构化素材理解结果。
- `CopywritingClient`：输入素材理解结果、内容方向、补充要求，输出小红书标题、正文、标签。
- `ImageCopyPipeline`：编排“视觉分析 -> 文案生成 -> fallback”的整体流程。

视觉分析输出建议结构：

```json
{
  "provider": "doubao",
  "summary": "图片展示一款浅色连衣裙，整体风格优雅通勤。",
  "product_name": "浅色连衣裙",
  "scene": "门店试穿/日常穿搭",
  "colors": ["米白", "浅杏"],
  "materials": ["轻薄面料"],
  "selling_points": ["显气质", "适合通勤", "版型利落"],
  "raw_text": "视觉模型原始摘要"
}
```

文案生成输入要包含：

- 视觉分析结果
- 用户选择的内容方向，默认“小红书种草”
- 用户补充要求
- 标题最长 20 个字符
- 标签最多 10 个

文案生成输出沿用当前 `ImageCopyResult`：

```json
{
  "title": "浅杏连衣裙太显气质",
  "body": "小红书正文...",
  "tags": ["禾一斯", "小红书种草", "通勤穿搭"]
}
```

### 3. fallback 策略

如果视觉 Key 未配置：

- 后端读取图片文件名、数量、格式等本地素材信息。
- 生成一个“本地素材摘要”，说明尚未启用视觉模型。
- 继续交给 DeepSeek 文案模型；如果 DeepSeek 也未配置，则返回稳定本地草稿。

如果视觉模型调用失败：

- 返回明确错误，前端提示“视觉识图失败，请检查 Key、接口地址或模型名”。
- 不静默伪装成真实识图成功。

如果 DeepSeek 调用失败：

- 返回明确错误，前端提示“文案生成失败，请检查 DeepSeek Key 或接口地址”。

### 4. 前端系统配置

`系统配置` 页面中的 AI API KEY 区域改为两个配置块：

- 视觉识图 API
  - 服务商：豆包、GPT、Gemini
  - API KEY
  - 接口地址
  - 模型
  - 保存 / 清除

- 文案生成 API
  - 服务商：DeepSeek
  - API KEY
  - 接口地址
  - 模型
  - 保存 / 清除

页面只展示 masked key，不把完整 Key 回显到输入框。

### 5. 后端接口

新增：

- `GET /api/settings/ai`
  - 获取 AI 配置状态。

- `PUT /api/settings/ai/{slot}`
  - 保存 `vision` 或 `copywriting` 配置。

- `DELETE /api/settings/ai/{slot}/key`
  - 清除指定槽位 Key。

修改：

- `POST /api/ai/image-copy`
  - 内部改为调用 `ImageCopyPipeline`。
  - 响应仍保持 `ImageCopyResult`，不破坏前端现有调用。

## 测试策略

后端：

- 设置仓库能写入、读取、更新、清除配置。
- 设置 API 不泄露完整 Key。
- 未配置 Key 时，`image-copy` 返回 fallback 草稿。
- 配置视觉 Key 和 DeepSeek Key 时，请求会按顺序调用视觉 client 与文案 client。
- mock 外部请求，验证 headers、base_url、model、图片 base64/data URL 结构。
- 外部调用失败时返回统一错误。

前端：

- 系统配置页能加载 AI 配置状态。
- 保存视觉配置调用正确 API。
- 保存 DeepSeek 配置调用正确 API。
- 清除 Key 后状态变为未保存。
- 智能创作页继续调用 `/api/ai/image-copy`，无需知道内部是双模型链路。

## 交付边界

本阶段可以先完成“配置持久化 + 双模型调用链路 + mock 验证 + UI 配置入口”。豆包真实 Key 后续填入后，使用同一套配置入口开启真实视觉识图。
