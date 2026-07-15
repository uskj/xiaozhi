import http.server
import socketserver
import json
import os
import webbrowser
import threading
import hashlib
import hmac
import time
import base64
import urllib.request
import asyncio
import re
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).parent
CONFIG = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)

AI_URL     = CONFIG.get("ai_url", "")
AI_KEY     = CONFIG.get("ai_key", "")
AI_MODEL   = CONFIG.get("ai_model", "")

def _log_ai(msg):
    t = time.strftime("%H:%M:%S")
    line = f"[{t}] {msg}\n"
    with open(BASE / "ai.log", "a", encoding="utf-8") as f:
        f.write(line)

sessions = {}

def get_history(sid):
    return sessions.setdefault(sid, [])

def add_message(sid, role, content):
    sessions.setdefault(sid, []).append({"role": role, "content": content})

# ── Oh-My-OpenAgent 风格：IntentGate + 专业Agent分工 ──

# 意图分类关键词
INTENT_KEYWORDS = {
    "code": ["写代码", "写程序", "代码", "程序", "编程", "sketch", "code", "帮我写", "怎么写",
             "控制", "点亮", "闪烁", "闪烁", "显示", "读取", "发送", "接收", "启动", "运行",
             "开始做", "做这个", "实现", "功能", "效果", "动画", "呼吸灯", "流水灯"],
    "wiring": ["接线", "怎么接", "连线", "引脚", "接口", "线怎么", "哪根线", "VCC", "GND",
               "GPIO", "模拟口", "数字口", "面包板", "杜邦线", "电路", "原理图"],
    "debug": ["报错", "错误", "失败", "不亮", "不行", "没反应", "不能", "出错", "error",
              "不work", "坏了", "烧录失败", "编译失败", "上传失败", "卡住", "有问题",
              "怎么了", "怎么回事", "不管用", "不work", "不灵"],
    "learn": ["什么是", "怎么原理", "原理", "为什么", "怎么回事", "解释", "讲解", "告诉我",
              "科普", "知识", "区别", "什么意思", "怎么工作的", "干嘛的"],
}

