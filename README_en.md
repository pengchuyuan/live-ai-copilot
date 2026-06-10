# Live AI Copilot V2 for Windows

Live AI Copilot V2 is a local AI livestream assistant prototype for Windows desktop streamers.

It helps streamers generate real-time speaking suggestions based on livestream comments, screen text, and microphone input.

This project runs locally and does not require the OpenAI API.

## Features

- Local AI response generation with Ollama
- OCR-based screen comment reading
- Microphone speech recognition
- Configurable streamer, brand, product, and FAQ profile
- Windows desktop GUI
- No cloud API required
- No TTS voice output; the tool only displays text suggestions

## What It Does

The app can:

1. Capture a fixed screen area and recognize text using OCR.
2. Convert microphone input into text using speech recognition.
3. Send the recognized text to a local Ollama model.
4. Generate a short sentence that the streamer can say immediately.

Example:

Viewer comment:

```
How do I choose the right size?
```

AI suggestion:

```
You can check the size chart first, and if you are between sizes, I recommend choosing the larger one.
```

## Requirements

- Windows 10 or later
- Python 3.10 or 3.11
- Ollama
- Tesseract OCR
- A local Ollama model, such as `qwen2.5:3b`

## Installation

### 1. Install Python

Install Python 3.10 or 3.11.

During installation, make sure to enable:

```
Add Python to PATH
```

### 2. Install Ollama

Install Ollama for Windows.

Then open PowerShell and run:

```
ollama run qwen2.5:3b
```

If your computer has better performance, you can try:

```
ollama run qwen2.5:7b
```

The first run will download the model. After that, it can run locally.

### 3. Install Tesseract OCR

Screen comment recognition requires Tesseract OCR.

A common Windows installation path is:

```
C:\Program Files\Tesseract-OCR	esseract.exe
```

If the app cannot find Tesseract, open `config.json` and change:

```
"tesseract_cmd": ""
```

to:

```
"tesseract_cmd": "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

If you need Chinese OCR support, make sure the Chinese language package `chi_sim` is installed with Tesseract.

### 4. Install Python Dependencies

Open PowerShell inside the project folder and run:

```
pip install -r requirements.txt
```

If `faster-whisper` takes too long to install, you can use the app without speech recognition first and only use OCR/manual input.

## Run the App

You can start the app by running:

```
python app.py
```

Or double-click:

```
run.bat
```

if the batch file is included in your local version.

## How to Use

### Step 1: Start Ollama

Make sure your local model is available:

```
ollama run qwen2.5:3b
```

### Step 2: Select the Comment Area

In the app, click:

```
Select Screen Area
```

Then drag your mouse to select the livestream comment area.

Since the comment area is usually fixed, you only need to select it once. The selected coordinates will be saved to `config.json`.

### Step 3: Start OCR

Click:

```
Start OCR
```

The app will capture the selected screen area every few seconds, recognize the text, and generate a speaking suggestion.

### Step 4: Start Speech Recognition

Click:

```
Start Speech Recognition
```

The app will record microphone input and generate speaking suggestions based on recognized speech.

Note: The current version captures microphone input only. It does not capture internal system audio. To capture system audio, future versions may add Windows WASAPI loopback or virtual audio device support.

## Configuration

The app includes a configurable streamer profile.

You can edit:

- Streamer type
- Platform
- Industry
- Brand name
- Livestream goal
- Main products
- Key selling points
- FAQ
- Prohibited claims
- Speaking style

After editing, click:

```
Save Configuration
```

The settings will be saved to `config.json`.

## Common Issues

### OCR is not accurate

OCR accuracy depends on font size, text color, background, and screen resolution.

Suggestions:

- Select only the comment text area.
- Avoid selecting unnecessary background elements.
- Increase the comment font size if possible.
- Use a clean background.
- For Chinese comments, install the `chi_sim` Tesseract language package.

### AI generation is slow

Local model speed depends on your computer performance.

For most computers, start with:

```
qwen2.5:3b
```

Avoid using larger models at first.

### Speech recognition is slow

`faster-whisper` may take time to load the model for the first time.

On CPU-only machines, use a smaller model such as:

```
"model_size": "base"
```

or

```
"model_size": "small"
```

inside `config.json`.

### Can it read TikTok, Douyin, or YouTube comments automatically?

V2 uses screen OCR, so it can work with many platforms as long as the comments are visible on screen.

Future versions may support platform-specific comment APIs, but each platform has different rules and access restrictions.

## Current Limitations

- OCR is based on screenshots, so accuracy may vary.
- Speech recognition currently uses microphone input, not internal system audio.
- AI quality depends on the local model used.
- No TTS is included.
- The app only displays text suggestions and does not speak on behalf of the streamer.
- This is an early prototype, not a polished commercial product.

## Roadmap

Possible future features:

- Better floating window mode
- One-click installer for Windows
- Automatic dependency detection
- Built-in model setup guide
- Visual screen understanding for games, movies, or product displays
- Platform-specific live comment integration
- Multi-profile support for different streamers or brands
- Hotkey-based quick generation
- Better UI design

## Disclaimer

This project is an experimental local AI livestream assistant.

Please follow the rules of the platform you are streaming on. Do not use AI-generated content to mislead viewers, make false claims, or violate platform policies.

## License

License information has not been decided yet.
