# Live AI Copilot V2 Windows 本地版

这是一个本地模型版 AI 直播副播原型，适合 Windows 桌面直播。

它可以做三件事：

1. 截取固定弹幕区域，用 OCR 识别屏幕文字。
2. 通过麦克风做语音识别，把你说的话转成文字。
3. 调用本地 Ollama 模型，生成一句主播可以直接说的话术。

不使用 OpenAI API，不需要云端付费。

---

## 1. 安装 Python

建议安装 Python 3.10 或 3.11。

安装时勾选：Add Python to PATH。

---

## 2. 安装 Ollama 和本地模型

先安装 Ollama Windows 版。

安装后打开 PowerShell，运行：

```bash
ollama run qwen2.5:3b
```

如果电脑配置比较好，可以用：

```bash
ollama run qwen2.5:7b
```

第一次会下载模型，之后就可以本地使用。

---

## 3. 安装 OCR 软件 Tesseract

屏幕弹幕识别需要 Tesseract OCR。

Windows 常见安装路径类似：

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

如果程序提示找不到 tesseract，请打开 `config.json`，把：

```json
"tesseract_cmd": ""
```

改成：

```json
"tesseract_cmd": "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
```

如果要识别中文弹幕，安装 Tesseract 时需要包含中文语言包 `chi_sim`。

---

## 4. 安装 Python 依赖

在项目文件夹打开 PowerShell，运行：

```bash
pip install -r requirements.txt
```

如果 `faster-whisper` 安装很慢，可以先不启用语音识别，只用 OCR。

---

## 5. 启动软件

双击：

```text
run.bat
```

或者运行：

```bash
python app.py
```

---

## 6. 使用方法

### 第一步：打开 Ollama

确保本地模型正在运行，例如：

```bash
ollama run qwen2.5:3b
```

### 第二步：选择弹幕区域

在软件里点击：

```text
拖拽选择区域
```

然后用鼠标框住直播间弹幕区域。

因为你说弹幕区域是固定窗口，所以只要选一次就行，程序会保存到 `config.json`。

### 第三步：开始 OCR

点击：

```text
开始OCR读弹幕
```

程序会每隔 2 秒截取弹幕区域，识别文字，自动生成话术。

### 第四步：开启语音识别

点击：

```text
开始语音识别
```

程序会每 5 秒录一次麦克风声音，并生成下一句建议。

注意：当前版本默认识别麦克风输入，不是系统内部声音。如果你想识别直播软件里的系统声音，需要后续接 Windows WASAPI loopback 或虚拟声卡。

---

## 7. 修改主播/品牌/产品配置

软件左侧就是通用配置模板。

你可以填：

- 主播类型
- 平台
- 行业
- 品牌名
- 直播目标
- 主推产品
- 核心卖点
- FAQ
- 禁止承诺内容
- 语气风格

改完后点：

```text
保存配置
```

它会保存到 `config.json`。

---

## 8. 常见问题

### 为什么识别弹幕不准？

OCR 对字体、颜色、背景很敏感。建议：

- 只框住弹幕文字区域，不要框太大。
- 让弹幕背景尽量干净。
- 弹幕字号调大一点。
- 中文弹幕需要安装中文语言包 `chi_sim`。

### 为什么生成慢？

本地模型速度取决于电脑配置。可以先用：

```bash
qwen2.5:3b
```

不要一开始用 7B 或更大的模型。

### 为什么语音识别慢？

`faster-whisper` 第一次加载模型会比较慢。CPU 机器建议用 `small` 或 `base`。可以在 `config.json` 里改：

```json
"model_size": "base"
```

### 能不能自动读取 TikTok / 抖音弹幕？

V2 先用屏幕 OCR，适合所有平台。后续可以做平台专用接口版，但每个平台规则和接口不同。

---

## 9. 当前版本限制

- OCR 是截屏识别，准确率不如平台官方弹幕接口。
- 语音识别默认来自麦克风，不是系统音频。
- 模型完全本地，效果取决于本地模型大小。
- 不包含 TTS，不会替主播发声，只显示文字建议。

