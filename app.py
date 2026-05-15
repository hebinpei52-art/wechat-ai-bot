#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号 AI 对话机器人 - 基于 Mimo API
功能：接收用户消息 → 调用 Mimo → 回复给用户
"""

import os
import time
import hashlib
import requests
from flask import Flask, request, make_response
from xml.etree import ElementTree as ET

# ========== 配置区（必须设置的环境变量）==========
# Railway 环境变量
WECHAT_TOKEN = os.environ.get("WECHAT_TOKEN", "")       # ★ 微信 Token，必须跟公众号后台一致
WECHAT_APPID = os.environ.get("WECHAT_APPID", "")       # AppID（只在需要时用）
WECHAT_ORIGINAL_ID = os.environ.get("WECHAT_ORIGINAL_ID", "")  # ★ 原始ID（gh_xxxxx），回复时用作 FromUserName

MIMO_API_URL = os.environ.get("MIMO_API_URL", "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions")
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")
MIMO_TIMEOUT = int(os.environ.get("MIMO_TIMEOUT", "8"))  # Mimo API 超时秒数（微信限制5s，留点余量）

BOT_NAME = os.environ.get("BOT_NAME", "小爪AI")
# ============================

app = Flask(__name__)


# ---------- 签名验证 ----------

def generate_sign(timestamp, nonce):
    """生成微信签名"""
    l = [WECHAT_TOKEN, timestamp, nonce]
    l.sort()
    return hashlib.sha1("".join(l).encode()).hexdigest()


def verify_wechat():
    """验证微信服务器"""
    signature = request.args.get("signature", "")
    timestamp = request.args.get("timestamp", "")
    nonce = request.args.get("nonce", "")

    if not signature or not timestamp or not nonce:
        return False

    s = sorted([WECHAT_TOKEN, timestamp, nonce])
    real_sig = hashlib.sha1("".join(s).encode()).hexdigest()
    return real_sig == signature


# ---------- 回复构建 ----------

def safe_xml_escape(text):
    """安全的 XML 内容转义（防止花括号/特殊字符破坏格式）"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def reply_text(to_user, content):
    """生成微信文本回复 XML（使用原始ID作为FromUserName）"""
    from_user = WECHAT_ORIGINAL_ID or WECHAT_APPID
    safe_content = safe_xml_escape(content)
    return f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{safe_content}]]></Content>
</xml>"""


# ---------- Mimo API ----------

def call_mimo(user_message):
    """调用 Mimo API 生成回复"""
    headers = {
        "Authorization": f"Bearer {MIMO_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mimo-v2.5",
        "messages": [
            {
                "role": "system",
                "content": f"你是一个友好的AI助手，名字叫{BOT_NAME}。你正在一个微信公众号里和用户对话。"
                           f"请用简洁、有趣、口语化的方式回复用户。每次回复不要太长，最好在200字以内。"
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        "max_tokens": 500,
        "temperature": 0.8
    }

    try:
        resp = requests.post(MIMO_API_URL, headers=headers, json=payload, timeout=MIMO_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        return str(data) if data else "小爪没想好怎么回，换个问题试试？😄"
    except requests.Timeout:
        return f"{BOT_NAME}思考太投入了，请再问一次吧~ 😅"
    except Exception as e:
        return f"抱歉，小爪暂时走神了，请稍后再试~ 😅"


# ---------- 路由 ----------

@app.route("/")
def index():
    return f"🤖 {BOT_NAME} 运行正常！"


@app.route("/wx", methods=["GET"])
def wechat_verify():
    """微信服务器验证 - 开发者配置时需要"""
    signature = request.args.get("signature")
    timestamp = request.args.get("timestamp")
    nonce = request.args.get("nonce")
    echostr = request.args.get("echostr")

    if not all([signature, timestamp, nonce]):
        return "error", 400

    l = sorted([WECHAT_TOKEN, timestamp, nonce])
    real_sig = hashlib.sha1("".join(l).encode()).hexdigest()

    if real_sig == signature and echostr:
        return make_response(echostr)
    elif real_sig == signature:
        return "verify ok"
    return "error", 400


@app.route("/wx", methods=["POST"])
def wechat_message():
    """接收微信消息并回复"""
    if not verify_wechat():
        return "error", 403

    # 初始 fallback 变量
    from_user = "unknown"
    reply = "收到消息了，但处理时遇到了一点小问题 😅"

    try:
        xml_data = request.data
        root = ET.fromstring(xml_data)
        msg_type = root.find("MsgType").text
        from_user = root.find("FromUserName").text
        content_elem = root.find("Content")
        content = content_elem.text if content_elem is not None else ""

        if msg_type == "text":
            user_text = content.strip()
            if not user_text:
                reply = "小爪没听清楚你说啥，再发一次？ 😄"
            else:
                reply = call_mimo(user_text)
        else:
            reply = f"小爪还在学习中，暂不支持{msg_type}类型的消息哦~ 😅"

    except Exception as e:
        # 如果连 from_user 都没解析出来，已经由外层的默认值兜底了
        app.logger.error(f"消息处理异常: {e}")

    # 统一构建响应
    response = make_response(reply_text(from_user, reply))
    response.content_type = "text/xml; charset=utf-8"
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🤖 {BOT_NAME} 启动中，端口：{port}")
    app.run(host="0.0.0.0", port=port)
