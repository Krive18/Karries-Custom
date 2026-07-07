# 矩阵发布计划确认与执行队列设计

## 背景

当前后端已经具备这些主线能力：

1. 用户可以通过产品库生成 AI 图文草稿。
2. 用户可以人工确认草稿。
3. 用户可以把已确认草稿转换为 `matrix_publish_plan` 和 `matrix_publish_item`。

当前缺口是：`matrix_publish_item` 生成后仍停留在待确认状态，还没有进入“自动发布执行队列”。真实的小红书浏览器自动化后续会依赖一个稳定的任务协议：能领取任务、提交成功、提交失败、进入人工接管。

本阶段目标是先把后端执行链路打通，不实现真实浏览器自动化，不直接调用小红书网页。

## 目标

1. 用户可以确认一个矩阵发布计划，使其中待确认 item 进入待自动提交状态。
2. 用户可以查看单个计划详情和计划下的 item 列表。
3. 用户可以取消尚未开始执行的计划。
4. 自动化 worker 可以通过内部 API 领取到期的待提交 item。
5. 自动化 worker 可以回写 item 执行结果：提交成功、提交失败、需要人工接管。
6. 后端根据 item 状态聚合更新 plan 状态。
7. 所有接口都保持用户数据隔离，worker 接口通过内部 token 鉴权。

## 非目标

1. 不实现真实小红书浏览器自动化。
2. 不上传图片、视频或封面到小红书。
3. 不实现验证码、扫码登录、风控处理。
4. 不做积分扣费。
5. 不新增复杂日志和截图表。
6. 不改造旧的 `publish_task` / `account` 发布链路；新 SaaS 主线使用 `matrix_publish_plan` / `matrix_publish_item`。

## 状态设计

### matrix_publish_plan.status

- `1`：草稿。
- `2`：待确认。
- `3`：待自动提交。
- `4`：自动提交中。
- `5`：已完成。
- `6`：存在失败。
- `7`：已取消。

### matrix_publish_item.status

- `1`：待确认。
- `2`：待自动提交。
- `3`：自动提交中。
- `4`：已提交到小红书定时发布。
- `5`：提交失败。
- `6`：需要人工接管。
- `7`：已取消。

本阶段只使用已有 tinyint 字段，不新增状态列。后续如做更完整审计日志，再单独增加日志表和截图字段。

## 用户侧 API

### 1. 获取计划详情

`GET /api/matrix-plans/{plan_id}`

返回当前用户自己的计划详情：

```json
{
  "id": 12,
  "plan_name": "7月第一周种草发布",
  "status": 2,
  "source_type": "content_draft",
  "content_type": "image_text",
  "schedule_start_time": 1783300000,
  "schedule_end_time": 1783900000,
  "scheduling_rule": {
    "source": "content_draft"
  },
  "item_count": 6
}
```

错误：

- 未登录：`401 UNAUTHORIZED`
- 计划不存在或不属于当前用户：`404 NOT_FOUND`

### 2. 获取计划 item 列表

`GET /api/matrix-plans/{plan_id}/items`

返回计划下的 item，按 `scheduled_time asc, id asc` 排序。每条 item 包含：

- `id`
- `plan_id`
- `xhs_account_id`
- `content_type`
- `title`
- `body`
- `tags`
- `material`
- `scheduled_time`
- `status`
- `last_error`
- `create_time`
- `update_time`

错误：

- 未登录：`401 UNAUTHORIZED`
- 计划不存在或不属于当前用户：`404 NOT_FOUND`

### 3. 确认计划进入待自动提交

`POST /api/matrix-plans/{plan_id}/confirm`

行为：

1. 校验计划属于当前用户。
2. 只允许 `status = 2` 的计划被确认。
3. 校验计划下至少有 1 条 item。
4. 校验所有 item 都是 `status = 1`。
5. 校验每条 item 的 `title` 和 `body` 非空。
6. 将 plan 状态更新为 `3`。
7. 将该 plan 下所有 item 状态从 `1` 更新为 `2`。

成功响应：

```json
{
  "id": 12,
  "status": 3,
  "item_count": 6
}
```

错误：

- 计划不存在或不属于当前用户：`404 NOT_FOUND`
- 计划状态不允许确认：`400 VALIDATION_ERROR`
- item 内容不完整：`400 VALIDATION_ERROR`

### 4. 取消计划

`POST /api/matrix-plans/{plan_id}/cancel`

行为：

1. 校验计划属于当前用户。
2. 只允许 `status` 为 `1`、`2`、`3` 的计划取消。
3. 如果存在 `status = 3` 的 item，说明 worker 已领取执行，不能取消。
4. 将 plan 状态更新为 `7`。
5. 将该 plan 下 `status in (1, 2)` 的 item 更新为 `7`。

成功响应：

```json
{
  "id": 12,
  "status": 7,
  "cancelled_item_count": 6
}
```

错误：

- 计划不存在或不属于当前用户：`404 NOT_FOUND`
- 计划或 item 已经进入不可取消状态：`400 VALIDATION_ERROR`

## Worker 内部 API

Worker 接口不使用用户登录 token。第一版使用固定内部 token：

- 配置项：`WORKER_API_TOKEN`
- 请求头：`X-Worker-Token: <token>`

如果未配置 `WORKER_API_TOKEN`，worker 接口返回 `503 SERVICE_UNAVAILABLE`，避免误开放。

### 1. 领取待执行 item

`POST /api/worker/matrix-publish-items/claim`

请求：

```json
{
  "limit": 5,
  "now_time": 1783300000
}
```

字段说明：

- `limit`：本次最多领取数量，默认 5，范围 1-20。
- `now_time`：当前时间戳，测试可传；线上可不传，由服务端取当前时间。

