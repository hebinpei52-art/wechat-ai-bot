# 微信公众号 AI 对话机器人 🤖

基于 Mimo API 的微信公众号自动回复机器人，接入 Mimo 大模型，支持对话和任务下发。

## 功能

- ✅ 接收用户消息，自动调用 Mimo AI 回复
- ✅ 支持中英文对话
- ✅ 可下发任务给 AI 执行
- ✅ 零成本部署（Railway 免费额度）

## 部署到 Railway

### 1. Fork 或上传到 GitHub
将本仓库 Fork 到你的 GitHub 账号下。

### 2. 在 Railway 中创建项目
1. 打开 [railway.app](https://railway.app)，用 GitHub 登录
2. 点 **New Project** → **Deploy from GitHub repo**
3. 选择 `wechat-ai-bot` 仓库
4. Railway 会自动检测到 `requirements.txt` 并安装依赖

### 3. 配置环境变量
在 Railway 项目的 **Variables** 中添加：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `WECHAT_TOKEN` | `你的随机字符串` | 微信验证 token，自己定义 |
| `MIMO_API_URL` | `https://token-plan-sgp.xiaomimimo.com/v1/chat/completions` | Mimo API 地址 |
| `MIMO_API_KEY` | `你的Mimo API Key` | Mimo API 密钥 |
| `BOT_NAME` | `小爪AI` | 机器人名称 |

### 4. 获取公网地址
Railway 部署完成后，在 **Settings** → **Networking** 中点击 **Generate Domain**，生成公网地址。

格式类似：`https://xxx.railway.app`

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

## 效果展示

用户关注订阅号后，发送消息即可获得 AI 自动回复。