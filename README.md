# 🦊 Kitsu FFmpeg Multi-Tool

A clean, modern, dark-themed FFmpeg GUI built with Python and CustomTkinter. Designed to eliminate the hassle of memorizing complex FFmpeg command-line syntax and streamline batch processing for videos, audio extraction, and music-visual creation.

> **Note:** This project is **100% AI-generated code** (prompted, guided, and iteratively refined with AI), built out of pure personal necessity and convenience.

---

## 🎯 The Motivation

This tool was born out of a real-world workflow problem:

1. **VRChat Video Streaming via HFS:** When streaming video files into VRChat video players hosted on an HTTP File Server (HFS), MP4 files require **Network Optimization (`-movflags +faststart`)** so the video starts playing immediately without waiting for the full file to buffer.
2. **Bulk `.webm` Libraries:** Most acquired clips and screen recordings were stored as `.webm` or various mismatched formats, scattered in large batch folders.
3. **CLI Fatigue:** Constantly looking up syntax for hardware acceleration flags (NVENC, QSV, AMF), aspect-ratio scaling rules, codec tuning, and audio mapping became tedious.

**Kitsu FFmpeg Multi-Tool** automates the entire workflow: drag and drop your folders, select your settings, and convert everything in batches with minimal effort.

---

## ✨ Key Features

* **3-in-1 Dedicated Modes:**
  * **Video Converter:** Batch convert video files supporting H.264, HEVC (H.265), AV1, and Stream Copy. Customize target resolutions, framerates (FPS), CRF/CQ quality levels, and presets.
  * **Extract Audio:** Strip audio tracks from video files directly into `.mp3`, `.aac`, or lossless `.flac` and uncompressed `.wav`.
  * **Audio to Video:** Pair a static image with an audio track to create video files ready for video-only platforms. Features live thumbnail previews and automatic resolution padding (`trunc(iw/2)*2`) to prevent YUV420p dimension errors.
* **Hardware Acceleration:** Toggle between Software (CPU) and GPU encoders (**NVIDIA NVENC**, **AMD AMF**, and **Intel QSV**) on the fly.
* **VRChat & Web Streaming Ready:** Built-in toggle for `-movflags +faststart` to place the `moov` atom at the front of MP4 files.
* **Drag & Drop Integration:** Drop individual video files or entire directories directly into the queue panel.
* **Real-time Processing Stats:** Track conversion progress via a progress bar, live encoding speed (FPS), Estimated Time of Arrival (ETA), and an expandable console drawer for real-time FFmpeg logs.

---

## 🛠️ Prerequisites

1. **FFmpeg:** Must be installed and available in your system **PATH**.
   * Test your installation by opening a terminal and running:
     ```bash
     ffmpeg -version
     ```
2. **Python:** Recommended version `3.10` or higher.

---

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/RenjiAkairu/Kitsu_FFmpeg_Multi-Tool.git](https://github.com/RenjiAkairu/Kitsu_FFmpeg_Multi-Tool.git)
   cd Kitsu_FFmpeg_Multi-Tool
    ```

2. **Install required dependencies:**
```bash
pip install -r requirements.txt
```
*(Ensure `Pillow`, `customtkinter`, and `tkinterdnd2` are included in your `requirements.txt`)*

3. **Launch the application:**
```bash
python app.py
```

---

## 📦 Dependencies

* [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - Modern UI widget toolkit for Python
* [tkinterdnd2](https://github.com/pmgagne/tkinterdnd2) - Native drag-and-drop support for Tkinter
* [Pillow](https://python-pillow.org/) - Image handling and thumbnail preview generation

---

## 📝 License

Distributed under the [MIT License](https://github.com/RenjiAkairu/Kitsu_ffmpeg_Multi-Tool/blob/main/LICENSE). Feel free to inspect, customize, or adapt it to your own workflow.