领取条件：

1. item `status = 2`。
2. item `scheduled_time <= now_time`。
3. 所属 plan `status in (3, 4)`。
4. 所属小红书账号 `status = 1`。

领取行为：

1. 使用 MySQL 事务。
2. 按 `scheduled_time asc, id asc` 领取。
3. 使用 `for update skip locked` 避免多个 worker 领取同一条 item。
4. 将领取到的 item 状态改为 `3`。
5. 将对应 plan 状态改为 `4`。
6. 返回 worker 需要执行的内容。

响应：

```json
{
  "items": [
    {
      "id": 101,
      "plan_id": 12,
      "user_id": 5,
      "xhs_account_id": 9,
      "login_state_path": "storage/xhs/9/state.json",
      "content_type": "image_text",
      "title": "通勤也能穿得很舒服",
      "body": "正文内容",
      "tags": ["#通勤穿搭", "#小红书种草"],
      "material": {
        "draft_id": 31,
        "source_content_draft_id": 31
      },
      "scheduled_time": 1783300000
    }
  ]
}
```

错误：

- token 缺失或错误：`401 UNAUTHORIZED`
- worker token 未配置：`503 SERVICE_UNAVAILABLE`

### 2. 回写提交成功

`POST /api/worker/matrix-publish-items/{item_id}/success`

请求：

```json
{
  "message": "submitted to xiaohongshu schedule"
}
```

行为：

1. 只允许 `status = 3` 的 item 回写成功。
2. 将 item 状态改为 `4`。
3. 清空 `last_error` 或写入成功消息。
4. 更新 `update_time`。
5. 聚合刷新 plan 状态：如果该计划下所有 item 都是 `4` 或 `7`，则 plan 状态改为 `5`。

### 3. 回写提交失败

`POST /api/worker/matrix-publish-items/{item_id}/fail`

请求：

```json
{
  "error_message": "upload image failed"
}
```

行为：

1. 只允许 `status = 3` 的 item 回写失败。
2. 将 item 状态改为 `5`。
3. 写入 `last_error`。
4. 将 plan 状态改为 `6`。

### 4. 回写人工接管

`POST /api/worker/matrix-publish-items/{item_id}/manual-takeover`

请求：

```json
{
  "reason": "login expired or risk verification required"
}
```

行为：

1. 只允许 `status = 3` 的 item 进入人工接管。
2. 将 item 状态改为 `6`。
3. 写入 `last_error`。
4. 将 plan 状态改为 `6`。

## 模块边界

### Schema

新增：

- `MatrixPlanDetail`
- `MatrixPlanItemDetail`
- `MatrixPlanActionResult`
- `WorkerClaimRequest`
- `WorkerClaimedItem`
- `WorkerClaimResponse`
- `WorkerItemSuccessRequest`
- `WorkerItemFailRequest`
- `WorkerItemManualTakeoverRequest`

### Repository

扩展 `MatrixPlanRepository`：

- `list_items_for_plan(user_id, plan_id)`
- `confirm_plan(user_id, plan_id)`
- `cancel_plan(user_id, plan_id)`
- `claim_due_items(limit, now_time)`
- `mark_item_success(item_id, message)`
- `mark_item_failed(item_id, error_message)`
- `mark_item_manual_takeover(item_id, reason)`
- `refresh_plan_status(plan_id)`

Repository 负责事务、行锁和 JSON 解析，API 层负责鉴权和响应格式。

### API

扩展：

- `backend/app/api/matrix_plans.py`

新增：

- `backend/app/api/worker_matrix_publish.py`

主应用注册 worker router。

### Config

扩展 `backend/app/core/config.py`：

- `worker_api_token: str`

环境变量：

- `WORKER_API_TOKEN`

## 错误处理

统一使用现有响应结构：

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "message"
  }
}
```

错误码：

- `UNAUTHORIZED`
- `NOT_FOUND`
- `VALIDATION_ERROR`
- `SERVICE_UNAVAILABLE`

## 测试计划

### 单元测试

1. 获取计划详情时，跨用户计划返回 404。
2. 获取 item 列表时，按 `scheduled_time asc, id asc` 排序。
3. 确认计划成功：plan `2 -> 3`，items `1 -> 2`。
4. 确认计划失败：plan 状态不是 `2` 返回 400。
5. 确认计划失败：item 标题或正文为空返回 400。
6. 取消计划成功：plan 进入 `7`，未执行 items 进入 `7`。
7. 取消计划失败：存在 `status = 3` 的 item 返回 400。
8. worker token 缺失或错误返回 401。
9. worker token 未配置返回 503。
10. worker claim 成功：到期 item 被改为 `3`，plan 改为 `4`。
11. worker claim 不领取未到期 item。
12. worker success：item 改为 `4`，全部完成时 plan 改为 `5`。
13. worker fail：item 改为 `5`，plan 改为 `6`。
14. worker manual takeover：item 改为 `6`，plan 改为 `6`。

### MySQL 集成测试

使用 `xhs_publisher_test`：

1. 通过已确认草稿创建 plan 和 items。
2. 调用确认接口。
3. 调用 worker claim 领取 due item。
4. 调用 worker success 回写成功。
5. 查询数据库确认状态流转正确。

## 验收标准

1. 用户侧可以看到计划详情和 item 列表。
2. 用户可以把待确认计划确认到待自动提交队列。
3. 用户可以取消尚未执行的计划。
4. worker 能通过 token 领取到期 item。
5. worker 回写成功、失败、人工接管时状态正确。
6. 所有状态变更保持用户隔离。
7. 后端测试在本地 MySQL 测试库下通过。