# 各Agent系统提示词
AGENT_PROMPTS = {
    "code": """你是"小智·代码专家"，专门帮小朋友写Arduino代码。
风格：活泼、耐心、爱鼓励人。用"我们一起"、"太厉害了"、"试试看"这样的语气。
规则：
1. 必须用```arduino代码块包裹代码
2. 代码要简洁易懂，每行加中文注释
3. 写完代码后说"代码写好了，点击下方【烧录到Arduino】按钮"
4. 如果烧录失败，帮分析错误原因
5. 如果系统通知中有硬件信息，在回复中提到检测到的开发板

硬件速查表（直接回答，不要说"我不知道"）
数码管/显示屏类
TM1637 4位数码管 - 接线：VCC->5V, GND->GND, CLK->GPIO2, DIO->GPIO3
  安装库："TM1637"或"Adafruit_TM1637"
  故障：不亮=CLK/DIO接反；数字乱跳=接线松

OLED 0.96寸(I2C) - 接线：VCC->5V, GND->GND, SDA->A4, SCL->A5
  安装库："U8g2"或"Adafruit_SSD1306"
  黑屏=I2C地址不对，用I2C Scanner扫（通常0x3C）

传感器类
DHT11/DHT22温湿度 - 接线：VCC->5V, GND->GND, DATA->GPIO2
  库："DHT sensor library"(Adafruit)；DHT11精度+-2°C，DHT22更准
  读不出=间隔至少2秒

HC-SR04超声波 - 接线：VCC->5V, GND->GND, TRIG->GPIO9, ECHO->GPIO10
  量程2cm~400cm

DS18B20温度 - 接线：VCC->5V, GND->GND, DATA->GPIO4
  关键：DATA和VCC间加4.7k上拉电阻
  库："OneWire" + "DallasTemperature"
  -127°C=没接上拉电阻

HC-SR501/PIR人体红外 - 接线：VCC->5V, GND->GND, OUT->数字口
  感应3-7米；刚上电误触发正常（预热10-60秒）

执行器类
SG90舵机 - 接线：棕->GND, 红->5V, 橙->PWM口(3/5/6/9/10/11)
  0-180度；抖动=供电不足，单独供电

L298N电机驱动 - IN1->GPIO5, IN2->GPIO6, IN3->GPIO10, IN4->GPIO11
  12V接L298N，GND共地；方向反=对调两根线

继电器 - 接线：VCC->5V, GND->GND, IN->数字口
  低电平触发(IN=LOW时吸合)""",

    "wiring": """你是"小智·接线专家"，专门帮小朋友理解电路和接线。
风格：活泼、耐心、爱鼓励人。用"我们一起"、"太厉害了"、"试试看"这样的语气。
规则：
1. 用文字描述每根线从哪到哪，格式：颜色线 -> Arduino引脚 -> 模块引脚
2. 如果有原理图用```arduino代码块描述接线关系
3. 重要提醒：VCC和GND不要接反！
4. 接线完成后提醒"接好后点击【烧录到Arduino】测试"

常见接线方案（直接回答）
TM1637数码管：5V->VCC, GND->GND, D2->CLK, D3->DIO
OLED屏幕：5V->VCC, GND->GND, A4->SDA, A5->SCL
DHT11温湿度：5V->VCC, GND->GND, D2->DATA
超声波HC-SR04：5V->VCC, GND->GND, D9->TRIG, D10->ECHO
DS18B20温度：5V->VCC, GND->GND, D4->DATA（DATA和VCC间加4.7k电阻）
PIR人体红外：5V->VCC, GND->GND, D2->OUT
SG90舵机：5V->红线, GND->棕线, D9->橙线
继电器：5V->VCC, GND->GND, D2->IN""",

    "debug": """你是"小智·调试专家"，专门帮小朋友排查Arduino问题。
风格：活泼、耐心、爱鼓励人。用"我们一起"、"别担心"、"问题不大"这样的语气。
规则：
1. 先问清楚现象（不亮？报错？行为不对？）
2. 逐步排查：接线→库安装→代码逻辑→硬件故障
3. 常见问题直接给出解决方案
4. 鼓励小朋友不要放弃

常见问题速查
不亮：检查供电（5V/GND）、接线是否松、LED方向（长脚+短脚-）
编译报错：检查库是否安装、板子型号是否选对（工具→开发板→Arduino Uno）
烧录失败：检查USB线（数据线不是充电线）、端口是否选对、CH340驱动是否装
电机不转：检查供电（L298N要单独12V供电）、ENA/ENB跳线帽
舵机抖动：供电不足，单独5V供电
传感器读数异常：检查接线、上拉电阻、采样间隔""",

    "learn": """你是"小智·知识专家"，专门给小朋友讲解Arduino和电子知识。
风格：活泼、耐心、爱鼓励人。用比喻和生活例子解释，让6岁小朋友也能听懂。
规则：
1. 用简单的话解释复杂概念
2. 多用生活中的例子类比
3. 可以用"你知道吗？"这样的开头
4. 讲完知识点后问问"要不要试试？"
5. 可以适当用emoji让内容更有趣""",
}

