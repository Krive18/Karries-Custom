# KARRIES 飞书群机器人配置

飞书任务通知默认关闭。后端只有在以下四个环境变量齐全时才会发送：

pytest 和 `XHS_ENV=test`/`APP_ENV=test` 环境会强制禁止向飞书发送消息，即使误配置了 `FEISHU_BOT_ENABLED=1`。真实机器人联调必须在 pytest 之外手动执行，并且一次只发送一条明确的测试消息。

```text
FEISHU_BOT_ENABLED=1
FEISHU_BOT_WEBHOOK_URL=<new webhook URL>
FEISHU_BOT_SIGNING_SECRET=<signing secret>
FEISHU_BOT_MENTION_OPEN_ID=<target colleague OpenID>
```

可选的同事显示名、超时与重试配置：

```text
FEISHU_BOT_MENTION_NAME=任务负责人
FEISHU_BOT_TIMEOUT_SECONDS=5
FEISHU_BOT_MAX_ATTEMPTS=3
```

## 本地验证

在启动后端的同一个 PowerShell 窗口中设置变量，然后重启后端：

```powershell
$env:FEISHU_BOT_ENABLED = "1"
$env:FEISHU_BOT_WEBHOOK_URL = "<new webhook URL>"
$env:FEISHU_BOT_SIGNING_SECRET = "<signing secret>"
$env:FEISHU_BOT_MENTION_OPEN_ID = "<target colleague OpenID>"
$env:FEISHU_BOT_MENTION_NAME = "任务负责人"
```

创建一个新的视频创作任务或 AI 智能翻译任务。群消息会在第一行 `@`
指定同事，并明确显示任务类型、任务编号、标题、模式/语言、素材数量和提交时间。
只有真正创建的任务会推送，幂等重试不会重复通知。

## 生产环境

将同样的变量添加到 `/etc/karries-api.env`，保持文件权限为 `600`，然后重启 `karries-api`。不要把 Webhook 或签名密钥写入代码、提交到 Git，也不要放在前端或日志中。

## 安全与故障边界

- 仅允许 `https://open.feishu.cn/open-apis/bot/v2/hook/` 官方 Webhook。
- 每次请求都按飞书签名校验规则生成时间戳和 HMAC-SHA256 签名。
- `FEISHU_BOT_MENTION_OPEN_ID` 必须是 `ou_` 开头的有效 OpenID；缺失或格式异常时通知保持关闭，避免消息未真正 `@` 到负责人却被误认为发送成功。
- 群消息仅包含任务类型、任务编号、标题、模式/语言、素材数量和时间，不包含完整脚本、素材文件名、用户账号或内部路径。
- 飞书临时不可用时会有限重试，不会回滚或中断用户任务创建。

官方参考：https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot

## 一次性获取同事 OpenID（企业自建应用）

这个工具使用企业自建应用的长连接事件，与上面的自定义 Webhook
机器人完全隔离。它只处理启动以后新收到的群聊 `@机器人` 消息，输出首个
有效发送者 OpenID 后立即断开；不会回复群聊、不会读取历史任务，也不会调用
消息发送接口。

在 PowerShell 中临时设置企业应用凭证并启动：

```powershell
cd "D:\A点绘环球\小红书自动化\backend"
$env:FEISHU_APP_ID = "<企业自建应用 App ID>"
$env:FEISHU_APP_SECRET = "<企业自建应用 App Secret>"
.\.venv\Scripts\python.exe -m app.cli.capture_feishu_open_id
```

看到等待提示后，让需要被提醒的同事在已添加该机器人的群里发送：

```text
@KARRIES 通讯录助手 获取我的ID
```

终端输出格式如下，并会自动结束：

```text
FEISHU_OPEN_ID=ou_xxx
```

App Secret 只应存在于当前 PowerShell 会话或受保护的服务器环境变量中，
不要写入源码、文档、前端、Git 或聊天记录。OpenID 与企业应用绑定，后续
发送带 `@` 的任务通知时必须继续使用同一个企业自建应用。

官方 SDK 参考：https://github.com/larksuite/channel-sdk-python
