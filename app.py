import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import threading
import os
import re
from pathlib import Path
import sys
import time
from PIL import Image

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
except ImportError:
    messagebox.showerror("Error", "tkinterdnd2 is not installed. Please run: pip install tkinterdnd2")
    sys.exit(1)

# Set theme
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class ToolTip(object):
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.close)
        self.tw = None

    def update_text(self, text):
        self.text = text
        if self.tw:
            for child in self.tw.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(text=self.text)

    def enter(self, event=None):
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tw, text=self.text, justify='left',
                       background="#2b2b2b", foreground="white", relief='solid', borderwidth=1,
                       font=("Segoe UI", 9))
        label.pack(ipadx=8, ipady=5)
        self.tw.attributes("-topmost", True)

    def close(self, event=None):
        if self.tw:
            self.tw.destroy()
            self.tw = None

class TkinterDnD_CTk(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)


class FFmpegGUI(TkinterDnD_CTk):
    def __init__(self):
        super().__init__()

        self.title("Kitsu FFmpeg Multi-Tool (Convert, Extract2Audio, Audio2Video)")
        self.geometry("1250x850")
        self.minsize(1050, 750)

        self.files_to_convert = [] 
        self.dest_dir = ""
        self.is_converting = False
        self.cancel_requested = False
        self.process = None
        self.card_fg_color = ("gray85", "gray17")
        self.static_image_path = ""

        if not self.check_ffmpeg():
            messagebox.showerror("Error", "FFMPEG is not installed or not in system PATH.")
            sys.exit(1)

        self.setup_ui()
        self.update_vc_preset_options()
        self.update_vc_audio_state()
        self.update_a2v_preset_options()

        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.on_drop)

    @property
    def valid_exts(self):
        mode = self.mode_tabs.get()
        if mode == "Audio to Video":
            return ['.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg', '.wma']
        elif mode == "Extract Audio":
            return ['.mp4', '.mkv', '.mov', '.webm', '.avi', '.flv', '.ts', '.mp3', '.wav', '.flac', '.aac']
        else: # Video Converter
            return ['.mp4', '.mkv', '.mov', '.webm', '.avi', '.flv', '.ts']

    def check_ffmpeg(self):
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, startupinfo=startupinfo)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def setup_ui(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=15, pady=15)

        self.top_section = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.top_section.pack(fill="both", expand=True)
        
        self.top_section.grid_columnconfigure(0, weight=1, uniform="group1") 
        self.top_section.grid_columnconfigure(1, weight=1, uniform="group1") 
        self.top_section.grid_rowconfigure(0, weight=1)

        self._build_left_pane()
        self._build_right_pane()
        self._build_footer()

    def _build_left_pane(self):
        self.left_pane = ctk.CTkFrame(self.top_section, fg_color=self.card_fg_color, corner_radius=10)
        self.left_pane.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.left_pane.grid_columnconfigure(0, weight=1)
        self.left_pane.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(self.left_pane, text="Queue / File List (Drag & Drop Supported)", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=15, pady=12, sticky="w")

        self.btn_frame = ctk.CTkFrame(self.left_pane, fg_color="transparent")
        self.btn_frame.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="ew")
        
        self.btn_add_file = ctk.CTkButton(self.btn_frame, text="Add File(s)", width=90, command=self.select_single_file)
        self.btn_add_file.pack(side="left", padx=(0, 6))
        self.btn_add_folder = ctk.CTkButton(self.btn_frame, text="Add Folder", width=90, command=self.select_folder)
        self.btn_add_folder.pack(side="left", padx=(0, 6))
        self.btn_clear = ctk.CTkButton(self.btn_frame, text="Clear", width=60, fg_color="#8B0000", hover_color="#600000", command=self.clear_queue)
        self.btn_clear.pack(side="right")

        self.file_list_frame = ctk.CTkScrollableFrame(self.left_pane, fg_color="transparent")
        self.file_list_frame.grid(row=2, column=0, sticky="nsew", padx=15, pady=(0, 15))
        
        self.file_list_frame.grid_columnconfigure(0, weight=1)
        self.file_list_frame.grid_columnconfigure(1, weight=0, minsize=85)
        self.file_list_frame.grid_columnconfigure(2, weight=0, minsize=100)
        
        self.draw_table_headers()

    def _build_right_pane(self):
        self.right_pane = ctk.CTkFrame(self.top_section, fg_color="transparent")
        self.right_pane.grid(row=0, column=1, sticky="nsew")
        self.right_pane.grid_columnconfigure(0, weight=1)
        self.right_pane.grid_rowconfigure(1, weight=1)

        # Output Settings (Shared)
        self.out_card = ctk.CTkFrame(self.right_pane, fg_color=self.card_fg_color, corner_radius=10)
        self.out_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.out_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.out_card, text="Shared Output Settings", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=3, padx=15, pady=(10, 5), sticky="w")
        
        self.btn_dest = ctk.CTkButton(self.out_card, text="Change Dest", width=100, command=self.select_dest_folder)
        self.btn_dest.grid(row=1, column=0, padx=15, pady=5, sticky="w")
        
        self.lbl_dest = ctk.CTkLabel(self.out_card, text="Default: <Source>/Converted", text_color="gray")
        self.lbl_dest.grid(row=1, column=1, padx=(0, 10), pady=5, sticky="w")

        self.btn_open_dest = ctk.CTkButton(self.out_card, text="Open Folder", width=90, fg_color="gray60", hover_color="gray40", command=self.open_dest_folder)
        self.btn_open_dest.grid(row=1, column=2, padx=(0, 15), pady=5, sticky="e")

        self.suffix_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.out_card, text="Add suffix", variable=self.suffix_var).grid(row=2, column=0, padx=15, pady=(5, 15), sticky="w")

        self.overwrite_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.out_card, text="Overwrite existing (-y)", variable=self.overwrite_var).grid(row=2, column=1, columnspan=2, padx=15, pady=(5, 15), sticky="w")

        # Mode Tabs
        self.mode_tabs = ctk.CTkTabview(self.right_pane)
        self.mode_tabs.grid(row=1, column=0, sticky="nsew")
        self.mode_tabs.configure(command=self.on_tab_changed)

        tab_vc = self.mode_tabs.add("Video Converter")
        self._build_tab_video_converter(tab_vc)

        tab_ea = self.mode_tabs.add("Extract Audio")
        self._build_tab_extract_audio(tab_ea)

        tab_a2v = self.mode_tabs.add("Audio to Video")
        self._build_tab_audio_to_video(tab_a2v)

    def _add_adv_checkbox(self, parent, row, text, var, tooltip):
        cb = ctk.CTkCheckBox(parent, text=text, variable=var)
        cb.grid(row=row, column=0, pady=5, sticky="w")
        lbl = ctk.CTkLabel(parent, text="(?)", text_color="gray50")
        lbl.grid(row=row, column=1, padx=5, sticky="w")
        ToolTip(lbl, tooltip)

    def toggle_adv_mode(self, _=None):
        if self.advance_mode_var.get():
            self.adv_card.pack(fill="x", pady=(0, 15))
        else:
            self.adv_card.pack_forget()

    def _build_tab_video_converter(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        self.vid_card = ctk.CTkFrame(scroll, fg_color=self.card_fg_color, corner_radius=10)
        self.vid_card.pack(fill="x", pady=(0, 15))
        self.vid_card.grid_columnconfigure((1, 3), weight=1) 
        
        ctk.CTkLabel(self.vid_card, text="Video Settings", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=4, padx=15, pady=(10, 5), sticky="w")

        # Format & Preset
        ctk.CTkLabel(self.vid_card, text="Format:").grid(row=1, column=0, padx=15, pady=5, sticky="w")
        self.vc_target_format = ctk.CTkComboBox(self.vid_card, values=[".mp4", ".mkv", ".mov", ".webm", ".avi"])
        self.vc_target_format.grid(row=1, column=1, padx=15, pady=5, sticky="ew")

        preset_header = ctk.CTkFrame(self.vid_card, fg_color="transparent")
        preset_header.grid(row=1, column=2, padx=15, pady=5, sticky="w")
        ctk.CTkLabel(preset_header, text="Preset:").pack(side="left")
        
        self.vc_preset_icon = ctk.CTkLabel(preset_header, text="?", width=18, height=18, corner_radius=9, fg_color=("gray75", "gray30"), text_color=("gray20", "gray85"), font=ctk.CTkFont(size=11, weight="bold"), cursor="hand2")
        self.vc_preset_icon.pack(side="left", padx=(6, 0))
        self.vc_preset_tooltip = ToolTip(self.vc_preset_icon, text="")
        
        self.vc_preset_combo = ctk.CTkComboBox(self.vid_card, values=[])
        self.vc_preset_combo.grid(row=1, column=3, padx=15, pady=5, sticky="ew")

        # Codec & FPS
        ctk.CTkLabel(self.vid_card, text="Video Codec:").grid(row=2, column=0, padx=15, pady=5, sticky="w")
        self.vc_video_codec = ctk.CTkComboBox(self.vid_card, values=["H.264", "H.265 (HEVC)", "AV1", "Copy (No re-encode)"], command=self.update_vc_video_state)
        self.vc_video_codec.grid(row=2, column=1, padx=15, pady=5, sticky="ew")

        ctk.CTkLabel(self.vid_card, text="FPS:").grid(row=2, column=2, padx=15, pady=5, sticky="w")
        self.vc_fps_combo = ctk.CTkComboBox(self.vid_card, values=["Keep Original", "24", "30", "60"])
        self.vc_fps_combo.grid(row=2, column=3, padx=15, pady=5, sticky="ew")

        # Encoder & Quality
        ctk.CTkLabel(self.vid_card, text="Encoder:").grid(row=3, column=0, padx=15, pady=5, sticky="w")
        self.vc_hardware_encoder = ctk.CTkComboBox(self.vid_card, values=["Software (CPU)", "NVIDIA (NVENC)", "AMD (AMF)", "Intel (QSV)"], command=self.update_vc_preset_options)
        self.vc_hardware_encoder.set("Software (CPU)")
        self.vc_hardware_encoder.grid(row=3, column=1, padx=15, pady=5, sticky="ew")

        crf_header = ctk.CTkFrame(self.vid_card, fg_color="transparent")
        crf_header.grid(row=3, column=2, columnspan=2, padx=15, pady=5, sticky="w")
        self.vc_crf_title_lbl = ctk.CTkLabel(crf_header, text="Quality (CRF/CQ: 23) - Default")
        self.vc_crf_title_lbl.pack(side="left")
        
        self.vc_crf_icon = ctk.CTkLabel(crf_header, text="?", width=18, height=18, corner_radius=9, fg_color=("gray75", "gray30"), text_color=("gray20", "gray85"), font=ctk.CTkFont(size=11, weight="bold"), cursor="hand2")
        self.vc_crf_icon.pack(side="left", padx=(6, 0))
        crf_info = ("The lower the value, the higher the quality and larger the file size:\n\n"
                    "• 0 = Uncompressed (Lossless / Very large file)\n"
                    "• 18-20 = Very high quality (Almost indistinguishable)\n"
                    "• 23 = Standard (Balance between size and quality)\n"
                    "• 28 = Space-saving, small file size\n"
                    "• 51 = Lowest quality")
        ToolTip(self.vc_crf_icon, text=crf_info)

        # Resolution & Slider
        ctk.CTkLabel(self.vid_card, text="Resolution:").grid(row=4, column=0, padx=15, pady=5, sticky="w")
        
        self.vc_res_frame = ctk.CTkFrame(self.vid_card, fg_color="transparent")
        self.vc_res_frame.grid(row=4, column=1, padx=15, pady=5, sticky="ew")
        
        self.vc_resolution = ctk.CTkComboBox(self.vc_res_frame, values=["Keep Original", "480p", "720p", "1080p", "2K", "4K", "Custom"], command=self.update_vc_res_state)
        self.vc_resolution.pack(fill="x", pady=(0, 2))
        self.vc_custom_res_entry = ctk.CTkEntry(self.vc_res_frame, placeholder_text="e.g. 1920x1080 or -2:720")

        self.vc_crf_slider = ctk.CTkSlider(self.vid_card, from_=0, to=51, number_of_steps=51, command=self.update_vc_crf_label)
        self.vc_crf_slider.set(23)
        self.vc_crf_slider.grid(row=4, column=2, columnspan=2, padx=15, pady=5, sticky="ew")

        # Advanced Mode Switch
        self.advance_mode_var = ctk.BooleanVar(value=False)
        self.chk_adv_mode = ctk.CTkSwitch(self.vid_card, text="Advanced Mode", variable=self.advance_mode_var, command=self.toggle_adv_mode)
        self.chk_adv_mode.grid(row=5, column=0, padx=15, pady=(2, 10), sticky="w")

        self.adv_card_container = ctk.CTkFrame(scroll, fg_color="transparent")
        self.adv_card_container.pack(fill="x")

        # --- Advanced Video Card ---
        self.adv_card = ctk.CTkFrame(self.adv_card_container, fg_color=self.card_fg_color, corner_radius=10)
        self.adv_card.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(self.adv_card, text="Advanced Encoder Settings", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=4, padx=15, pady=(10, 5), sticky="w")

        # Scaling Filter
        ctk.CTkLabel(self.adv_card, text="Scaling Filter:").grid(row=1, column=0, padx=15, pady=5, sticky="w")
        self.vc_scaler_filter = ctk.CTkComboBox(self.adv_card, values=["Lanczos", "Spline", "Bicubic", "Bilinear"])
        self.vc_scaler_filter.set("Bicubic")
        self.vc_scaler_filter.grid(row=1, column=1, padx=15, pady=5, sticky="ew")
        
        lbl_sf_help = ctk.CTkLabel(self.adv_card, text="(?)", text_color="gray50")
        lbl_sf_help.grid(row=1, column=2, padx=(5, 15), pady=5, sticky="w")
        ToolTip(lbl_sf_help, "Lanczos: Maximum sharpness (may cause halo).\nSpline: Balanced sharpness, low halo.\nBicubic: Standard soft/natural image.\nBilinear: Fastest processing, softer image.")

        # Rate Control
        ctk.CTkLabel(self.adv_card, text="Rate Control Mode:").grid(row=2, column=0, padx=15, pady=5, sticky="w")
        self.vc_rc_mode = ctk.CTkComboBox(self.adv_card, values=["CQ / CRF (Quality)", "VBR (Variable Bitrate)", "CBR (Constant Bitrate)"], command=self.update_vc_rc_mode)
        self.vc_rc_mode.grid(row=2, column=1, padx=15, pady=5, sticky="ew")

        lbl_rc_help = ctk.CTkLabel(self.adv_card, text="(?)", text_color="gray50")
        lbl_rc_help.grid(row=2, column=2, padx=(5, 15), pady=5, sticky="w")
        ToolTip(lbl_rc_help, "CQ / CRF: Focuses on preserving quality (slider-based).\nVBR: Variable bitrate. Controls target/max bounds.\nCBR: Constant bitrate. Forces exact bitrate.")

        self.vc_limit_bitrate_var = ctk.BooleanVar(value=True)
        self.chk_limit_bitrate = ctk.CTkCheckBox(self.adv_card, text="Limit Max Bitrate (Auto by Resolution)", variable=self.vc_limit_bitrate_var)
        self.chk_limit_bitrate.grid(row=3, column=1, columnspan=2, padx=15, pady=5, sticky="w")
        
        lbl_lim_help = ctk.CTkLabel(self.adv_card, text="(?)", text_color="gray50")
        lbl_lim_help.grid(row=3, column=2, padx=(5, 15), pady=5, sticky="w")
        ToolTip(lbl_lim_help, "Dynamically limits max bitrate based on resolution to prevent buffering.\n480p=3M, 720p=6M, 1080p=12M, 2K/4K=45M.")

        self.vc_bitrate_frame = ctk.CTkFrame(self.adv_card, fg_color="transparent")
        self.vc_bitrate_frame.grid(row=4, column=0, columnspan=4, padx=15, pady=5, sticky="ew")
        
        self.lbl_vbr_target = ctk.CTkLabel(self.vc_bitrate_frame, text="Target:")
        self.lbl_vbr_target.pack(side="left", padx=(0,5))
        self.vc_vbr_target = ctk.CTkEntry(self.vc_bitrate_frame, width=80, placeholder_text="e.g. 6000")
        self.vc_vbr_target.pack(side="left", padx=5)
        
        self.lbl_vbr_max = ctk.CTkLabel(self.vc_bitrate_frame, text="kbps   Max:")
        self.lbl_vbr_max.pack(side="left", padx=(10,5))
        self.vc_vbr_max = ctk.CTkEntry(self.vc_bitrate_frame, width=80, placeholder_text="e.g. 12000")
        self.vc_vbr_max.pack(side="left", padx=5)
        self.lbl_vbr_kbps = ctk.CTkLabel(self.vc_bitrate_frame, text="kbps")
        self.lbl_vbr_kbps.pack(side="left", padx=(5,0))
        
        self.vc_bitrate_frame.grid_remove()

        # Hardware Features Container
        self.hw_features_frame = ctk.CTkFrame(self.adv_card, fg_color="transparent")
        self.hw_features_frame.grid(row=5, column=0, columnspan=4, padx=15, pady=10, sticky="ew")

        # NVENC
        self.nvenc_features = ctk.CTkFrame(self.hw_features_frame, fg_color="transparent")
        self.vc_nvenc_saq = ctk.BooleanVar(value=True)
        self.vc_nvenc_taq = ctk.BooleanVar(value=True)
        self.vc_nvenc_lookahead = ctk.BooleanVar(value=True)
        self.vc_nvenc_wp = ctk.BooleanVar(value=True)
        self._add_adv_checkbox(self.nvenc_features, 0, "Spatial AQ", self.vc_nvenc_saq, "Smooths out square blocks in dark scenes or rapid lighting changes.")
        self._add_adv_checkbox(self.nvenc_features, 1, "Temporal AQ", self.vc_nvenc_taq, "Reduces bitrate in static scenes to make fast-moving scenes clearer.")
        self._add_adv_checkbox(self.nvenc_features, 2, "RC Lookahead", self.vc_nvenc_lookahead, "Pre-reads 32 frames to prepare bitrate for sudden flashes/movement.")
        self._add_adv_checkbox(self.nvenc_features, 3, "Weighted Prediction", self.vc_nvenc_wp, "Fixes flickering in flash/laser scenes.\n(WARNING: Disables B-Frames, which may increase file size)")

        # QSV
        self.qsv_features = ctk.CTkFrame(self.hw_features_frame, fg_color="transparent")
        self.vc_qsv_lookahead = ctk.BooleanVar(value=True)
        self.vc_qsv_adapt = ctk.BooleanVar(value=True)
        self._add_adv_checkbox(self.qsv_features, 0, "Lookahead", self.vc_qsv_lookahead, "Enable Intel's frame scanning feature to capture high-motion scenes.")
        self._add_adv_checkbox(self.qsv_features, 1, "Adaptive I/B-Frames", self.vc_qsv_adapt, "Instruct chip to dynamically compress frames during rapid scene switches.")

        # AMF
        self.amf_features = ctk.CTkFrame(self.hw_features_frame, fg_color="transparent")
        self.vc_amf_preanalysis = ctk.BooleanVar(value=True)
        self.vc_amf_vbaq = ctk.BooleanVar(value=True)
        self._add_adv_checkbox(self.amf_features, 0, "Pre-Analysis", self.vc_amf_preanalysis, "Proactively analyzes video to identify fast-moving objects and adjust bitrate.")
        self._add_adv_checkbox(self.amf_features, 1, "VBAQ (Variance Based AQ)", self.vc_amf_vbaq, "Smooths pixels on flat surfaces and dark scenes to prevent pixelation.")

        # CPU
        self.cpu_features = ctk.CTkFrame(self.hw_features_frame, fg_color="transparent")
        self.vc_cpu_aq = ctk.BooleanVar(value=True)
        self._add_adv_checkbox(self.cpu_features, 0, "AQ-Mode 3 (Dark Bias)", self.vc_cpu_aq, "Focuses on smoothing dark and fast-changing light scenes to prevent blocking.")

        # Audio Card
        self.aud_card = ctk.CTkFrame(scroll, fg_color=self.card_fg_color, corner_radius=10)
        self.aud_card.pack(fill="x", pady=(0, 15))
        self.aud_card.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(self.aud_card, text="Audio & Advanced Settings", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=4, padx=15, pady=(10, 5), sticky="w")

        ctk.CTkLabel(self.aud_card, text="Audio Codec:").grid(row=1, column=0, padx=15, pady=5, sticky="w")
        self.vc_audio_codec = ctk.CTkComboBox(self.aud_card, values=["AAC", "MP3", "AC3", "FLAC", "Copy (No re-encode)"], command=self.update_vc_audio_state)
        self.vc_audio_codec.grid(row=1, column=1, padx=15, pady=5, sticky="ew")

        ctk.CTkLabel(self.aud_card, text="Audio Bitrate:").grid(row=1, column=2, padx=15, pady=5, sticky="w")
        self.vc_audio_bitrate = ctk.CTkComboBox(self.aud_card, values=["128k", "192k", "256k", "320k"])
        self.vc_audio_bitrate.grid(row=1, column=3, padx=15, pady=5, sticky="ew")

        self.vc_faststart_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.aud_card, text="Network Optimization (faststart)", variable=self.vc_faststart_var).grid(row=2, column=0, columnspan=2, padx=15, pady=(10, 15), sticky="w")


    def _build_tab_extract_audio(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        ea_card = ctk.CTkFrame(scroll, fg_color=self.card_fg_color, corner_radius=10)
        ea_card.pack(fill="x", pady=5)
        ea_card.grid_columnconfigure((1), weight=1)

        ctk.CTkLabel(ea_card, text="Extract Audio Settings", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=2, padx=15, pady=(10, 10), sticky="w")

        ctk.CTkLabel(ea_card, text="Target Format:").grid(row=1, column=0, padx=15, pady=10, sticky="w")
        self.ea_target_format = ctk.CTkComboBox(ea_card, values=[".mp3", ".aac", ".flac", ".wav"], command=self.update_ea_state)
        self.ea_target_format.grid(row=1, column=1, padx=15, pady=10, sticky="ew")

        ctk.CTkLabel(ea_card, text="Audio Bitrate:").grid(row=2, column=0, padx=15, pady=10, sticky="w")
        self.ea_audio_bitrate = ctk.CTkComboBox(ea_card, values=["128k", "192k", "256k", "320k"])
        self.ea_audio_bitrate.grid(row=2, column=1, padx=15, pady=10, sticky="ew")
        
        ctk.CTkLabel(ea_card, text="Note: Extracting to FLAC or WAV is lossless and ignores bitrate.").grid(row=3, column=0, columnspan=2, padx=15, pady=(0,15), sticky="w")


    def _build_tab_audio_to_video(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # Image Selection
        img_card = ctk.CTkFrame(scroll, fg_color=self.card_fg_color, corner_radius=10)
        img_card.pack(fill="x", pady=5)
        img_card.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(img_card, text="Static Image Selection", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=3, padx=15, pady=(10, 5), sticky="w")
        
        self.btn_select_img = ctk.CTkButton(img_card, text="Select Image", width=120, command=self.select_static_image)
        self.btn_select_img.grid(row=1, column=0, padx=15, pady=(5,15), sticky="nw")
        
        self.lbl_static_img = ctk.CTkLabel(img_card, text="No image selected", text_color="gray", wraplength=200)
        self.lbl_static_img.grid(row=1, column=1, padx=10, pady=(5,15), sticky="nw")
        
        # Image Preview
        self.img_preview_lbl = ctk.CTkLabel(img_card, text="No Preview", width=120, height=90, fg_color="gray25", corner_radius=8)
        self.img_preview_lbl.grid(row=1, column=2, padx=15, pady=(0, 15), sticky="e")

        # Video Settings (A2V)
        a2v_vid_card = ctk.CTkFrame(scroll, fg_color=self.card_fg_color, corner_radius=10)
        a2v_vid_card.pack(fill="x", pady=10)
        a2v_vid_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(a2v_vid_card, text="Output Video & Audio Settings", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=2, padx=15, pady=(10, 5), sticky="w")
        
        ctk.CTkLabel(a2v_vid_card, text="Video Format:").grid(row=1, column=0, padx=15, pady=5, sticky="w")
        self.a2v_target_format = ctk.CTkComboBox(a2v_vid_card, values=[".mp4", ".mkv"])
        self.a2v_target_format.grid(row=1, column=1, padx=15, pady=5, sticky="ew")

        ctk.CTkLabel(a2v_vid_card, text="Encoder:").grid(row=2, column=0, padx=15, pady=5, sticky="w")
        self.a2v_hardware_encoder = ctk.CTkComboBox(a2v_vid_card, values=["Software (CPU)", "NVIDIA (NVENC)", "AMD (AMF)", "Intel (QSV)"], command=self.update_a2v_preset_options)
        self.a2v_hardware_encoder.grid(row=2, column=1, padx=15, pady=5, sticky="ew")
        
        ctk.CTkLabel(a2v_vid_card, text="Preset:").grid(row=3, column=0, padx=15, pady=5, sticky="w")
        self.a2v_preset_combo = ctk.CTkComboBox(a2v_vid_card, values=[])
        self.a2v_preset_combo.grid(row=3, column=1, padx=15, pady=5, sticky="ew")

        ctk.CTkLabel(a2v_vid_card, text="FPS (Low is fine for static):").grid(row=4, column=0, padx=15, pady=5, sticky="w")
        self.a2v_fps_combo = ctk.CTkComboBox(a2v_vid_card, values=["1", "2", "24", "30"])
        self.a2v_fps_combo.grid(row=4, column=1, padx=15, pady=5, sticky="ew")
        
        ctk.CTkLabel(a2v_vid_card, text="Resolution:").grid(row=5, column=0, padx=15, pady=5, sticky="w")
        
        self.a2v_res_frame = ctk.CTkFrame(a2v_vid_card, fg_color="transparent")
        self.a2v_res_frame.grid(row=5, column=1, padx=15, pady=5, sticky="ew")
        
        self.a2v_resolution = ctk.CTkComboBox(self.a2v_res_frame, values=["Match Image Size", "480p", "720p", "1080p", "2K", "4K", "Custom"], command=self.update_a2v_res_state)
        self.a2v_resolution.pack(fill="x", pady=(0, 2))
        self.a2v_custom_res_entry = ctk.CTkEntry(self.a2v_res_frame, placeholder_text="e.g. 1920x1080 or -2:720")

        ctk.CTkLabel(a2v_vid_card, text="Audio Bitrate:").grid(row=6, column=0, padx=15, pady=(5, 15), sticky="w")
        self.a2v_audio_bitrate = ctk.CTkComboBox(a2v_vid_card, values=["Copy Original", "128k", "192k", "256k", "320k"])
        self.a2v_audio_bitrate.set("Copy Original")
        self.a2v_audio_bitrate.grid(row=6, column=1, padx=15, pady=(5, 15), sticky="ew")

    def _build_footer(self):
        self.footer = ctk.CTkFrame(self.main_container, fg_color=("gray85", "gray17"), corner_radius=10)
        self.footer.pack(fill="x", side="bottom")
        self.footer.grid_columnconfigure(1, weight=1) 
        
        self.details_var = ctk.BooleanVar(value=False)
        self.switch_details = ctk.CTkSwitch(self.footer, text="Console", variable=self.details_var, command=self.toggle_details, width=50)
        self.switch_details.grid(row=0, column=0, padx=15, pady=15, sticky="w")
        
        self.progress_bar = ctk.CTkProgressBar(self.footer)
        self.progress_bar.grid(row=0, column=1, padx=15, pady=15, sticky="ew")
        self.progress_bar.set(0)

        self.btn_convert = ctk.CTkButton(self.footer, text="Convert", font=ctk.CTkFont(weight="bold"), width=120, command=self.toggle_conversion)
        self.btn_convert.grid(row=0, column=2, padx=15, pady=15, sticky="e")

        self.status_frame = ctk.CTkFrame(self.footer, fg_color="transparent", height=25)
        self.status_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=15)
        self.status_frame.grid_columnconfigure(1, weight=1)
        
        self.lbl_status = ctk.CTkLabel(self.status_frame, text="Ready", text_color="gray")
        self.lbl_status.grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.lbl_eta = ctk.CTkLabel(self.status_frame, text="", text_color="gray")
        self.lbl_eta.grid(row=0, column=1, sticky="e", pady=(0, 5))

        self.console_textbox = ctk.CTkTextbox(self.footer, height=120)

    # --- Mode Update Handlers ---
    def on_tab_changed(self):
        pass

    def select_static_image(self):
        file = filedialog.askopenfilename(filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp")])
        if file:
            self.static_image_path = file
            self.lbl_static_img.configure(text=Path(file).name)
            
            try:
                img = Image.open(file)
                # Keep aspect ratio while fitting into 120x90
                img.thumbnail((120, 90), Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                self.img_preview_lbl.configure(image=ctk_img, text="")
            except Exception as e:
                self.img_preview_lbl.configure(image="", text="Preview Error")

    # --- Existing VC Handlers ---
    def update_vc_crf_label(self, val):
        val = int(val)
        text = f"Quality (CRF/CQ: {val}) - "
        if val <= 20: text += "High Quality"
        elif val <= 24: text += "Default"
        else: text += "Small File"
        self.vc_crf_title_lbl.configure(text=text)

    def update_vc_rc_mode(self, val=None):
        if not hasattr(self, 'vc_rc_mode'): return
        mode = self.vc_rc_mode.get()
        if mode in ["VBR (Variable Bitrate)", "CBR (Constant Bitrate)"]:
            self.vc_bitrate_frame.grid()
            self.vc_crf_slider.configure(state="disabled")
            self.chk_limit_bitrate.configure(state="disabled")
            
            for child in self.vc_bitrate_frame.winfo_children():
                child.pack_forget()
                
            if mode == "CBR (Constant Bitrate)":
                self.lbl_vbr_target.pack(side="left", padx=(0,5))
                self.vc_vbr_target.pack(side="left", padx=5)
                self.lbl_vbr_kbps.configure(text="kbps")
                self.lbl_vbr_kbps.pack(side="left", padx=(5,0))
            else:
                self.lbl_vbr_target.pack(side="left", padx=(0,5))
                self.vc_vbr_target.pack(side="left", padx=5)
                self.lbl_vbr_max.configure(text="kbps   Max:")
                self.lbl_vbr_max.pack(side="left", padx=(10,5))
                self.vc_vbr_max.pack(side="left", padx=5)
                self.lbl_vbr_kbps.configure(text="kbps")
                self.lbl_vbr_kbps.pack(side="left", padx=(5,0))
        else:
            self.vc_bitrate_frame.grid_remove()
            self.vc_crf_slider.configure(state="normal")
            self.chk_limit_bitrate.configure(state="normal")

    def update_vc_preset_options(self, _=None):
        enc = self.vc_hardware_encoder.get()
        is_nvenc = "NVENC" in enc
        is_qsv = "QSV" in enc
        is_amf = "AMF" in enc
        
        if hasattr(self, 'hw_features_frame'):
            for child in self.hw_features_frame.winfo_children():
                child.grid_remove()
            
            if is_nvenc:
                self.nvenc_features.grid(row=0, column=0, sticky="ew")
            elif is_qsv:
                self.qsv_features.grid(row=0, column=0, sticky="ew")
            elif is_amf:
                self.amf_features.grid(row=0, column=0, sticky="ew")
            else:
                self.cpu_features.grid(row=0, column=0, sticky="ew")

        if "CPU" in enc:
            self.vc_preset_combo.configure(values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"])
            self.vc_preset_combo.set("medium")
            self.vc_preset_tooltip.update_text("Compression speed: Slower = Smaller file size at the same quality\n(Recommended: medium or slow)")
        elif is_nvenc:
            self.vc_preset_combo.configure(values=["p1", "p2", "p3", "p4", "p5", "p6", "p7"])
            self.vc_preset_combo.set("p4")
            self.vc_preset_tooltip.update_text(
                "Graphics card speed: p1 (Fastest) to p7 (Sharpest / Slowest)\n"
                "(Recommended: p4 for general videos, p6-p7 for flashing/high-motion party clips)"
            )
        else:
            self.vc_preset_combo.configure(values=["default", "quality", "speed", "balanced"])
            self.vc_preset_combo.set("default")
            self.vc_preset_tooltip.update_text("Hardware specific preset profiles.")

    def update_a2v_preset_options(self, _=None):
        enc = self.a2v_hardware_encoder.get()
        if "CPU" in enc:
            self.a2v_preset_combo.configure(values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"])
            self.a2v_preset_combo.set("medium")
        elif "NVENC" in enc:
            self.a2v_preset_combo.configure(values=["p1", "p2", "p3", "p4", "p5", "p6", "p7"])
            self.a2v_preset_combo.set("p4")
        else:
            self.a2v_preset_combo.configure(values=["default", "quality", "speed", "balanced"])
            self.a2v_preset_combo.set("default")

    def update_vc_audio_state(self, _=None):
        ac = self.vc_audio_codec.get()
        if ac in ["Copy (No re-encode)", "FLAC"]:
            self.vc_audio_bitrate.configure(state="disabled")
        else:
            self.vc_audio_bitrate.configure(state="normal")

    def update_ea_state(self, _=None):
        fmt = self.ea_target_format.get()
        if fmt in [".flac", ".wav"]:
            self.ea_audio_bitrate.configure(state="disabled")
        else:
            self.ea_audio_bitrate.configure(state="normal")

    def update_vc_video_state(self, _=None):
        vc = self.vc_video_codec.get()
        if vc == "Copy (No re-encode)":
            self.vc_hardware_encoder.configure(state="disabled")
            self.vc_preset_combo.configure(state="disabled")
            self.vc_crf_slider.configure(state="disabled")
            self.vc_resolution.configure(state="disabled")
            self.vc_fps_combo.configure(state="disabled")
            if self.vc_custom_res_entry.winfo_ismapped():
                self.vc_custom_res_entry.pack_forget()
        else:
            self.vc_hardware_encoder.configure(state="normal")
            self.vc_preset_combo.configure(state="normal")
            self.vc_crf_slider.configure(state="normal")
            self.vc_resolution.configure(state="normal")
            self.vc_fps_combo.configure(state="normal")
            self.update_vc_res_state()

    def update_vc_res_state(self, _=None):
        if self.vc_resolution.get() == "Custom":
            self.vc_custom_res_entry.pack(fill="x", pady=(5, 0))
        else:
            if self.vc_custom_res_entry.winfo_ismapped():
                self.vc_custom_res_entry.pack_forget()

    def update_a2v_res_state(self, _=None):
        if self.a2v_resolution.get() == "Custom":
            self.a2v_custom_res_entry.pack(fill="x", pady=(5, 0))
        else:
            if self.a2v_custom_res_entry.winfo_ismapped():
                self.a2v_custom_res_entry.pack_forget()

    # --- Common UI Handlers ---
    def draw_table_headers(self):
        hdr_fg = ("gray80", "gray25")
        ctk.CTkLabel(self.file_list_frame, text="Name", fg_color=hdr_fg, corner_radius=5).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ctk.CTkLabel(self.file_list_frame, text="Size", fg_color=hdr_fg, corner_radius=5).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ctk.CTkLabel(self.file_list_frame, text="Status", fg_color=hdr_fg, corner_radius=5).grid(row=0, column=2, sticky="ew", padx=2, pady=2)

    def toggle_details(self):
        if self.details_var.get():
            self.status_frame.grid_forget()
            self.console_textbox.grid(row=1, column=0, columnspan=3, padx=15, pady=(0, 15), sticky="ew")
            self.status_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 5))
        else:
            self.console_textbox.grid_forget()

    def set_default_dest_dir(self, source_path):
        if not self.dest_dir and source_path:
            p = Path(source_path)
            parent = p.parent if p.is_file() else p
            self.dest_dir = str(parent / "Converted")
            self.lbl_dest.configure(text=self.dest_dir)

    def refresh_file_list(self):
        for widget in self.file_list_frame.winfo_children():
            widget.destroy()
        self.draw_table_headers()
        if not self.files_to_convert: return
            
        for i, item in enumerate(self.files_to_convert):
            row_idx = i + 1
            name_text = item['path'].name
            display_name = name_text if len(name_text) < 65 else name_text[:62] + "..."
            
            lbl_name = ctk.CTkLabel(self.file_list_frame, text=display_name, anchor="w")
            lbl_name.grid(row=row_idx, column=0, sticky="ew", padx=5, pady=2)
            ToolTip(lbl_name, text=str(item['path']))
            
            size_mb = item['path'].stat().st_size / (1024 * 1024)
            lbl_size = ctk.CTkLabel(self.file_list_frame, text=f"{size_mb:.1f} MB")
            lbl_size.grid(row=row_idx, column=1, sticky="ew", padx=5, pady=2)
            
            color = "white"
            if item['status'] == 'Done': color = "lightgreen"
            elif item['status'] == 'Error': color = "salmon"
            elif item['status'] == 'Processing...': color = "lightblue"
            
            lbl_status = ctk.CTkLabel(self.file_list_frame, text=item['status'], text_color=color)
            lbl_status.grid(row=row_idx, column=2, sticky="ew", padx=5, pady=2)
            item['ui_status_lbl'] = lbl_status
            
        self.file_list_frame._parent_canvas.yview_moveto(1.0)

    def clear_queue(self):
        if self.is_converting:
            messagebox.showwarning("Warning", "Cannot clear queue while converting.")
            return
        self.files_to_convert = []
        self.dest_dir = ""
        self.lbl_dest.configure(text="Default: <Source>/Converted")
        self.progress_bar.set(0)
        self.lbl_status.configure(text="Ready")
        self.lbl_eta.configure(text="")
        self.console_textbox.delete("0.0", "end")
        self.console_textbox.insert("0.0", "--- FFMPEG Log ---\n")
        self.refresh_file_list()

    def select_single_file(self):
        files = filedialog.askopenfilenames()
        if files:
            added = False
            for file in files:
                p = Path(file)
                if p.suffix.lower() in self.valid_exts:
                    self.files_to_convert.append({'path': p, 'status': 'Pending'})
                    added = True
            if added:
                self.set_default_dest_dir(files[0])
                self.progress_bar.set(0)
                self.lbl_status.configure(text="Ready")
                self.refresh_file_list()

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            added = False
            for f in Path(folder).iterdir():
                if f.is_file() and f.suffix.lower() in self.valid_exts:
                    self.files_to_convert.append({'path': f, 'status': 'Pending'})
                    added = True
            if added:
                self.set_default_dest_dir(folder)
                self.progress_bar.set(0)
                self.lbl_status.configure(text="Ready")
                self.refresh_file_list()

    def select_dest_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.dest_dir = folder
            self.lbl_dest.configure(text=self.dest_dir)

    def open_dest_folder(self):
        if self.dest_dir and Path(self.dest_dir).exists():
            if os.name == 'nt':
                os.startfile(self.dest_dir)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', self.dest_dir])
            else:
                subprocess.Popen(['xdg-open', self.dest_dir])
        else:
            messagebox.showinfo("Info", "Destination folder has not been created yet.")

    def on_drop(self, event):
        files = self.split_dnd_data(event.data)
        added = False
        for f in files:
            p = Path(f.strip('{}')) 
            if p.is_dir():
                for sub_f in p.iterdir():
                    if sub_f.is_file() and sub_f.suffix.lower() in self.valid_exts:
                        self.files_to_convert.append({'path': sub_f, 'status': 'Pending'})
                        added = True
            elif p.is_file() and p.suffix.lower() in self.valid_exts:
                self.files_to_convert.append({'path': p, 'status': 'Pending'})
                added = True
                
        if added:
            self.set_default_dest_dir(Path(files[0].strip('{}')))
            self.progress_bar.set(0)
            self.lbl_status.configure(text="Ready")
            self.refresh_file_list()

    def split_dnd_data(self, data):
        if not data: return []
        import shlex
        if '{' in data:
            matches = re.finditer(r'\{([^{}]+)\}|(\S+)', data)
            paths = []
            for m in matches:
                paths.append(m.group(1) or m.group(2))
            return paths
        else:
            return shlex.split(data)

    def log(self, message):
        self.console_textbox.insert("end", message + "\n")
        self.console_textbox.see("end")

    # --- Core Execution Logic ---
    def get_duration(self, file_path):
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        cmd = ["ffmpeg", "-i", str(file_path)]
        try:
            result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, startupinfo=startupinfo)
            match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})", result.stderr)
            if match:
                hours, minutes, seconds = match.groups()
                return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        except Exception:
            pass
        return 0

    def toggle_conversion(self):
        if self.is_converting:
            self.cancel_requested = True
            self.btn_convert.configure(text="Cancelling...", state="disabled")
            if self.process:
                self.process.terminate()
        else:
            mode = self.mode_tabs.get()
            if mode == "Audio to Video" and not self.static_image_path:
                messagebox.showwarning("Warning", "Please select a static image first for Audio to Video conversion.")
                return

            pending_files = [f for f in self.files_to_convert if f['status'] in ['Pending', 'Error', 'Cancelled']]
            if not pending_files:
                messagebox.showwarning("Warning", "No pending files to process.")
                return
            
            self.is_converting = True
            self.cancel_requested = False
            self.btn_convert.configure(text="Cancel / Stop", fg_color="#8B0000", hover_color="#600000")
            self.progress_bar.set(0)
            threading.Thread(target=self._conversion_thread, args=(pending_files, mode), daemon=True).start()

    def _build_ffmpeg_command_vc(self, input_file, output_file):
        cmd = ["ffmpeg"]
        if self.overwrite_var.get(): cmd.append("-y")
        else: cmd.append("-n")
        
        cmd.extend(["-i", str(input_file)])

        vc = self.vc_video_codec.get()
        ac = self.vc_audio_codec.get()
        hw = self.vc_hardware_encoder.get()
        res = self.vc_resolution.get()

        # Video
        if vc == "Copy (No re-encode)":
            cmd.extend(["-c:v", "copy"])
        else:
            is_nvenc = "NVENC" in hw
            is_qsv = "QSV" in hw
            is_amf = "AMF" in hw
            
            if "H.264" in vc: c_v = "h264_nvenc" if is_nvenc else "h264_qsv" if is_qsv else "h264_amf" if is_amf else "libx264"
            elif "H.265" in vc: c_v = "hevc_nvenc" if is_nvenc else "hevc_qsv" if is_qsv else "hevc_amf" if is_amf else "libx265"
            elif "AV1" in vc: c_v = "av1_nvenc" if is_nvenc else "av1_qsv" if is_qsv else "av1_amf" if is_amf else "libaom-av1"
            else: c_v = "libx264"
                
            cmd.extend(["-c:v", c_v])
            
            preset = self.vc_preset_combo.get()
            if preset and preset != "default": cmd.extend(["-preset", preset])
            
            res = self.vc_resolution.get()
            vf_args = []
            if res != "Keep Original":
                scaler_flag = "bicubic"
                if hasattr(self, 'advance_mode_var') and self.advance_mode_var.get():
                    scaler_flag = self.vc_scaler_filter.get().split()[0].lower()
                    
                if res == "Custom":
                    custom_res = self.vc_custom_res_entry.get().strip()
                    if custom_res: 
                        vf_args.append(f"scale={custom_res}:flags={scaler_flag}")
                else:
                    res_map = {"480p": "480", "720p": "720", "1080p": "1080", "2K": "1440", "4K": "2160"}
                    if res in res_map: 
                        vf_args.append(f"scale=-2:{res_map[res]}:flags={scaler_flag}")
                        
            if vf_args:
                cmd.extend(["-vf", ",".join(vf_args)])

            crf = int(self.vc_crf_slider.get())
            is_advanced = hasattr(self, 'advance_mode_var') and self.advance_mode_var.get()
            rc_mode = self.vc_rc_mode.get() if is_advanced else "CQ / CRF (Quality)"
            target_kbps = self.vc_vbr_target.get().strip() or "6000" if is_advanced else "6000"
            max_kbps = self.vc_vbr_max.get().strip() or "12000" if is_advanced else "12000"
            is_quality_mode = "CQ" in rc_mode or "CRF" in rc_mode
            limit_max = self.vc_limit_bitrate_var.get() if is_advanced else True

            if is_nvenc:
                if is_quality_mode:
                    cmd.extend(["-rc", "constqp", "-cq", str(crf), "-b:v", "0"])
                elif "VBR" in rc_mode:
                    cmd.extend(["-rc", "vbr", "-b:v", f"{target_kbps}k", "-maxrate", f"{max_kbps}k", "-bufsize", f"{max_kbps}k"])
                elif "CBR" in rc_mode:
                    cmd.extend(["-rc", "cbr", "-b:v", f"{target_kbps}k", "-maxrate", f"{target_kbps}k", "-bufsize", f"{target_kbps}k"])
                    
                if is_advanced:
                    if self.vc_nvenc_saq.get(): cmd.extend(["-spatial-aq", "1"])
                    if self.vc_nvenc_taq.get(): cmd.extend(["-temporal-aq", "1"])
                    if self.vc_nvenc_lookahead.get(): cmd.extend(["-rc-lookahead", "32"])
                    if self.vc_nvenc_wp.get(): cmd.extend(["-weighted_pred", "1", "-bf", "0"])
                else:
                    # In normal mode, we don't force weighted_pred because disabling B-frames (-bf 0) heavily reduces compression efficiency for general users.
                    # We only keep spatial-aq, temporal-aq, and rc-lookahead which are universally beneficial.
                    cmd.extend(["-spatial-aq", "1", "-temporal-aq", "1", "-rc-lookahead", "32"])

            elif is_qsv:
                if is_quality_mode:
                    cmd.extend(["-rc", "cqp", "-q", str(crf)])
                elif "VBR" in rc_mode:
                    cmd.extend(["-rc", "vbr", "-b:v", f"{target_kbps}k", "-maxrate", f"{max_kbps}k", "-bufsize", f"{max_kbps}k"])
                elif "CBR" in rc_mode:
                    cmd.extend(["-rc", "cbr", "-b:v", f"{target_kbps}k"])
                    
                if is_advanced:
                    if self.vc_qsv_lookahead.get(): cmd.extend(["-look_ahead", "1", "-look_ahead_depth", "32"])
                    if self.vc_qsv_adapt.get(): cmd.extend(["-adaptive_i", "1", "-adaptive_b", "1"])
                else:
                    cmd.extend(["-look_ahead", "1", "-look_ahead_depth", "32", "-adaptive_i", "1", "-adaptive_b", "1"])

            elif is_amf:
                if is_quality_mode:
                    cmd.extend(["-rc", "cqp", "-qp_i", str(crf), "-qp_p", str(crf)])
                elif "VBR" in rc_mode:
                    cmd.extend(["-rc", "vbr_latency", "-b:v", f"{target_kbps}k", "-maxrate", f"{max_kbps}k"])
                elif "CBR" in rc_mode:
                    cmd.extend(["-rc", "cbr", "-b:v", f"{target_kbps}k"])
                    
                if is_advanced:
                    if self.vc_amf_preanalysis.get(): cmd.extend(["-preanalysis", "1"])
                    if self.vc_amf_vbaq.get(): cmd.extend(["-vbaq", "1"])
                else:
                    cmd.extend(["-preanalysis", "1", "-vbaq", "1"])
                    
            else: # CPU
                if is_quality_mode:
                    cmd.extend(["-crf", str(crf)])
                elif "VBR" in rc_mode:
                    cmd.extend(["-b:v", f"{target_kbps}k", "-maxrate", f"{max_kbps}k", "-bufsize", f"{max_kbps}k"])
                elif "CBR" in rc_mode:
                    cmd.extend(["-b:v", f"{target_kbps}k", "-minrate", f"{target_kbps}k", "-maxrate", f"{target_kbps}k", "-bufsize", f"{target_kbps}k"])
                    
                if is_advanced:
                    if self.vc_cpu_aq.get(): cmd.extend(["-aq-mode", "3"])
                else:
                    cmd.extend(["-aq-mode", "3"])

            if is_quality_mode and limit_max:
                res = self.vc_resolution.get()
                if res == "480p": max_bitrate = "3000k"
                elif res == "720p": max_bitrate = "6000k"
                elif res == "1080p": max_bitrate = "12000k"
                elif res in ["2K", "4K"]: max_bitrate = "45000k"
                else: max_bitrate = "15000k"
                cmd.extend(["-maxrate", max_bitrate, "-bufsize", max_bitrate])

            fps = self.vc_fps_combo.get()
            if fps != "Keep Original": cmd.extend(["-r", fps])

            vf_args = []
            if res != "Keep Original":
                if res == "Custom":
                    custom_res = self.vc_custom_res_entry.get().strip()
                    if custom_res: vf_args.append(f"scale={custom_res}")
                else:
                    res_map = {"480p": "480", "720p": "720", "1080p": "1080", "2K": "1440", "4K": "2160"}
                    if res in res_map: vf_args.append(f"scale=-2:{res_map[res]}")
            if vf_args: cmd.extend(["-vf", ",".join(vf_args)])

        # Audio
        if ac == "Copy (No re-encode)": cmd.extend(["-c:a", "copy"])
        elif ac == "FLAC": cmd.extend(["-c:a", "flac"])
        else:
            ac_map = {"AAC": "aac", "MP3": "libmp3lame", "AC3": "ac3"}
            cmd.extend(["-c:a", ac_map.get(ac, "aac")])
            abit = self.vc_audio_bitrate.get()
            if abit: cmd.extend(["-b:a", abit])

        if self.vc_faststart_var.get() and self.vc_target_format.get() in [".mp4", ".mov"]:
            cmd.extend(["-movflags", "+faststart"])

        cmd.append(str(output_file))
        return cmd

    def _build_ffmpeg_command_ea(self, input_file, output_file):
        cmd = ["ffmpeg"]
        if self.overwrite_var.get(): cmd.append("-y")
        else: cmd.append("-n")
        
        cmd.extend(["-i", str(input_file), "-vn"]) # No video

        fmt = self.ea_target_format.get()
        if fmt == ".mp3":
            cmd.extend(["-c:a", "libmp3lame", "-b:a", self.ea_audio_bitrate.get()])
        elif fmt == ".aac":
            cmd.extend(["-c:a", "aac", "-b:a", self.ea_audio_bitrate.get()])
        elif fmt == ".flac":
            cmd.extend(["-c:a", "flac"])
        elif fmt == ".wav":
            cmd.extend(["-c:a", "pcm_s16le"])

        cmd.append(str(output_file))
        return cmd

    def _build_ffmpeg_command_a2v(self, input_file, output_file):
        cmd = ["ffmpeg"]
        if self.overwrite_var.get(): cmd.append("-y")
        else: cmd.append("-n")

        cmd.extend(["-loop", "1", "-i", str(self.static_image_path)])
        cmd.extend(["-i", str(input_file)])

        hw = self.a2v_hardware_encoder.get()
        is_nvenc = "NVENC" in hw
        is_qsv = "QSV" in hw
        is_amf = "AMF" in hw
        c_v = "h264_nvenc" if is_nvenc else "h264_qsv" if is_qsv else "h264_amf" if is_amf else "libx264"
        
        cmd.extend(["-c:v", c_v])
        
        preset = self.a2v_preset_combo.get()
        if preset and preset != "default": 
            cmd.extend(["-preset", preset])
        
        if not is_nvenc and not is_qsv and not is_amf:
            cmd.extend(["-tune", "stillimage"])
        elif is_nvenc:
            cmd.extend(["-tune", "hq"])

        cmd.extend(["-r", self.a2v_fps_combo.get()])
        
        res = self.a2v_resolution.get()
        vf_args = []
        if res != "Match Image Size":
            if res == "Custom":
                custom_res = self.a2v_custom_res_entry.get().strip()
                if custom_res:
                    vf_args.append(f"scale={custom_res}")
            else:
                res_map = {"480p": "480", "720p": "720", "1080p": "1080", "2K": "1440", "4K": "2160"}
                if res in res_map:
                    vf_args.append(f"scale=-2:{res_map[res]}")
                    
        if not vf_args:
            vf_args.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")
            
        cmd.extend(["-vf", ",".join(vf_args), "-pix_fmt", "yuv420p"])

        a_bit = self.a2v_audio_bitrate.get()
        if a_bit == "Copy Original":
            cmd.extend(["-c:a", "copy"])
        else:
            cmd.extend(["-c:a", "aac", "-b:a", a_bit])

        cmd.append("-shortest")
        cmd.append(str(output_file))
        return cmd

    def _conversion_thread(self, pending_files, mode):
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        total_files = len(pending_files)

        for i, item in enumerate(pending_files):
            if self.cancel_requested: break
            
            input_file = item['path']
            out_dir = Path(self.dest_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            
            # Determine target format based on mode
            if mode == "Video Converter": target_fmt = self.vc_target_format.get()
            elif mode == "Extract Audio": target_fmt = self.ea_target_format.get()
            else: target_fmt = self.a2v_target_format.get()

            suffix = "_converted" if self.suffix_var.get() else ""
            output_file = out_dir / f"{input_file.stem}{suffix}{target_fmt}"
            
            self.after(0, lambda idx=i, name=input_file.name: self.lbl_status.configure(text=f"Processing File {idx+1} of {total_files}: {name}"))
            
            item['status'] = 'Processing...'
            if 'ui_status_lbl' in item and item['ui_status_lbl'].winfo_exists():
                self.after(0, lambda lbl=item['ui_status_lbl']: lbl.configure(text='Processing...', text_color="lightblue"))
            
            duration = self.get_duration(input_file)
            
            if mode == "Video Converter": cmd = self._build_ffmpeg_command_vc(input_file, output_file)
            elif mode == "Extract Audio": cmd = self._build_ffmpeg_command_ea(input_file, output_file)
            else: cmd = self._build_ffmpeg_command_a2v(input_file, output_file)

            self.after(0, lambda msg="Command: " + " ".join(cmd): self.log(msg))

            self.process = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True, startupinfo=startupinfo)
            
            start_time_proc = time.time()
            last_eta_update = 0

            for line in self.process.stderr:
                if self.cancel_requested: break
                self.after(0, lambda l=line.strip(): self.log(l))
                
                if duration > 0:
                    time_match = re.search(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})", line)
                    if time_match:
                        hours, minutes, seconds = time_match.groups()
                        current_time = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                        progress = min(current_time / duration, 1.0)
                        self.after(0, self.progress_bar.set, progress)
                        
                        now = time.time()
                        if now - last_eta_update > 1:
                            elapsed = now - start_time_proc
                            if progress > 0:
                                total_est = elapsed / progress
                                eta = total_est - elapsed
                                fps_match = re.search(r"fps=\s*(\d+)", line)
                                fps_txt = f"{fps_match.group(1)} fps | " if fps_match else ""
                                eta_str = time.strftime('%H:%M:%S', time.gmtime(max(0, eta)))
                                self.after(0, lambda e=eta_str, f=fps_txt: self.lbl_eta.configure(text=f"{f}ETA: {e}"))
                                last_eta_update = now

            self.process.wait()
            
            if self.cancel_requested:
                item['status'] = 'Cancelled'
                if 'ui_status_lbl' in item and item['ui_status_lbl'].winfo_exists():
                    self.after(0, lambda lbl=item['ui_status_lbl']: lbl.configure(text='Cancelled', text_color="gray"))
                self.after(0, lambda name=input_file.name: self.log(f"--- Cancelled {name} ---"))
            elif self.process.returncode == 0:
                item['status'] = 'Done'
                self.after(0, self.progress_bar.set, 1.0)
                if 'ui_status_lbl' in item and item['ui_status_lbl'].winfo_exists():
                    self.after(0, lambda lbl=item['ui_status_lbl']: lbl.configure(text='Done', text_color="lightgreen"))
                self.after(0, lambda name=input_file.name: self.log(f"--- Finished {name} ---"))
            else:
                item['status'] = 'Error'
                if 'ui_status_lbl' in item and item['ui_status_lbl'].winfo_exists():
                    self.after(0, lambda lbl=item['ui_status_lbl']: lbl.configure(text='Error', text_color="salmon"))
                self.after(0, lambda name=input_file.name: self.log(f"--- Failed {name} ---"))

        self.is_converting = False
        self.process = None
        self.after(0, lambda: self.btn_convert.configure(text="Convert", fg_color=["#3a7ebf", "#1f538d"], hover_color=["#325882", "#14375e"], state="normal"))
        
        if self.cancel_requested:
            self.after(0, lambda: self.lbl_status.configure(text="Operation cancelled."))
        else:
            self.after(0, lambda: self.lbl_status.configure(text="All files processed!"))
        
        self.after(0, lambda: self.lbl_eta.configure(text=""))
        self.after(0, lambda: messagebox.showinfo("Finished", "Batch process completed!" if not self.cancel_requested else "Process cancelled!"))

if __name__ == "__main__":
    app = FFmpegGUI()
    app.mainloop()