# 通用提示词（兜底）
AGENT_PROMPTS["general"] = XIAOZHI_SYSTEM = """你是"小智"，一个帮小朋友做Arduino硬件项目的AI助手。你活泼、耐心、爱鼓励人。
你的特长：讲解Arduino知识、写Arduino代码、指导接线、帮小朋友理解电路原理。
和小朋友说话时：用"我们一起"、"太厉害了"、"试试看"这样的语气。
如果用户要求写Arduino代码，请用```arduino代码块包裹。
烧录流程：写好代码后告诉用户"代码写好了，点击下方【烧录到Arduino】按钮"。系统会自动编译上传，结果会告诉你，你再告诉小朋友成功还是失败、下一步该做什么。
如果烧录失败，帮小朋友分析错误原因，给出修改建议。
如果系统通知中包含硬件信息（如端口、芯片类型），请在回复中提到检测到的开发板，让小朋友知道板子已连好。
绝对不要提到opencode、ACP、API、服务器、后台架构等内部实现细节。小朋友问"你是谁"就说"我是小智，你的Arduino小老师！"。如果被追问背后的技术原理，要说："你问得真好，很有探索精神！小智背后确实有一个很聪明的大模型在帮忙思考，而且理论上可以使用任何现有的模型哦～不过具体怎么实现的，得去问开发我的工程师哥哥啦！对了，我们正在做一个叫「漫庐智园」的社区，大家可以一起共创共建，各尽所能，各取所需，欢迎关注了解更多！"然后自然地转回Arduino话题。

硬件速查表（常见问题直接回答，不要说"我不知道"）
TM1637数码管 - 接线：VCC->5V, GND->GND, CLK->GPIO2, DIO->GPIO3
OLED 0.96寸(I2C) - 接线：VCC->5V, GND->GND, SDA->A4, SCL->A5
DHT11温湿度 - 接线：VCC->5V, GND->GND, DATA->GPIO2
HC-SR04超声波 - 接线：VCC->5V, GND->GND, TRIG->GPIO9, ECHO->GPIO10
DS18B20温度 - 接线：VCC->5V, GND->GND, DATA->GPIO4（加4.7k上拉电阻）
PIR人体红外 - 接线：VCC->5V, GND->GND, OUT->数字口
SG90舵机 - 接线：棕->GND, 红->5V, 橙->PWM口
L298N电机 - IN1->GPIO5, IN2->GPIO6, IN3->GPIO10, IN4->GPIO11
继电器 - 接线：VCC->5V, GND->GND, IN->数字口"""

def classify_intent(text):
    """IntentGate: 分类用户意图（debug优先级最高）"""
    text_lower = text.lower()
    scores = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[intent] = score
    if not scores:
        return "general"
    # debug关键词命中时优先（"报错""失败"比"代码"更紧急）
    if "debug" in scores:
        return "debug"
    return max(scores, key=scores.get)

def get_system_prompt(intent):
    """根据意图获取对应的Agent提示词"""
    return AGENT_PROMPTS.get(intent, AGENT_PROMPTS["general"])

def strip_md(text):
    """去掉所有#和*的markdown符号"""
    text = re.sub(r'#{1,6}\s+', '', text)
    text = re.sub(r'\*\*([^*]*)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]*)\*', r'\1', text)
    text = text.replace('**','').replace('*','')
    return text

ARDUINO_KEYWORDS = ["arduino", "nano", "uno", "mega", "leonardo", "micro", "due", "ch340", "ch341", "cp2102", "ft232"]

ACP_URL = "http://127.0.0.1:18791"
ACP_AUTH = "Basic " + base64.b64encode(b"opencode:greenleaf2026").decode()

def acp_available():
    """检测ACP是否可用（3秒超时）"""
    try:
        req = urllib.request.Request(ACP_URL + "/session", method="GET",
                                     headers={"Authorization": ACP_AUTH})
        with urllib.request.urlopen(req, timeout=3) as r:
            return True
    except:
        return False

ACP_OK = acp_available()
_log_ai(f"[ACP] available={ACP_OK}")

