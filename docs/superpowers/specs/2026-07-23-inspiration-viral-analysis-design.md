# 灵感对话与爆款解析优先落地技术设计

## 1. 目标

本文档用于定义“灵感对话”和“爆款解析”两个模块的优先落地方案。它们是主线产品中最先需要完成的 AI 入口：

- 灵感对话：让禾一斯员工通过对话获得选题、标题、脚本、种草角度、发布策略等运营建议。
- 爆款解析：让禾一斯员工上传参考视频或填写参考信息，拆解爆款视频结构，并沉淀为可复用的小红书创作方案。

两个模块必须作为独立菜单呈现，不能混在一个页面中；同时它们都需要被管理端查看完整内容，以便禾一斯老板和管理层掌握团队选题、素材方向和 AI 使用情况。

## 2. 优先级判断

推荐先实现灵感对话，再实现爆款解析。

原因：

- 灵感对话只依赖 DeepSeek 文本生成，当前最容易形成真实可用闭环。
- 爆款解析最终需要豆包等视频理解能力，当前应先完成任务、文件、状态、结果结构和页面，Provider 后续可替换。
- 两个模块都需要 AI 调用日志和算力扣费，先抽出基础服务可以避免重复代码。

落地顺序：

1. AI 文本调用基础层。
2. 灵感对话后端。
3. 灵感对话用户端页面。
4. 管理端灵感对话查看。
5. 爆款解析任务后端。
6. 爆款解析用户端页面。
7. 管理端爆款解析查看。
8. AI 调用日志和算力扣费接入。

## 3. 共享 AI 基础层

现有 `backend/app/api/ai.py` 已有图文文案生成入口，但不应继续承载所有 AI 业务。新增模块时应抽象出共享 AI 服务层。

建议结构：

- `backend/app/services/ai_provider_service.py`：统一封装 DeepSeek、豆包等 Provider 调用。
- `backend/app/services/ai_usage_service.py`：记录 AI 调用日志、耗时、消耗算力和错误信息。
- `backend/app/services/credit_charge_service.py`：统一处理算力扣费和失败回滚。
- `backend/app/integrations/deepseek.py`：继续作为 DeepSeek HTTP 适配层。
- `backend/app/integrations/doubao.py`：预留豆包视频理解适配层，等 Key 和接口确定后接入。

第一版要求：

- DeepSeek Key 不写死在代码中，优先从配置或环境变量读取。
- AI Provider 返回失败时，业务接口必须返回可理解错误。
- AI 调用必须记录日志，即使失败也应记录失败原因。
- 扣费规则先预留接口，若团队共享钱包尚未完全改造，可先记录 `business_type` 和预估消耗，后续切换到正式扣费。

## 4. 灵感对话

### 4.1 用户价值

灵感对话是禾一斯员工的运营助手，不是普通聊天工具。它需要围绕小红书运营场景提供答案。

典型问题：

- 这个产品适合做哪些小红书种草角度？
- 按这个账号定位，帮我写 10 个标题。
- 这个视频脚本开头不够吸引人，帮我优化前三秒钩子。
- 今天适合发什么选题？
- 这个产品能不能换一个更像真实体验的表达？

### 4.2 用户端页面

用户端菜单名称：`灵感对话`。

页面布局建议：

- 左侧：会话列表，支持新建、搜索、按产品或时间筛选。
- 中间：对话窗口，展示用户消息和 AI 回复。
- 右侧：运营上下文面板，可选择产品、账号定位、内容目标和语气。

上下文选择：

- 关联产品，可为空。
- 关联小红书账号定位，可为空。
- 内容目标，例如选题、标题、正文、脚本、发布策略。
- 语气风格，例如自然真诚、专业、口语化、高级感。
- 补充要求。

快捷操作：

- 一键生成选题。
- 一键生成标题。
- 一键生成图文草稿。
- 一键优化已有文案。
- 将 AI 回复保存为内容草稿。

### 4.3 管理端查看

管理端菜单名称：`灵感对话记录`。

禾一斯老板和管理层可以查看员工完整对话内容。

能力：

- 按员工筛选。
- 按时间筛选。
- 按产品筛选。
- 按关键词搜索。
- 查看完整问答。
- 查看该会话消耗算力。
- 查看是否转成内容草稿。

管理端只读，不直接修改员工对话。

### 4.4 数据模型

`inspiration_session`：灵感对话会话。

字段建议：

