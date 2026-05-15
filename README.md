# 微信公众号 AI 对话机器人 🤖

基于 Mimo API 的微信公众号自动回复机器人，支持多轮对话、图片识别和指令系统。

## 功能

- ✅ **文字对话** — Mimo-v2.5 多轮记忆，每次回复带历史上下文
- ✅ **图片识别** — 支持用户发送图片，Mimo 尝试描述
- ✅ **指令系统** — `/help` 查看帮助，`/clear` 清除对话记忆
- ✅ **消息去重** — 防微信超时重试导致重复处理
- ✅ **完善日志** — 所有请求、Mimo 调用、超时异常均记录
- ✅ **零成本部署** — Railway 免费额度

## 环境变量

| 变量名 | 必须 | 默认值 | 说明 |
|--------|------|--------|------|
| `WECHAT_TOKEN` | ✅ | — | 微信验证 Token，与公众号后台一致 |
| `WECHAT_ORIGINAL_ID` | ✅ | — | 公众号原始ID（gh_xxxxx），回复XML里用作 FromUserName |
| `MIMO_API_URL` | | `https://token-plan-sgp.xiaomimimo.com/v1/chat/completions` | Mimo API 地址 |
| `MIMO_API_KEY` | ✅ | — | Mimo API 密钥 |
| `BOT_NAME` | | `小爪AI` | 机器人名称，出现在回复风格里 |
| `MIMO_TIMEOUT` | | `4` | Mimo API 超时秒数（建议 4-5 秒，微信限制 5 秒内响应） |
| `MAX_HISTORY` | | `10` | 每用户保留消息条数（约 5 轮对话），重启会丢失 |

## 部署到 Railway

### 1. Fork 或上传到 GitHub

### 2. 在 Railway 中创建项目
1. 打开 [railway.app](https://railway.app)，用 GitHub 登录
2. 点 **New Project** → **Deploy from GitHub repo**
3. 选择仓库，Railway 自动检测 `requirements.txt` 并安装

### 3. 配置环境变量
在 Railway 项目的 **Variables** 中添加上面表格中必须的环境变量。

> ⚠️ **重要**：`WECHAT_ORIGINAL_ID` 必须填公众号的原始ID，不是 AppID。在微信公众号后台 → 设置与开发 → 公众号设置 → 账号详情 可查到，格式为 `gh_xxxxx`。

### 4. 获取公网地址
Railway 部署完成后，在 **Settings** → **Networking** 中点击 **Generate Domain**，格式类似：`https://xxx.railway.app`

### 5. 配置微信公众号后台
1. 打开 [微信公众平台](https://mp.weixin.qq.com/)
2. **设置与开发** → **基本配置**
3. 填写：
   - URL：`https://xxx.railway.app/wx`
   - Token：填你在环境变量里设置的 `WECHAT_TOKEN`
   - 消息加解密方式：选择 **明文模式**
4. 点提交，成功后就能用了！

## 本地测试

```bash
pip install -r requirements.txt
python app.py
```

访问 `http://localhost:5000` 查看运行状态。

## 使用说明

### 指令
- `/help` — 查看所有支持的指令
- `/clear` — 清除当前对话记忆，重新开始

### 对话
直接发送文字消息，AI 会根据上下文进行多轮对话。

### 图片
发送图片给公众号，Mimo 会尝试描述图片内容。

## 查看日志

Railway 项目 → Deployments → 选最新部署 → **View Logs** 可看到：
- `POST /wx` 请求记录
- Mimo 超时/异常警告
- 消息处理全流程

## 技术细节

- **框架**：Flask + gunicorn（Railway 推荐）
- **多轮记忆**：内存 `defaultdict(deque)`，重启丢失；生产环境可换 Redis
- **消息去重**：内存 `set`，通过 MsgId 过滤微信重试消息
- **超时策略**：MIMO_TIMEOUT 建议 ≤ 5 秒（微信被动回复超时限制）