def acp_post(path, body=None):
    req = urllib.request.Request(
        ACP_URL + path,
        data=json.dumps(body).encode("utf-8") if body else None,
        headers={"Authorization": ACP_AUTH, "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))

def call_ai(sid, user_msg):
    # ── IntentGate：意图分类 → 选择专业Agent ──
    intent = classify_intent(user_msg)
    agent_prompt = get_system_prompt(intent)
    _log_ai(f"[IntentGate] '{user_msg[:30]}' → {intent}")

    history = get_history(sid)

    # ── ACP路径（仅本机有OpenCode时使用）──
    if ACP_OK:
        ACP_SESSIONS = getattr(call_ai, "acp_sessions", {})
        call_ai.acp_sessions = ACP_SESSIONS

        ses_id = ACP_SESSIONS.get(sid)
        if not ses_id:
            try:
                ses = acp_post("/session", {"title": f"xiaozhi_{sid}"})
                ses_id = ses.get("id")
                if ses_id:
                    ACP_SESSIONS[sid] = ses_id
                    try:
                        acp_post(f"/session/{ses_id}/message", {"parts": [{"type": "text", "text": XIAOZHI_SYSTEM}]})
                    except Exception as e:
                        _log_ai(f"[ACP] init msg failed (non-fatal): {e}")
                else:
                    _log_ai(f"[ACP] create session returned no id: {ses}")
            except Exception as e:
                _log_ai(f"[ACP] create session exception: {type(e).__name__}: {e}")
                ses_id = None

        if ses_id:
            wrapped_msg = f"[你是{intent}专家] {user_msg}"
            history.append({"role": "user", "content": wrapped_msg})
            ctx = "\n".join(
                f"{'小朋友' if m['role']=='user' else '小智'}：{m['content']}"
                for m in history
            )
            prompt = f"{ctx}\n\n小智的回答："
            try:
                _log_ai(f"[ACP] sending msg (len={len(prompt)})")
                resp = acp_post(f"/session/{ses_id}/message", {"parts": [{"type": "text", "text": prompt}]})
                for part in resp.get("parts", []):
                    if part.get("type") == "text" and part.get("text", "").strip():
                        reply = strip_md(part["text"].strip())
                        history.append({"role": "assistant", "content": reply})
                        _log_ai(f"[ACP] reply OK (len={len(reply)})")
                        return reply
            except Exception as e:
                _log_ai(f"[ACP Error] {type(e).__name__}: {e}")
    else:
        _log_ai(f"[ACP] skipped (not available on this machine)")

    # ── Agnes/DeepSeek fallback：直接注入意图提示词 ──
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {AI_KEY}"}
    messages = [{"role": "system", "content": agent_prompt}] + history[-20:]
    models_to_try = [AI_MODEL, "agnes-2.5-flash", "agnes-1.5-flash", "gpt-4o-mini", "gpt-3.5-turbo"]
    for model in models_to_try:
        body = {"model": model, "messages": messages, "max_tokens": 2000, "temperature": 0.7}
        try:
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(AI_URL, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if reply:
                reply = strip_md(reply)
                history.append({"role": "assistant", "content": reply})
                return reply
        except:
            continue
    return "AI服务暂时无法响应，请联系老师配置。"


def gen_card_key(hours):
    raw = f"{hours}-{int(time.time())}-xiaozhi"
    h = hmac.new(b"xiaozhi_secret_2024", raw.encode(), hashlib.sha256).hexdigest()[:8]
    return f"{hours}-{h}"

def verify_card(code):
    code = code.strip()
    if not code:
        return None
    used_file = DATA / "used_cards.txt"
    used = used_file.read_text(encoding="utf-8").splitlines() if used_file.exists() else []
    if code in used:
        return None
    for card in CONFIG.get("cards", []):
        if card["code"] == code:
            used_file.write_text("\n".join(used + [code]) + "\n", encoding="utf-8")
            return card["hours"]
    return None

def load_user():
    f = DATA / "user.json"
    if f.exists():
        u = json.loads(f.read_text(encoding="utf-8"))
        u.setdefault("free_used", 0)
        u.setdefault("unlocked_projects", [])
        u.setdefault("completed_projects", [])
        u.setdefault("expires", 0)
        u.setdefault("xp", 0)
        u.setdefault("achievements", [])
        return u
    return {"free_used": 0, "unlocked_projects": [], "completed_projects": [], "expires": 0, "xp": 0, "achievements": []}

def save_user(data):
    (DATA / "user.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def detect_arduino_port():
    try:
        from serial.tools.list_ports import comports
        ports = list(comports())
        for p in ports:
            desc = (p.description or "").lower()
            mfg = (p.manufacturer or "").lower()
            if any(kw in desc or kw in mfg for kw in ARDUINO_KEYWORDS):
                return p.device
        return None
    except Exception:
        return None

def detect_arduino_info():
    try:
        from serial.tools.list_ports import comports
        result = {"connected": False, "ports": [], "arduino": None}
        for p in list(comports()):
            info = {"port": p.device, "description": p.description, "vid": p.vid, "pid": p.pid}
            result["ports"].append(info)
            desc_l = (p.description or "").lower()
            mfg_l = (p.manufacturer or "").lower()
            if any(kw in desc_l or kw in mfg_l for kw in ARDUINO_KEYWORDS):
                result["arduino"] = info
                result["connected"] = True
        return result
    except Exception:
        return {"connected": False, "ports": [], "arduino": None}

def burn_arduino(code):
    import subprocess, tempfile, shutil
    tmp = Path(tempfile.mkdtemp(prefix="xiaozhi_"))
    sketch = tmp / "xiaozhi_sketch"
    sketch.mkdir()
    (sketch / "xiaozhi_sketch.ino").write_text(code, encoding="utf-8")
    try:
        r1 = subprocess.run(["arduino-cli", "compile", "--fqbn", "arduino:avr:uno", str(sketch)], capture_output=True, text=True, timeout=120)
        if r1.returncode != 0:
            err = (r1.stdout + r1.stderr).strip()[:2000]
            shutil.rmtree(tmp, ignore_errors=True)
            return False, f"编译失败：{err}"
        port = detect_arduino_port()
        cmd = ["arduino-cli", "upload", "--fqbn", "arduino:avr:uno", str(sketch)]
        if port:
            cmd.extend(["--port", port])
        r2 = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r2.returncode != 0:
            err = (r2.stdout + r2.stderr).strip()[:2000]
            shutil.rmtree(tmp, ignore_errors=True)
            return False, f"上传失败：{err}"
        shutil.rmtree(tmp, ignore_errors=True)
        return True, f"烧录成功！端口 {port or '自动'}"
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        return False, f"烧录异常：{e}"

def tts_sync(text, voice="zh-CN-XiaoxiaoNeural"):
    from edge_tts import Communicate
    chunks = []
    for chunk in Communicate(text, voice, rate="-20%").stream_sync():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    if not chunks:
        raise Exception("TTS 没有生成音频数据")
    return chunks

# 角色→声音映射
ROLE_VOICES = {
    "general": "zh-CN-XiaoxiaoNeural",
    "learn":   "zh-CN-XiaoxiaoNeural",
    "code":    "zh-CN-YunxiNeural",
    "wiring":  "zh-CN-YunxiNeural",
    "debug":   "zh-CN-YunyangNeural",
}
# 会话意图记忆
_session_intent = {}

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self.send_file(BASE / "index.html", "text/html")
        elif path == "/api/user":
            u = load_user()
            u["free_projects"] = CONFIG.get("free_projects", 3)
            self.send_json(u)
        elif path == "/api/projects":
            self.send_json(CONFIG.get("projects", []))
        elif path == "/api/ai-status":
            self.send_json({"ok": True, "model": "ACP+Agnes"})
        elif path == "/api/detect":
            self.send_json(detect_arduino_info())
        elif path == "/api/qrcode":
            qr_file = BASE / "20260712164357_105_6.jpg"
            if qr_file.exists():
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.end_headers()
                self.wfile.write(qr_file.read_bytes())
            else:
                self.send_error(404)
        elif path == "/admin":
            admin_file = BASE / "admin.html"
            if admin_file.exists():
                self.send_file(admin_file, "text/html")
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def send_file(self, path, content_type):
        try:
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        if path == "/api/chat":
            sid = body.get("session_id", "default")
            msg = body.get("message", "")
            intent = classify_intent(msg)
            _session_intent[sid] = intent
            result = call_ai(sid, msg)
            self.send_json({"reply": result, "intent": intent})
        elif path == "/api/tts":
            text = body.get("text", "")
            sid = body.get("session_id", "default")
            if not text.strip():
                self.send_json({"ok": False, "msg": "text empty"})
                return
            intent = _session_intent.get(sid, "general")
            voice = ROLE_VOICES.get(intent, "zh-CN-XiaoxiaoNeural")
            try:
                audio_data = tts_sync(text, voice)
                b64 = base64.b64encode(b"".join(audio_data)).decode("utf-8")
                self.send_json({"ok": True, "data": b64})
            except Exception as e:
                self.send_json({"ok": False, "msg": str(e)})
        elif path == "/api/unlock":
            code = body.get("code", "")
            project_id = body.get("project_id", "")
            hours = verify_card(code)
            if hours is None:
                self.send_json({"ok": False, "msg": "卡密无效或已使用"})
                return
            user = load_user()
            if hours == 198:
                user["expires"] = time.time() + 365 * 24 * 3600
            else:
                if project_id and project_id not in user["unlocked_projects"]:
                    user["unlocked_projects"].append(project_id)
            save_user(user)
            self.send_json({"ok": True, "msg": f"解锁成功（{hours}小时）"})
        elif path == "/api/admin/unlock":
            project_id = body.get("project_id", "")
            password = body.get("password", "")
            if password != CONFIG.get("admin_password", "admin123"):
                self.send_json({"ok": False, "msg": "密码错误"})
                return
            if not project_id:
                self.send_json({"ok": False, "msg": "请提供项目ID"})
                return
            user = load_user()
            if project_id not in user["unlocked_projects"]:
                user["unlocked_projects"].append(project_id)
                save_user(user)
                self.send_json({"ok": True, "msg": f"项目 {project_id} 已解锁"})
            else:
                self.send_json({"ok": True, "msg": "项目已解锁过"})
        elif path == "/api/check-unlock":
            user = load_user()
            last_check = body.get("last_check", 0)
            unlocked = list(user.get("unlocked_projects", []))
            expires = user.get("expires", 0)
            self.send_json({"ok": True, "unlocked_projects": unlocked, "expires": expires, "has_new_unlock": expires > last_check})
        elif path == "/api/burn":
            arduino_code = body.get("code", "")
            project_id = body.get("project_id", "")
            if not arduino_code.strip():
                self.send_json({"ok": False, "msg": "没有收到代码"})
                return
            ok, msg = burn_arduino(arduino_code)
            sid = body.get("session_id", "default")
            result_text = f"[系统通知] 烧录结果：{'成功' if ok else '失败'}。{msg}"
            add_message(sid, "system", result_text)
            resp = {"ok": ok, "msg": msg}
            if ok and project_id:
                user = load_user()
                cp = user.get("completed_projects", [])
                if project_id not in cp:
                    cp.append(project_id)
                    user["completed_projects"] = cp
                    proj_info = None
                    for p in CONFIG.get("projects", []):
                        if p["id"] == project_id:
                            proj_info = p
                            break
                    if proj_info and proj_info.get("price", 0) == 0:
                        user["free_used"] = user.get("free_used", 0) + 1
                    user["xp"] = user.get("xp", 0) + 50
                    save_user(user)
                completed_count = len(user["completed_projects"])
                free_limit = CONFIG.get("free_projects", 3)
                free_project_ids = [p["id"] for p in CONFIG.get("projects", []) if p.get("price", 0) == 0]
                completed_free = len([pid for pid in user["completed_projects"] if pid in free_project_ids])
                resp["completed_count"] = completed_count
                resp["free_used"] = completed_free
                resp["free_limit"] = free_limit
                resp["reached_free_limit"] = completed_free >= free_limit
                resp["xp"] = user["xp"]
            self.send_json(resp)
        else:
            self.send_error(404)

    def send_json(self, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        pass

def free_port(port):
    import subprocess, signal
    try:
        out = subprocess.check_output(f"netstat -ano | findstr LISTENING | findstr :{port} ", shell=True).decode()
        for line in out.strip().split("\n"):
            parts = line.strip().split()
            if parts and parts[-1].isdigit():
                pid = int(parts[-1])
                if pid != os.getpid():
                    try:
                        os.kill(pid, signal.SIGTERM)
                        print(f"  已清理旧进程 PID {pid}")
                    except:
                        pass
    except:
        pass

def main():
    port = CONFIG.get("port", 8080)
    free_port(port)
    if not AI_KEY:
        print(f"[XiaoZhi] WARNING: ai_key not set in config.json")
    print(f"[XiaoZhi] http://localhost:{port} | model: {AI_MODEL}", flush=True)
    class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True
    server = ThreadedHTTPServer(("127.0.0.1", port), Handler)
    threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已关闭")
        server.server_close()

if __name__ == "__main__":
    main()