- `id`：主键。
- `tenant_id`：租户 ID。
- `user_id`：创建人。
- `title`：会话标题。
- `linked_product_id`：关联产品 ID，允许为 0。
- `linked_xhs_account_id`：关联小红书账号 ID，允许为 0。
- `goal_type`：对话目标，如 topic、title、body、script、strategy。
- `status`：状态，active 或 archived。
- `message_count`：消息数量。
- `total_credit_cost`：累计消耗算力。
- `create_time`：创建时间。
- `update_time`：更新时间。

`inspiration_message`：灵感对话消息。

字段建议：

- `id`：主键。
- `tenant_id`：租户 ID。
- `session_id`：会话 ID。
- `user_id`：用户 ID。
- `role`：消息角色，user 或 assistant。
- `content`：消息内容。
- `context_json`：产品、账号、目标等上下文快照。
- `ai_provider`：AI 服务商。
- `ai_model`：模型名称。
- `credit_cost`：本条消息消耗算力。
- `latency_ms`：响应耗时。
- `status`：success 或 failed。
- `error_message`：失败原因。
- `create_time`：创建时间。

### 4.5 API 设计

用户端 API：

- `POST /api/inspiration/sessions`：新建会话。
- `GET /api/inspiration/sessions`：获取自己的会话列表。
- `GET /api/inspiration/sessions/{session_id}`：获取会话详情和消息。
- `POST /api/inspiration/sessions/{session_id}/messages`：发送消息并获取 AI 回复。
- `POST /api/inspiration/messages/{message_id}/save-draft`：将回复保存为内容草稿。
- `POST /api/inspiration/sessions/{session_id}/archive`：归档会话。

管理端 API：

- `GET /api/admin/inspiration/sessions`：查看本租户所有员工会话。
- `GET /api/admin/inspiration/sessions/{session_id}`：查看完整会话内容。

## 5. 爆款解析

### 5.1 用户价值

爆款解析用于拆解参考视频的运营结构，帮助禾一斯员工学习爆款的表达方式，但不能鼓励搬运或侵权。

输出重点：

- 前三秒钩子。
- 视频结构。
- 镜头节奏。
- 字幕和口播脚本。
- 卖点表达方式。
- 评论区可复用选题。
- 可转化为自有素材的二创方向。
- 小红书图文或视频脚本建议。

### 5.2 第一版能力边界

第一版先完成任务型流程。

在豆包视频理解未接入前，支持两种输入：

- 上传视频文件，保存文件信息并创建解析任务。
- 用户手动补充视频文案、口播稿、观察笔记，由 DeepSeek 先做文本拆解。

接入豆包后：

- 豆包负责读取视频画面、音频、字幕或关键帧。
- DeepSeek 负责将豆包结果整理成小红书运营分析和可复用脚本。

### 5.3 用户端页面

用户端菜单名称：`爆款解析`。

页面结构：

- 上传区：上传视频、图片或填写链接。
- 解析目标：选择拆解钩子、脚本、镜头节奏、卖点表达、生成复用方案。
- 补充说明：用户填写观察笔记或目标产品。
- 任务列表：展示待解析、解析中、已完成、失败。
- 结果详情：结构化展示解析结论和可复用内容。

结果页快捷操作：

- 转入灵感对话继续讨论。
- 转入智能创作生成图文。
- 转入智能剪辑生成工单。
- 保存为爆款案例。

### 5.4 管理端查看

管理端菜单名称：`爆款解析记录`。

能力：

- 查看员工提交的爆款解析任务。
- 查看上传文件、参考链接和补充说明。
- 查看完整解析结果。
- 查看任务状态和消耗算力。
- 按员工、时间、状态、关键词筛选。

管理端只读，不直接修改解析结果。

### 5.5 数据模型

`viral_analysis_job`：爆款解析任务。

字段建议：

- `id`：主键。
- `tenant_id`：租户 ID。
- `user_id`：创建人。
- `title`：任务标题。
- `source_type`：来源类型，upload、link 或 text。
- `source_url`：参考链接，允许为空。
- `material_file_id`：素材文件 ID，允许为 0。
- `analysis_goal`：解析目标。
- `supplement_text`：补充说明、口播稿或观察笔记。
- `status`：pending、processing、completed、failed、cancelled。
- `ai_provider`：AI 服务商。
- `ai_model`：模型名称。
- `credit_cost`：消耗算力。
- `error_message`：失败原因。
- `create_time`：创建时间。
- `update_time`：更新时间。

`viral_analysis_result`：爆款解析结果。

字段建议：

