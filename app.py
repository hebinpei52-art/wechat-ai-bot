#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号 AI 对话机器人 - 基于 Mimo API
功能：接收用户消息 → 调用 Mimo → 回复给用户
"""

import os
import time
import hashlib
import json
import random
import string
import requests
from flask import Flask, request, abort, make_response
from xml.etree import ElementTree as ET

# ========== 配置区 ==========
# 请在 Railway 环境变量中设置以下值
WECHAT_TOKEN = os.environ.get("WECHAT_TOKEN", "your_token_here")       # 设置一个安全的随机字符串
WECHAT_APPID = os.environ.get("WECHAT_APPID", "wx9eaace66f868c3b2")    # 你的 AppID
WECHAT_AES_KEY = os.environ.get("WECHAT_AES_KEY", "")                  # 如果开启加解密就填

MIMO_API_URL = os.environ.get("MIMO_API_URL", "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions")
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "your_mimo_key_here")

BOT_NAME = os.environ.get("BOT_NAME", "小爪AI")
# ============================

app = Flask(__name__)

def generate_sign(timestamp, nonce):
    """生成微信签名"""
    l = [WECHAT_TOKEN, timestamp, nonce]
    l.sort()
    return hashlib.sha1("".join(l).encode()).hexdigest()

def verify_wechat():
    """验证微信服务器"""
    token = WECHAT_TOKEN
    signature = request.args.get("signature", "")
    timestamp = request.args.get("timestamp", "")
    nonce = request.args.get("nonce", "")

    if not signature or not timestamp or not nonce:
        return False

    s = sorted([token, timestamp, nonce])
    real_sig = hashlib.sha1("".join(s).encode()).hexdigest()
    return real_sig == signature

def reply_text(to_user, content):
    """生成微信文本回复 XML"""
    tpl = """<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{timestamp}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""
    return tpl.format(
        to_user=to_user,
        from_user=WECHAT_APPID,
        timestamp=int(time.time()),
        content=content
    )

def call_mimo(user_message):
    """调用 Mimo API 生成回复"""
    headers = {
        "Authorization": f"Bearer {MIMO_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "MiniMax-Text-01",
        "messages": [
            {
                "role": "system",
                "content": f"""你是一个友好的AI助手，名字叫{BOT_NAME}。你正在一个微信公众号里和用户对话。
请用简洁、有趣、口语化的方式回复用户。如果用户的问题是关于AI、副业、闲鱼、提示词等话题，可以多说几句。
每次回复不要太长，最好在200字以内。"""
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
        resp = requests.post(MIMO_API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        # 兼容不同格式的响应
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        return str(data)
    except Exception as e:
        return f"抱歉，小爪暂时走神了，请稍后再试~ 😅\n错误：{str(e)}"

@app.route("/")
def index():
    return "🤖 {name} 运行正常！".format(name=BOT_NAME)

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

    # 解析 XML
    xml_data = request.data
    try:
        root = ET.fromstring(xml_data)
        msg_type = root.find("MsgType").text
        from_user = root.find("FromUserName").text
        content_elem = root.find("Content")
        content = content_elem.text if content_elem is not None else ""

        # 只处理文本消息
        if msg_type == "text":
            user_text = content.strip()
            if not user_text:
                reply = "小爪没听清楚你说啥，再发一次？ 😄"
            else:
                reply = call_mimo(user_text)
        else:
            reply = f"小爪现在还在学习中，暂不支持{msg_type}类型的消息哦~ 😅"

        response = make_response(reply_text(from_user, reply))
        response.content_type = "application/xml"
        return response

    except Exception as e:
        return make_response(reply_text(
            from_user if 'from_user' in dir() else "unknown",
            f"处理消息时出错了：{str(e)}"
        ))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🤖 {BOT_NAME} 启动中，端口：{port}")
    app.run(host="0.0.0.0", port=port)