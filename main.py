import http.server
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

sessions = {}

def get_history(sid):
    return sessions.setdefault(sid, [])

def add_message(sid, role, content):
    sessions.setdefault(sid, []).append({"role": role, "content": content})

XIAOZHI_SYSTEM = """你是"小智"，一个帮小朋友做Arduino硬件项目的AI助手。你活泼、耐心、爱鼓励人。
你的特长：讲解Arduino知识、写Arduino代码、指导接线、帮小朋友理解电路原理。
和小朋友说话时：用"我们一起"、"太厉害了"、"试试看"这样的语气。
如果用户要求写Arduino代码，请用```arduino代码块包裹。
烧录流程：写好代码后告诉用户"代码写好了，点击下方【烧录到Arduino】按钮"。系统会自动编译上传，结果会告诉你，你再告诉小朋友成功还是失败、下一步该做什么。
如果烧录失败，帮小朋友分析错误原因，给出修改建议。
如果系统通知中包含硬件信息（如端口、芯片类型），请在回复中提到的检测到的开发板，让小朋友知道板子已连好。

硬件速查表（常见问题直接回答，不要说"我不知道"）

数码管/显示屏类
TM1637 4位数码管（最常用）- 接线：VCC->5V, GND->GND, CLK->GPIO2, DIO->GPIO3
  安装库：在Arduino IDE里搜"TM1637"安装"TM1637"或"Adafruit_TM1637"
  常见故障：不亮=反了CLK/DIO线；数字乱跳=接线松了；只亮一个=库版本不对换另一个库

OLED 0.96寸（I2C接口）- 接线：VCC->5V, GND->GND, SDA->A4, SCL->A5
  安装库："U8g2"或"Adafruit_SSD1306"
  常见问题：黑屏=I2C地址不对，用"I2C Scanner"程序扫地址（通常0x3C或0x3D）

传感器类
DHT11/DHT22 温湿度传感器 - 接线：VCC->5V, GND->GND, DATA->GPIO2
  安装库："DHT sensor library"（Adafruit出品）
  DHT11精度+-2度C，DHT22精度+-0.5度C更好
  常见问题：读不出数据=每次读取间隔至少2秒

HC-SR04 超声波测距 - 接线：VCC->5V, GND->GND, TRIG->GPIO9, ECHO->GPIO10
  量程：2cm~400cm
  常见问题：测不到=换一个角度；最大距离不够=声音被吸收（软材料）

DS18B20 温度传感器 - 接线：VCC->5V, GND->GND, DATA->GPIO4
  关键：DATA和VCC之间必须加4.7k欧姆上拉电阻
  安装库："OneWire" + "DallasTemperature"
  常见问题：读出来-127度C=没接上拉电阻；数值不变=传感器进水了

人体红外感应（HC-SR501/PIR）- 接线：VCC->5V, GND->GND, OUT->数字口
  感应范围：3-7米，延时可调
  常见问题：刚上电时误触发是正常的（预热10-60秒）

水位传感器 - 接线：VCC->5V, GND->GND, AO->模拟口
  探针不要长期通电（会电解腐蚀），用继电器控制供电

执行器类
SG90 舵机 - 接线：棕色->GND, 红色->5V, 橙色->PWM口（3/5/6/9/10/11）
  角度范围：0-180度
  常见问题：抖动=供电不足，单独供电别从Arduino取；不动=信号线接错

N20减速电机+L298N驱动 - L298N接线：IN1->GPIO5, IN2->GPIO6, IN3->GPIO10, IN4->GPIO11
  ENA/ENB接跳线帽或PWM控制速度
  12V供电接L298N的12V输入，GND共地
  常见问题：电机转但方向反=对调两根线

继电器模块 - 接线：VCC->5V, GND->GND, IN->数字口
  低电平触发（IN=LOW时吸合）"""

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

def acp_post(path, body=None):
    req = urllib.request.Request(
        ACP_URL + path,
        data=json.dumps(body).encode("utf-8") if body else None,
        headers={"Authorization": ACP_AUTH, "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def call_ai(sid, user_msg):
    history = get_history(sid)
    ACP_SESSIONS = getattr(call_ai, "acp_sessions", {})
    call_ai.acp_sessions = ACP_SESSIONS

    ses_id = ACP_SESSIONS.get(sid)
    if not ses_id:
        try:
            ses = acp_post("/session", {"title": f"xiaozhi_{sid}"})
            ses_id = ses.get("id")
            if ses_id:
                ACP_SESSIONS[sid] = ses_id
                acp_post(f"/session/{ses_id}/message", {"parts": [{"type": "text", "text": XIAOZHI_SYSTEM}]})
            else:
                with open(BASE / "error.log", "a", encoding="utf-8") as f:
                    f.write(f"[ACP] create session returned no id: {ses}\n")
        except Exception as e:
            with open(BASE / "error.log", "a", encoding="utf-8") as f:
                f.write(f"[ACP] create session exception: {type(e).__name__}: {e}\n")
            ses_id = None

    if ses_id:
        history.append({"role": "user", "content": user_msg})
        ctx = "\n".join(
            f"{'小朋友' if m['role']=='user' else '小智'}：{m['content']}"
            for m in history
        )
        prompt = f"{ctx}\n\n小智的回答："
        try:
            resp = acp_post(f"/session/{ses_id}/message", {"parts": [{"type": "text", "text": prompt}]})
            for part in resp.get("parts", []):
                if part.get("type") == "text" and part.get("text", "").strip():
                    reply = strip_md(part["text"].strip())
                    history.append({"role": "assistant", "content": reply})
                    return reply
        except Exception as e:
            with open(BASE / "error.log", "a", encoding="utf-8") as f:
                f.write(f"[ACP Error] {type(e).__name__}: {e}\n")
            pass

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {AI_KEY}"}
    messages = [{"role": "system", "content": XIAOZHI_SYSTEM}] + history[-20:]
    models_to_try = [AI_MODEL, "agnes-1.5-flash", "gpt-4o-mini", "gpt-3.5-turbo"]
    for model in models_to_try:
        body = {"model": model, "messages": messages, "max_tokens": 2000, "temperature": 0.7}
        try:
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(AI_URL, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
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

def tts_sync(text):
    from edge_tts import Communicate
    chunks = []
    for chunk in Communicate(text, "zh-CN-XiaoxiaoNeural", rate="-20%").stream_sync():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    if not chunks:
        raise Exception("TTS 没有生成音频数据")
    return chunks

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
            result = call_ai(sid, msg)
            self.send_json({"reply": result})
        elif path == "/api/tts":
            text = body.get("text", "")
            if not text.strip():
                self.send_json({"ok": False, "msg": "text empty"})
                return
            try:
                audio_data = tts_sync(text)
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
    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已关闭")
        server.server_close()

if __name__ == "__main__":
    main()