- `id`：主键。
- `tenant_id`：租户 ID。
- `job_id`：任务 ID。
- `hook_summary`：前三秒钩子总结。
- `structure_summary`：视频结构总结。
- `shot_rhythm`：镜头节奏。
- `script_breakdown`：脚本拆解。
- `selling_points`：卖点表达。
- `reuse_suggestions`：可复用建议。
- `rewritten_script`：改写后的自有脚本。
- `tags`：推荐标签 JSON。
- `raw_result_json`：AI 原始结构化结果。
- `create_time`：创建时间。

`viral_analysis_material`：爆款解析素材。

字段建议：

- `id`：主键。
- `tenant_id`：租户 ID。
- `job_id`：任务 ID。
- `file_name`：文件名。
- `file_type`：文件类型，image、video、document 或 other。
- `mime_type`：MIME 类型。
- `file_size`：文件大小。
- `storage_path`：对象存储路径或本地开发路径。
- `create_time`：创建时间。

### 5.6 API 设计

用户端 API：

- `POST /api/viral-analysis/jobs`：创建解析任务。
- `POST /api/viral-analysis/jobs/{job_id}/materials`：上传解析素材。
- `GET /api/viral-analysis/jobs`：获取自己的解析任务列表。
- `GET /api/viral-analysis/jobs/{job_id}`：获取任务详情和结果。
- `POST /api/viral-analysis/jobs/{job_id}/run`：开始解析。
- `POST /api/viral-analysis/jobs/{job_id}/cancel`：取消任务。
- `POST /api/viral-analysis/jobs/{job_id}/save-draft`：将结果保存为内容草稿。

管理端 API：

- `GET /api/admin/viral-analysis/jobs`：查看本租户所有解析任务。
- `GET /api/admin/viral-analysis/jobs/{job_id}`：查看完整任务和解析结果。

开发者端 API：

- `GET /api/developer/viral-analysis/jobs`：排查全部租户解析任务。
- `GET /api/developer/viral-analysis/jobs/{job_id}`：查看技术细节、Provider 调用和失败原因。

## 6. 算力扣费

第一版建议先做记录，再做强扣费；当团队共享钱包完成后切换为正式扣费。

推荐规则：

- 灵感对话：按 assistant 回复扣费。
- 爆款解析：按解析任务扣费。
- 保存草稿不重复扣费。
- AI 调用失败不扣费。
- Provider 已成功返回但用户不采用，仍可计费。

本轮如果团队共享钱包尚未完成，可以先写入 AI 使用记录并保存预估消耗；正式扣费启用后，所有扣费和退费必须写入算力流水，关联业务类型：

- `inspiration_chat`
- `viral_analysis`

## 7. 安全和权限

必须满足：

- 用户只能访问本租户数据。
- 员工只能管理自己创建的会话和解析任务。
- 老板和管理层可以查看本租户所有员工完整内容。
- 开发者端可以按内部权限查看全部租户，但必须记录审计日志。
- 文件访问必须鉴权，不能直接暴露未签名的对象存储地址。
- AI Key 不返回前端。

## 8. 前端实现范围

用户端：

- 新增 `灵感对话` 菜单和页面。
- 新增 `爆款解析` 菜单和页面。
- 两个模块都要显示算力消耗提示。
- 两个模块都要支持结果转内容草稿的入口。

管理端：

- 新增 `灵感对话记录`。
- 新增 `爆款解析记录`。
- 支持筛选、详情查看和完整内容查看。

开发者端：

- 第一轮可只做 AI 调用日志和失败排查入口。
- 爆款解析 Provider 失败时，开发者端要能看到任务错误。

## 9. 测试策略

后端测试：

- 灵感对话新建会话、发送消息、读取会话、归档会话。
- 管理端查看本租户员工完整会话。
- 爆款解析创建任务、上传素材、运行解析、读取结果。
- 不同租户之间数据隔离。
- AI Provider 失败时状态和错误返回正确。
- 算力不足或扣费失败时任务不能继续进入付费执行阶段。

前端测试：

- 用户端菜单能进入灵感对话和爆款解析。
- 灵感对话能发送消息并展示回复。
- 爆款解析能创建任务并展示状态。
- 管理端能查看记录列表和详情。

## 10. 当前不做

本子规格不包含：

- 豆包视频理解的真实接口接入。
- 长视频完整转写。
- 视频下载和搬运。
- 真实支付接口。
- 完整团队共享钱包改造。
- 小红书自动发布 Worker 改造。

以上能力会在对应模块的后续计划中单独处理。
