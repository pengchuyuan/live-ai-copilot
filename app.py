import json
import queue
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import tkinter as tk
from tkinter import messagebox, scrolledtext

CONFIG_PATH = Path(__file__).with_name("config.json")


def safe_imports():
    missing = []
    modules = {}
    for name, import_name in [
        ("mss", "mss"),
        ("PIL", "PIL.Image"),
        ("pytesseract", "pytesseract"),
        ("cv2", "cv2"),
        ("numpy", "numpy"),
        ("keyboard", "keyboard"),
        ("sounddevice", "sounddevice"),
        ("faster_whisper", "faster_whisper"),
    ]:
        try:
            modules[name] = __import__(import_name, fromlist=["*"])
        except Exception:
            missing.append(name)
            modules[name] = None
    return modules, missing


MODULES, MISSING_MODULES = safe_imports()


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(config: Dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_text(text: str) -> str:
    text = text.replace("\r", "\n")
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        line = re.sub(r"\s+", " ", line)
        if line:
            lines.append(line)
    return "\n".join(lines)


def compact_context(text: str, max_chars: int = 1400) -> str:
    text = normalize_text(text)
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


@dataclass
class GenerateEvent:
    source: str
    text: str


class OllamaClient:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def update_config(self, config: Dict[str, Any]):
        self.config = config

    def build_prompt(self, event: GenerateEvent) -> str:
        ollama = self.config.get("ollama", {})
        profile = self.config.get("assistant_profile", {})
        max_context_chars = int(ollama.get("max_context_chars", 3500))
        profile_text = json.dumps(profile, ensure_ascii=False, indent=2)
        profile_text = compact_context(profile_text, max_context_chars)
        source_name = "screen OCR comments" if event.source == "ocr" else "speech transcription" if event.source == "speech" else "manual input"
        return f"""
You are a real-time livestream speaking assistant.
You help any type of streamer say the next natural line during a live stream.

Streamer / brand / product profile:
{profile_text}

Current input source: {source_name}
Current viewer comment, screen text, or live situation:
{event.text}

Generate exactly one short sentence or two very short sentences the streamer can say immediately.
Output only the speakable line. Do not explain. Do not add labels.
""".strip()

    def generate(self, event: GenerateEvent) -> str:
        ollama = self.config.get("ollama", {})
        base_url = ollama.get("base_url", "http://localhost:11434").rstrip("/")
        model = ollama.get("model", "qwen2.5:3b")
        prompt = self.build_prompt(event)
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": float(ollama.get("temperature", 0.6)),
                "num_predict": 90,
            },
        }
        r = requests.post(f"{base_url}/api/generate", json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data.get("response", "").strip()


class RegionSelector:
    def __init__(self, root: tk.Tk, on_select):
        self.root = root
        self.on_select = on_select
        self.start_x = 0
        self.start_y = 0
        self.rect = None

    def open(self):
        self.win = tk.Toplevel(self.root)
        self.win.attributes("-fullscreen", True)
        self.win.attributes("-alpha", 0.25)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="black")
        self.canvas = tk.Canvas(self.win, cursor="cross", bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_text(
            30, 30, anchor="nw", fill="white",
            text="拖拽选择弹幕区域，松开鼠标确认。按 Esc 取消。",
            font=("Microsoft YaHei", 18, "bold")
        )
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.win.bind("<Escape>", lambda e: self.win.destroy())

    def on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.rect = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="red", width=3)

    def on_drag(self, event):
        if self.rect:
            self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        left = min(self.start_x, event.x)
        top = min(self.start_y, event.y)
        width = abs(event.x - self.start_x)
        height = abs(event.y - self.start_y)
        if width > 20 and height > 20:
            self.on_select({"left": left, "top": top, "width": width, "height": height})
        self.win.destroy()


