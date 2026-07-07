# 确认草稿进入矩阵发布计划设计

## 背景

当前系统已经具备产品库、AI 内容草稿、人工确认状态和矩阵发布计划基础表。现有缺口是：用户确认 AI 草稿后，还不能把这些草稿批量转成矩阵发布计划中的待发布内容项。

本阶段目标是打通一条后端主线链路：

产品资料生成内容草稿 -> 用户人工确认草稿 -> 从确认草稿创建矩阵发布计划 -> 生成待确认的矩阵发布 item。

本阶段不实现真实小红书浏览器自动发布，不实现视频剪辑，不实现支付扣费。

## 目标

1. 用户可以选择一个或多个已确认的内容草稿创建矩阵发布计划。
2. 后端校验草稿、账号和产品都属于当前登录用户。
3. 只有 `confirmed` 状态的草稿可以进入发布计划。
4. 后端按账号和排期规则生成 `matrix_publish_item`。
5. item 的标题、正文、标签和素材上下文来自对应草稿。
6. 创建后返回计划 ID、item 数量、草稿数量和账号数量。

## 非目标

1. 不自动提交到小红书创作后台。
2. 不启动浏览器自动化。
3. 不支持视频发布和剪辑。
4. 不做积分扣费。
5. 不做前端页面改造。
6. 不修改现有 `/api/content-drafts/product-copy` 生成逻辑。

## 推荐方案

新增接口：

`POST /api/matrix-plans/from-drafts`

该接口专门负责“确认草稿转矩阵发布计划”，避免把草稿逻辑塞进已有 `/api/matrix-plans` 产品排期接口里。

## API 设计

### 请求

```json
{
  "plan_name": "7月第一周种草发布",
  "draft_ids": [1, 2, 3],
  "xhs_account_ids": [10, 11],
  "schedule_start": 1783300000,
  "schedule_end": 1783900000,
  "min_interval_minutes": 360
}
```

字段说明：

- `plan_name`：发布计划名称，必填，1 到 200 字符。
- `draft_ids`：已确认内容草稿 ID 列表，必填，至少 1 个。
- `xhs_account_ids`：目标小红书账号 ID 列表，必填，至少 1 个。
- `schedule_start`：排期开始时间戳，必填。
- `schedule_end`：排期结束时间戳，必填。
- `min_interval_minutes`：同账号内容之间最小间隔，默认 360 分钟。

约束：

- `draft_ids` 不允许重复，重复返回 `400 VALIDATION_ERROR`。
- `xhs_account_ids` 不允许重复，重复返回 `400 VALIDATION_ERROR`。

### 响应

```json
{
  "success": true,
  "data": {
    "id": 12,
    "item_count": 6,
    "draft_count": 3,
    "account_count": 2
  },
  "error": null
}
```

### 错误

- 未登录：`401 UNAUTHORIZED`
- 草稿不存在或不属于当前用户：`404 NOT_FOUND`
- 草稿不是 `confirmed` 状态：`400 VALIDATION_ERROR`
- 小红书账号不存在或不属于当前用户：`404 NOT_FOUND`
- 排期开始时间晚于结束时间：`400 VALIDATION_ERROR`
- 草稿 ID 或账号 ID 重复：`400 VALIDATION_ERROR`

## 数据流

1. 用户在前端选择已确认草稿和目标账号。
2. 前端调用 `POST /api/matrix-plans/from-drafts`。
3. 后端读取当前用户。
4. 后端校验所有草稿都属于当前用户且状态为 `confirmed`。
5. 后端校验所有小红书账号都属于当前用户。
6. 后端创建一条 `matrix_publish_plan`。
7. 后端按 `xhs_account_ids` 外层、`draft_ids` 内层的顺序生成待确认 item。
8. 每个 item 从草稿复制：
   - `title`
   - `body`
   - `tag_json`
   - `material_json`
9. 后端提交事务并返回结果。

`material_json` 必须保留草稿上下文，并额外写入：

- `draft_id`
- `source_content_draft_id`

## 排期规则

本阶段复用现有 `generate_schedule_times` 思路。

生成 item 的数量为：

`draft_count * account_count`

排期方式：

1. 每个账号从 `schedule_start` 开始。
2. 不同账号之间错开 5 分钟。
3. 同一账号的多条内容按 `min_interval_minutes` 间隔。
4. 如果计算出的时间超过 `schedule_end`，则压到 `schedule_end`。

## 状态设计

`content_draft`：

- 只有 `confirmed` 可以进入计划。
- 本阶段不改变草稿状态，避免一个草稿被复用时产生隐藏副作用。

`matrix_publish_plan`：

- 新建状态为 `2`，表示待确认。

`matrix_publish_item`：

- 新建状态为 `1`，表示待确认。

后续阶段再实现“确认发布计划 -> 待提交 -> 自动发布执行”。

## 模块边界

新增 schema：

- `MatrixPlanFromDraftsCreate`

扩展 repository：

- `ContentDraftRepository`
  - 批量读取用户草稿。
  - 校验草稿状态。
- `MatrixPlanRepository`
  - 新增从草稿创建计划和 item 的方法。

扩展 API：

- `backend/app/api/matrix_plans.py`
  - 新增 `POST /api/matrix-plans/from-drafts`

复用：

- `XHSAccountRepository`
- `generate_schedule_times`
- `current_user`
- `get_db_connection`
- `ok/fail` 响应格式

## 事务要求

创建计划和创建 item 必须在同一事务中完成。

如果任意 item 写入失败：

1. 回滚 `matrix_publish_plan`
2. 回滚所有已插入的 `matrix_publish_item`
3. 不改变 `content_draft`

## 测试计划

新增或扩展测试文件：

- `backend/tests/test_matrix_plan_from_drafts_api.py`

测试用例：

1. confirmed 草稿可以创建矩阵发布计划和 item。
2. draft/rejected 草稿不能进入发布计划。
3. 跨用户草稿返回 404。
4. 跨用户账号返回 404。
5. 无登录访问返回 401。
6. 排期时间范围错误返回 400。
7. repository 写 item 失败时事务回滚。
8. item 标题、正文、标签、素材上下文来自草稿。
9. 重复草稿 ID 或账号 ID 返回 400。

## 验收标准

1. `POST /api/matrix-plans/from-drafts` 可用。
2. 已确认草稿可以批量生成矩阵计划 item。
3. 用户隔离测试通过。
4. 事务回滚测试通过。
5. 后端完整测试通过。
6. 运行中的本地后端迁移后接口可访问。
