# 小智 TTS 发声功能使用说明

## 功能概述
小智现在支持通过 Web 界面直接发声，无需额外配置 Arduino 代码！

## 使用方式

### 1. 基本发声
在"小智"对话框中输入文字，小智会自动识别并朗读出来。

### 2. 音量调节
- 音量滑块范围：0-100
- 静音：音量设为 0

### 3. 语音选择
系统自动选择中文女声（小姚/云希），也可以切换到男声或其他声音。

## 技术原理
- 使用 Edge-TTS 调用微软 Azure 语音合成服务
- 无需 API Key，直接通过浏览器调用
- 音频数据以 Base64 格式传输，安全便捷

## 注意事项
- 需要稳定的网络连接
- 朗读内容不宜过长（建议<500 字）
- 某些特殊字符可能需要转义

## 开发者接口

### 发声 API
```
POST http://localhost:8080/api/tts
Content-Type: application/json

{
  "text": "你好，我是小智！"
}

响应：
{
  "ok": true,
  "data": "base64 音频数据...",
  "voice": "zh-CN-XiaoyiNeural"
}
```

## 常见问题

### Q: 为什么发声没有声音？
A: 请检查：
1. 浏览器是否允许自动播放音频
2. 系统音量是否开启
3. 浏览器是否支持 Web Audio API

### Q: 如何调整语速？
A: 当前版本使用微软默认语速，如需调整需修改代码中的语音参数。

### Q: 可以上传自定义语音吗？
A: 需要修改代码，使用其他 TTS 服务。

## 升级建议

### 方案一：本地 TTS 服务
```python
# 使用 pyttsx3 离线语音合成
import pyttsx3
engine = pyttsx3.init()
engine.say("你好")
engine.runAndWait()
```

### 方案二：阿里云语音合成
需要申请 API Key 并配置到 config.json：
```json
{
  "tts_api_key": "sk-xxx",
  "tts_api_url": "https://dashscope.aliyuncs.com/api/v1/services/audio/text-to-audio"
}
```

## 技术支持
如有问题，请联系管理员。