class OCRWorker(threading.Thread):
    def __init__(self, app, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.app = app
        self.stop_event = stop_event
        self.last_text = ""

    def run(self):
        if any(MODULES.get(x) is None for x in ["mss", "PIL", "pytesseract", "cv2", "numpy"]):
            self.app.log("OCR依赖未完整安装，请先 pip install -r requirements.txt")
            return
        mss = MODULES["mss"]
        Image = MODULES["PIL"]
        pytesseract = MODULES["pytesseract"]
        cv2 = MODULES["cv2"]
        np = MODULES["numpy"]

        cfg = self.app.config.get("screen_ocr", {})
        tesseract_cmd = cfg.get("tesseract_cmd", "")
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

        with mss.mss() as sct:
            while not self.stop_event.is_set():
                cfg = self.app.config.get("screen_ocr", {})
                region = cfg.get("region", {})
                interval = float(cfg.get("interval_seconds", 2.0))
                lang = cfg.get("language", "chi_sim+eng")
                min_len = int(cfg.get("min_text_length", 2))
                try:
                    shot = sct.grab(region)
                    img = Image.frombytes("RGB", shot.size, shot.rgb)
                    arr = np.array(img)
                    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
                    gray = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
                    gray = cv2.GaussianBlur(gray, (3, 3), 0)
                    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    text = pytesseract.image_to_string(thresh, lang=lang, config="--psm 6")
                    text = normalize_text(text)
                    if len(text) >= min_len and text != self.last_text:
                        self.last_text = text
                        self.app.enqueue_generation(GenerateEvent(source="ocr", text=text))
                        self.app.log(f"OCR识别：{text[:120]}")
                except Exception as e:
                    self.app.log(f"OCR错误：{e}")
                time.sleep(interval)


class SpeechWorker(threading.Thread):
    def __init__(self, app, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.app = app
        self.stop_event = stop_event
        self.model = None
        self.last_text = ""

    def run(self):
        if MODULES.get("sounddevice") is None or MODULES.get("faster_whisper") is None or MODULES.get("numpy") is None:
            self.app.log("语音识别依赖未完整安装，请先 pip install -r requirements.txt")
            return
        sd = MODULES["sounddevice"]
        np = MODULES["numpy"]
        WhisperModel = MODULES["faster_whisper"].WhisperModel
        cfg = self.app.config.get("speech", {})
        model_size = cfg.get("model_size", "small")
        self.app.log(f"正在加载语音模型 faster-whisper: {model_size}，第一次可能较慢。")
        try:
            self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        except Exception as e:
            self.app.log(f"语音模型加载失败：{e}")
            return
        self.app.log("语音识别已启动。")
        while not self.stop_event.is_set():
            cfg = self.app.config.get("speech", {})
            seconds = float(cfg.get("interval_seconds", 5))
            sample_rate = int(cfg.get("sample_rate", 16000))
            device = cfg.get("device_index", None)
            language = cfg.get("language", "zh") or None
            try:
                audio = sd.rec(int(seconds * sample_rate), samplerate=sample_rate, channels=1, dtype="float32", device=device)
                sd.wait()
                audio = np.squeeze(audio)
                segments, _info = self.model.transcribe(audio, language=language, vad_filter=True)
                text = normalize_text(" ".join(seg.text.strip() for seg in segments))
                if text and text != self.last_text:
                    self.last_text = text
                    self.app.enqueue_generation(GenerateEvent(source="speech", text=text))
                    self.app.log(f"语音识别：{text[:120]}")
            except Exception as e:
                self.app.log(f"语音识别错误：{e}")
                time.sleep(1)


class GeneratorWorker(threading.Thread):
    def __init__(self, app, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.app = app
        self.stop_event = stop_event

    def run(self):
        while not self.stop_event.is_set():
            try:
                event = self.app.generation_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self.app.set_status("正在生成话术...")
                reply = self.app.ollama.generate(event)
                if reply:
                    self.app.show_reply(reply, event)
                else:
                    self.app.log("模型返回空内容。")
            except Exception as e:
                self.app.log(f"生成失败：{e}")
            finally:
                self.app.set_status("待机")


class LiveAICopilotApp:
    def __init__(self):
        self.config = load_config()
        self.ollama = OllamaClient(self.config)
        self.root = tk.Tk()
        self.root.title("Live AI Copilot V2 - 本地弹幕/语音直播副播")
        self.root.geometry("1100x760")
        self.root.minsize(920, 650)
        self.root.attributes("-topmost", True)
        self.generation_queue: queue.Queue[GenerateEvent] = queue.Queue(maxsize=10)
        self.stop_event = threading.Event()
        self.ocr_stop = threading.Event()
        self.speech_stop = threading.Event()
        self.ocr_worker: Optional[OCRWorker] = None
        self.speech_worker: Optional[SpeechWorker] = None
        self.generator_worker = GeneratorWorker(self, self.stop_event)
        self.build_ui()
        self.generator_worker.start()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        if MISSING_MODULES:
            self.log("部分依赖未安装：" + ", ".join(MISSING_MODULES) + "。请运行 pip install -r requirements.txt")

    def build_ui(self):
        top = tk.Frame(self.root)
        top.pack(fill=tk.X, padx=10, pady=8)
        self.status_var = tk.StringVar(value="待机")
        tk.Label(top, text="模型：").pack(side=tk.LEFT)
        self.model_var = tk.StringVar(value=self.config.get("ollama", {}).get("model", "qwen2.5:3b"))
        tk.Entry(top, textvariable=self.model_var, width=18).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="保存模型", command=self.save_model).pack(side=tk.LEFT, padx=4)
        self.topmost_var = tk.BooleanVar(value=True)
        tk.Checkbutton(top, text="窗口置顶", variable=self.topmost_var, command=self.toggle_topmost).pack(side=tk.LEFT, padx=8)
        tk.Label(top, textvariable=self.status_var, fg="blue").pack(side=tk.RIGHT)

        main = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        left = tk.Frame(main)
        right = tk.Frame(main)
        main.add(left, width=440)
        main.add(right, width=650)

        tk.Label(left, text="主播/品牌/产品配置（通用模板）", font=("Microsoft YaHei", 11, "bold")).pack(anchor="w")
        self.profile_text = scrolledtext.ScrolledText(left, height=24, wrap=tk.WORD)
        self.profile_text.pack(fill=tk.BOTH, expand=True, pady=6)
        self.profile_text.insert("1.0", json.dumps(self.config.get("assistant_profile", {}), ensure_ascii=False, indent=2))
        btns = tk.Frame(left)
        btns.pack(fill=tk.X, pady=4)
        tk.Button(btns, text="保存配置", command=self.save_profile).pack(side=tk.LEFT, padx=2)
        tk.Button(btns, text="重新加载", command=self.reload_config).pack(side=tk.LEFT, padx=2)
        tk.Button(btns, text="测试Ollama", command=self.test_ollama).pack(side=tk.LEFT, padx=2)

        tk.Label(left, text="弹幕区域", font=("Microsoft YaHei", 10, "bold")).pack(anchor="w", pady=(10, 0))
        region_frame = tk.Frame(left)
        region_frame.pack(fill=tk.X, pady=4)
        region = self.config.get("screen_ocr", {}).get("region", {})
        self.left_var = tk.IntVar(value=int(region.get("left", 1200)))
        self.top_var = tk.IntVar(value=int(region.get("top", 120)))
        self.width_var = tk.IntVar(value=int(region.get("width", 650)))
        self.height_var = tk.IntVar(value=int(region.get("height", 760)))
        for label, var in [("L", self.left_var), ("T", self.top_var), ("W", self.width_var), ("H", self.height_var)]:
            tk.Label(region_frame, text=label).pack(side=tk.LEFT)
            tk.Entry(region_frame, textvariable=var, width=6).pack(side=tk.LEFT, padx=2)
        tk.Button(region_frame, text="拖拽选择区域", command=self.select_region).pack(side=tk.LEFT, padx=5)
        ocr_btns = tk.Frame(left)
        ocr_btns.pack(fill=tk.X, pady=4)
        tk.Button(ocr_btns, text="开始OCR读弹幕", command=self.start_ocr).pack(side=tk.LEFT, padx=2)
        tk.Button(ocr_btns, text="停止OCR", command=self.stop_ocr).pack(side=tk.LEFT, padx=2)
        speech_btns = tk.Frame(left)
        speech_btns.pack(fill=tk.X, pady=4)
        tk.Button(speech_btns, text="开始语音识别", command=self.start_speech).pack(side=tk.LEFT, padx=2)
        tk.Button(speech_btns, text="停止语音", command=self.stop_speech).pack(side=tk.LEFT, padx=2)

        tk.Label(right, text="手动输入 / 当前情况", font=("Microsoft YaHei", 11, "bold")).pack(anchor="w")
        self.manual_input = scrolledtext.ScrolledText(right, height=5, wrap=tk.WORD)
        self.manual_input.pack(fill=tk.X, pady=6)
        action_frame = tk.Frame(right)
        action_frame.pack(fill=tk.X)
        tk.Button(action_frame, text="生成话术", command=self.manual_generate, height=2).pack(side=tk.LEFT, padx=2)
        tk.Button(action_frame, text="清空输入", command=lambda: self.manual_input.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=2)
        tk.Button(action_frame, text="复制话术", command=self.copy_reply).pack(side=tk.LEFT, padx=2)

        tk.Label(right, text="AI建议主播说", font=("Microsoft YaHei", 12, "bold")).pack(anchor="w", pady=(12, 0))
        self.reply_text = scrolledtext.ScrolledText(right, height=8, wrap=tk.WORD, font=("Microsoft YaHei", 18))
        self.reply_text.pack(fill=tk.BOTH, expand=True, pady=6)

        tk.Label(right, text="运行日志", font=("Microsoft YaHei", 10, "bold")).pack(anchor="w")
        self.log_text = scrolledtext.ScrolledText(right, height=9, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=6)

    def save_model(self):
        self.config.setdefault("ollama", {})["model"] = self.model_var.get().strip() or "qwen2.5:3b"
        save_config(self.config)
        self.ollama.update_config(self.config)
        self.log("模型配置已保存。")

    def toggle_topmost(self):
        self.root.attributes("-topmost", bool(self.topmost_var.get()))

    def save_profile(self):
        try:
            profile = json.loads(self.profile_text.get("1.0", tk.END))
            self.config["assistant_profile"] = profile
            self.save_region_to_config()
            save_config(self.config)
            self.ollama.update_config(self.config)
            self.log("配置已保存到 config.json。")
        except Exception as e:
            messagebox.showerror("配置错误", f"JSON格式不正确：{e}")

    def save_region_to_config(self):
        self.config.setdefault("screen_ocr", {})["region"] = {
            "left": int(self.left_var.get()),
            "top": int(self.top_var.get()),
            "width": int(self.width_var.get()),
            "height": int(self.height_var.get()),
        }

    def reload_config(self):
        try:
            self.config = load_config()
            self.ollama.update_config(self.config)
            self.profile_text.delete("1.0", tk.END)
            self.profile_text.insert("1.0", json.dumps(self.config.get("assistant_profile", {}), ensure_ascii=False, indent=2))
            region = self.config.get("screen_ocr", {}).get("region", {})
            self.left_var.set(int(region.get("left", 1200)))
            self.top_var.set(int(region.get("top", 120)))
            self.width_var.set(int(region.get("width", 650)))
            self.height_var.set(int(region.get("height", 760)))
            self.model_var.set(self.config.get("ollama", {}).get("model", "qwen2.5:3b"))
            self.log("配置已重新加载。")
        except Exception as e:
            self.log(f"重新加载失败：{e}")

    def test_ollama(self):
        self.enqueue_generation(GenerateEvent(source="manual", text="测试：直播间没人说话，我现在应该说什么？"))

    def select_region(self):
        RegionSelector(self.root, self.on_region_selected).open()

    def on_region_selected(self, region: Dict[str, int]):
        self.left_var.set(region["left"])
        self.top_var.set(region["top"])
        self.width_var.set(region["width"])
        self.height_var.set(region["height"])
        self.save_region_to_config()
        save_config(self.config)
        self.log(f"已选择弹幕区域：{region}")

    def start_ocr(self):
        self.save_region_to_config()
        save_config(self.config)
        if self.ocr_worker and self.ocr_worker.is_alive():
            self.log("OCR已经在运行。")
            return
        self.ocr_stop.clear()
        self.ocr_worker = OCRWorker(self, self.ocr_stop)
        self.ocr_worker.start()
        self.log("OCR读弹幕已启动。")

    def stop_ocr(self):
        self.ocr_stop.set()
        self.log("OCR读弹幕已停止。")

    def start_speech(self):
        if self.speech_worker and self.speech_worker.is_alive():
            self.log("语音识别已经在运行。")
            return
        self.speech_stop.clear()
        self.speech_worker = SpeechWorker(self, self.speech_stop)
        self.speech_worker.start()
        self.log("语音识别启动中。")

    def stop_speech(self):
        self.speech_stop.set()
        self.log("语音识别已停止。")

    def manual_generate(self):
        text = self.manual_input.get("1.0", tk.END).strip()
        if not text:
            return
        self.enqueue_generation(GenerateEvent(source="manual", text=text))

    def enqueue_generation(self, event: GenerateEvent):
        try:
            if self.generation_queue.full():
                try:
                    self.generation_queue.get_nowait()
                except queue.Empty:
                    pass
            self.generation_queue.put_nowait(event)
        except Exception as e:
            self.log(f"加入生成队列失败：{e}")

    def show_reply(self, reply: str, event: GenerateEvent):
        def update():
            self.reply_text.delete("1.0", tk.END)
            self.reply_text.insert("1.0", reply)
            self.log(f"生成[{event.source}]：{reply}")
        self.root.after(0, update)

    def copy_reply(self):
        text = self.reply_text.get("1.0", tk.END).strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.log("话术已复制。")

    def set_status(self, text: str):
        self.root.after(0, lambda: self.status_var.set(text))

    def log(self, text: str):
        timestamp = time.strftime("%H:%M:%S")
        def update():
            self.log_text.insert(tk.END, f"[{timestamp}] {text}\n")
            self.log_text.see(tk.END)
        try:
            self.root.after(0, update)
        except Exception:
            pass

    def on_close(self):
        self.stop_event.set()
        self.ocr_stop.set()
        self.speech_stop.set()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    LiveAICopilotApp().run()
