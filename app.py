#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号 AI 对话机器人 - 基于 Mimo API
"""

import os
import time
import hashlib
import logging
import requests
from collections import defaultdict, deque
from flask import Flask, request, make_response
from xml.etree import ElementTree as ET

# ========== 日志配置 ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ========== 环境变量 ==========
WECHAT_TOKEN = os.environ.get("WECHAT_TOKEN", "")
WECHAT_ORIGINAL_ID = os.environ.get("WECHAT_ORIGINAL_ID", "")

MIMO_API_URL = os.environ.get("MIMO_API_URL", "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions")
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")
MIMO_TIMEOUT = int(os.environ.get("MIMO_TIMEOUT", "4"))  # ← 4秒，给微信留1秒余量

BOT_NAME = os.environ.get("BOT_NAME", "小爪AI")
MAX_HISTORY = int(os.environ.get("MAX_HISTORY", "10"))   # 每用户保留最近10条（≈5轮对话）

app = Flask(__name__)

# ========== 多轮对话记忆（内存版，重启丢失） ==========
# key: from_user(openid), value: deque of {"role": ..., "content": ...}
user_histories: dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))

# ========== 消息去重（防微信重试） ==========
# 简单 set，重启清空；生产环境可换 Redis + TTL
processed_msg_ids: set[str] = set()


# ---------- 签名验证 ----------

def verify_wechat() -> bool:
    signature = request.args.get("signature", "")
    timestamp = request.args.get("timestamp", "")
    nonce = request.args.get("nonce", "")
    if not all([signature, timestamp, nonce]):
        return False
    real_sig = hashlib.sha1("".join(sorted([WECHAT_TOKEN, timestamp, nonce])).encode()).hexdigest()
    return real_sig == signature


# ---------- 回复构建 ----------

def safe_cdata(text: str) -> str:
    """CDATA 不需要转义，但防止 ]]> 破坏 XML 结构"""
    return text.replace("]]>", "]]]]><![CDATA[>")


def reply_text(to_user: str, content: str) -> str:
    return f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{WECHAT_ORIGINAL_ID}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{safe_cdata(content)}]]></Content>
</xml>"""


# ---------- Mimo API ----------

SYSTEM_PROMPT = (
    f"你是一个友好的AI助手，名字叫{BOT_NAME}。"
    "你在微信公众号里和用户对话，请用简洁口语化的方式回复，每次不超过200字。"
)


def call_mimo(from_user: str, user_message: str) -> str:
    """调用 Mimo，携带该用户的历史对话（多轮记忆）"""
    history = list(user_histories[from_user])

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    headers = {
        "Authorization": f"Bearer {MIMO_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mimo-v2.5",
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.8
    }

    try:
        resp = requests.post(MIMO_API_URL, headers=headers, json=payload, timeout=MIMO_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        reply = data["choices"][0]["message"]["content"]

        # 保存本轮到记忆
        user_histories[from_user].append({"role": "user", "content": user_message})
        user_histories[from_user].append({"role": "assistant", "content": reply})

        return reply

    except requests.Timeout:
        logger.warning(f"Mimo 超时 | user={from_user} | msg={user_message[:40]}")
        return f"🕐 {BOT_NAME}没来得及想好，请再发一次～"
    except Exception as e:
        logger.error(f"Mimo 调用失败: {e} | user={from_user}")
        return "抱歉，小爪暂时走神了，请稍后再试～ 😅"


def call_mimo_with_image(from_user: str, text: str, image_url: str) -> str:
    """图片消息（vision 场景不带历史上下文）"""
    headers = {
        "Authorization": f"Bearer {MIMO_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mimo-v2.5",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": text or "请描述这张图片"},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]}
        ],
        "max_tokens": 500,
        "temperature": 0.8
    }

    try:
        resp = requests.post(MIMO_API_URL, headers=headers, json=payload, timeout=MIMO_TIMEOUT)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except requests.Timeout:
        logger.warning(f"Mimo 图片超时 | user={from_user}")
        return f"🕐 {BOT_NAME}看图太认真了，请再发一次～"
    except Exception as e:
        logger.error(f"Mimo 图片调用失败: {e} | user={from_user}")
        return "小爪看到你的图片了，但暂时识别不了，请稍后再试～ 😅"


# ---------- 指令处理 ----------

def handle_command(cmd: str, from_user: str) -> str | None:
    """返回 None 表示不是指令"""
    if cmd == "/clear":
        user_histories[from_user].clear()
        return "✅ 对话记忆已清除，咱们重新开始！"
    if cmd == "/help":
        return "📋 支持的指令：\n/clear - 清除对话记忆\n/help - 查看帮助"
    return None


# ---------- 路由 ----------

@app.route("/")
def index():
    return f"🤖 {BOT_NAME} 运行正常！"


@app.route("/wx", methods=["GET"])
def wechat_verify():
    signature = request.args.get("signature")
    timestamp = request.args.get("timestamp")
    nonce = request.args.get("nonce")
    echostr = request.args.get("echostr")

    if not all([signature, timestamp, nonce]):
        return "error", 400

    real_sig = hashlib.sha1("".join(sorted([WECHAT_TOKEN, timestamp, nonce])).encode()).hexdigest()
    if real_sig == signature:
        return make_response(echostr or "verify ok")
    return "error", 400


@app.route("/wx", methods=["POST"])
def wechat_message():
    if not verify_wechat():
        return "error", 403

    from_user = "unknown"
    reply = "收到消息了，但处理时遇到了一点小问题 😅"

    try:
        root = ET.fromstring(request.data)
        msg_type = root.find("MsgType").text
        from_user = root.find("FromUserName").text
        msg_id = root.findtext("MsgId", "")

        # ---- 去重：微信超时会重试，同一 MsgId 只处理一次 ----
        if msg_id and msg_id in processed_msg_ids:
            logger.info(f"重复消息，跳过 | MsgId={msg_id}")
            return "success"  # 返回 success 让微信停止重试
        if msg_id:
            processed_msg_ids.add(msg_id)
            # 防止 set 无限增长，超过 10000 条清一半
            if len(processed_msg_ids) > 10000:
                for _ in range(5000):
                    processed_msg_ids.pop()

        # ---- 消息分发 ----
        if msg_type == "text":
            content = (root.findtext("Content") or "").strip()
            if not content:
                reply = "小爪没听清楚，再说一次？😄"
            else:
                # 指令优先
                cmd_reply = handle_command(content, from_user)
                reply = cmd_reply if cmd_reply is not None else call_mimo(from_user, content)

        elif msg_type == "image":
            pic_url = root.findtext("PicUrl", "")
            reply = call_mimo_with_image(from_user, "请描述这张图片", pic_url) if pic_url \
                else "小爪收到图片了，但没找到图片地址 😅"

        else:
            reply = f"小爪还在学习中，暂不支持「{msg_type}」类消息～ 😅"

    except Exception as e:
        logger.error(f"消息处理异常: {e}")

    response = make_response(reply_text(from_user, reply))
    response.content_type = "text/xml; charset=utf-8"
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🤖 {BOT_NAME} 启动，端口：{port}")
    app.run(host="0.0.0.0", port=port)