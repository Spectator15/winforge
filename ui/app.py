import customtkinter as ctk
import threading
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.operations import (
    create_restore_point,
    run_dism, run_sfc, run_chkdsk, run_full_repair,
    clean_temp_files, clean_windows_update_cache, clean_prefetch,
    run_disk_cleanup, flush_dns, reset_network,
    install_dotnet, install_vcredist, install_directx, install_webview2,
    TWEAK_FUNCTIONS, PRESETS
)

# ─── COLOURS ──────────────────────────────────────────────────────────────────
BG_DARK     = "#0d0d0f"
BG_PANEL    = "#131316"
BG_CARD     = "#1a1a1f"
BG_HOVER    = "#222228"
ACCENT      = "#4f8ef7"
ACCENT_DIM  = "#2a4a8a"
SUCCESS     = "#3ecf6e"
WARNING     = "#f5a623"
DANGER      = "#e84040"
TEXT_PRI    = "#f0f0f5"
TEXT_SEC    = "#8888a0"
TEXT_DIM    = "#555568"
BORDER      = "#2a2a35"

TWEAK_LABELS = {
    "disable_telemetry":      "Disable Telemetry",
    "disable_cortana":        "Disable Cortana",
    "disable_xbox_gamebar":   "Disable Xbox Game Bar",
    "set_high_performance":   "High Performance Power Plan",
    "disable_search_indexing":"Disable Search Indexing",
    "disable_superfetch":     "Disable SysMain (Superfetch)",
    "show_file_extensions":   "Show File Extensions",
    "show_hidden_files":      "Show Hidden Files",
    "disable_tips":           "Disable Tips & Suggestions",
    "classic_context_menu":   "Classic Right-Click Menu (Win11)",
    "disable_onedrive":       "Disable OneDrive",
    "enable_dark_mode":       "Enable Windows Dark Mode",
    "disable_startup_delay":  "Remove Startup Delay",
}


class WinForgeApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("WinForge")
        self.geometry("1100x720")
        self.minsize(900, 620)
        self.configure(fg_color=BG_DARK)

        self._current_tab = None
        self._tweak_vars = {}
        self._running = False

        self._build_layout()
        self._show_tab("repair")

    # ─── LAYOUT ───────────────────────────────────────────────────────────────

    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_area()

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, fg_color=BG_PANEL, width=200, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(10, weight=1)

        # Logo area
        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=20, pady=(24, 8), sticky="ew")

        ctk.CTkLabel(
            logo_frame, text="⚙ WinForge",
            font=ctk.CTkFont(family="Consolas", size=20, weight="bold"),
            text_color=ACCENT
        ).pack(anchor="w")

        ctk.CTkLabel(
            logo_frame, text="Windows Toolkit",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT_DIM
        ).pack(anchor="w")

        # Divider
        ctk.CTkFrame(sidebar, fg_color=BORDER, height=1).grid(
            row=1, column=0, sticky="ew", padx=16, pady=(8, 16)
        )

        # Nav buttons
        nav_items = [
            ("repair",       "🔧  System Repair"),
            ("cleanup",      "🧹  Cleanup"),
            ("dependencies", "📦  Dependencies"),
            ("tweaks",       "⚡  Tweaks"),
            ("restore",      "🛡  Restore Point"),
        ]

        self._nav_buttons = {}
        for i, (tab_id, label) in enumerate(nav_items, start=2):
            btn = ctk.CTkButton(
                sidebar, text=label, anchor="w",
                font=ctk.CTkFont(family="Consolas", size=13),
                fg_color="transparent",
                hover_color=BG_HOVER,
                text_color=TEXT_SEC,
                corner_radius=8,
                height=40,
                command=lambda t=tab_id: self._show_tab(t)
            )
            btn.grid(row=i, column=0, padx=10, pady=2, sticky="ew")
            self._nav_buttons[tab_id] = btn

        # Version label at bottom
        ctk.CTkLabel(
            sidebar, text="v1.0.0  |  admin mode",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=TEXT_DIM
        ).grid(row=11, column=0, padx=20, pady=16, sticky="sw")

    def _build_main_area(self):
        self._main = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0)
        self._main.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self._main.grid_columnconfigure(0, weight=1)
        self._main.grid_rowconfigure(1, weight=1)

        # Output log at bottom
        self._build_log()

    def _build_log(self):
        log_frame = ctk.CTkFrame(self._main, fg_color=BG_PANEL, corner_radius=10)
        log_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))
        log_frame.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(log_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 0))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header, text="Output Log",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=TEXT_SEC
        ).grid(row=0, column=0, sticky="w")

        clear_btn = ctk.CTkButton(
            header, text="Clear", width=60, height=22,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=BG_CARD, hover_color=BG_HOVER,
            text_color=TEXT_SEC, corner_radius=6,
            command=self._clear_log
        )
        clear_btn.grid(row=0, column=2, sticky="e")

        self._log_box = ctk.CTkTextbox(
            log_frame, height=140,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=BG_DARK,
            text_color=TEXT_PRI,
            corner_radius=8,
            wrap="word",
            state="disabled"
        )
        self._log_box.grid(row=1, column=0, sticky="ew", padx=8, pady=8)

    # ─── TAB SWITCHING ────────────────────────────────────────────────────────

    def _show_tab(self, tab_id):
        if self._current_tab:
            self._current_tab.destroy()

        for tid, btn in self._nav_buttons.items():
            if tid == tab_id:
                btn.configure(fg_color=ACCENT_DIM, text_color=TEXT_PRI)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_SEC)

        frame = ctk.CTkScrollableFrame(
            self._main, fg_color="transparent", corner_radius=0
        )
        frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(8, 8))
        frame.grid_columnconfigure(0, weight=1)

        self._current_tab = frame

        builders = {
            "repair":       self._build_repair_tab,
            "cleanup":      self._build_cleanup_tab,
            "dependencies": self._build_deps_tab,
            "tweaks":       self._build_tweaks_tab,
            "restore":      self._build_restore_tab,
        }
        builders[tab_id](frame)

    # ─── SHARED WIDGETS ───────────────────────────────────────────────────────

    def _section_header(self, parent, title, subtitle="", row=0):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=row, column=0, sticky="ew", pady=(4, 10))

        ctk.CTkLabel(
            f, text=title,
            font=ctk.CTkFont(family="Consolas", size=18, weight="bold"),
            text_color=TEXT_PRI
        ).pack(anchor="w")

        if subtitle:
            ctk.CTkLabel(
                f, text=subtitle,
                font=ctk.CTkFont(family="Consolas", size=12),
                text_color=TEXT_SEC
            ).pack(anchor="w")

    def _card(self, parent, row, col=0, colspan=1, padx=(0, 0), pady=(0, 8)):
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10,
                            border_width=1, border_color=BORDER)
        card.grid(row=row, column=col, columnspan=colspan,
                  sticky="ew", padx=padx, pady=pady)
        card.grid_columnconfigure(0, weight=1)
        return card

    def _action_button(self, parent, text, command, color=ACCENT, row=0, col=0, width=160):
        return ctk.CTkButton(
            parent, text=text, command=command,
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            fg_color=color, hover_color=self._darken(color),
            text_color="#ffffff", corner_radius=8,
            height=36, width=width
        ).grid(row=row, column=col, padx=8, pady=8, sticky="w")

    def _darken(self, hex_color):
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        factor = 0.75
        return "#{:02x}{:02x}{:02x}".format(int(r*factor), int(g*factor), int(b*factor))

    def _card_label(self, card, title, desc):
        ctk.CTkLabel(
            card, text=title,
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            text_color=TEXT_PRI, anchor="w"
        ).grid(row=0, column=0, padx=14, pady=(12, 0), sticky="w")
        ctk.CTkLabel(
            card, text=desc,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT_SEC, anchor="w", wraplength=500
        ).grid(row=1, column=0, padx=14, pady=(2, 0), sticky="w")

    # ─── REPAIR TAB ───────────────────────────────────────────────────────────

    def _build_repair_tab(self, parent):
        self._section_header(parent, "System Repair",
                             "Fix corrupted Windows files and system components.", row=0)

        items = [
            ("DISM RestoreHealth",
             "Repairs the Windows component store. Run this first if Windows is acting up. Takes 5-15 min.",
             lambda: self._run_op(run_dism), ACCENT),

            ("System File Checker (SFC)",
             "Scans and repairs corrupted Windows system files. Run after DISM.",
             lambda: self._run_op(run_sfc), ACCENT),

            ("Check Disk (CHKDSK)",
             "Schedules a disk integrity scan on next boot. Will prompt you to restart.",
             lambda: self._run_op(run_chkdsk), WARNING),

            ("Full Repair (DISM + SFC)",
             "Creates a restore point, then runs DISM followed by SFC automatically.",
             lambda: self._run_op(run_full_repair), SUCCESS),
        ]

        for i, (title, desc, cmd, col) in enumerate(items, start=1):
            card = self._card(parent, row=i, pady=(0, 10))
            card.grid_columnconfigure(0, weight=1)
            self._card_label(card, title, desc)
            ctk.CTkButton(
                card, text="Run",
                font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
                fg_color=col, hover_color=self._darken(col),
                text_color="#fff", corner_radius=8, height=34, width=100,
                command=cmd
            ).grid(row=2, column=0, padx=14, pady=10, sticky="w")

    # ─── CLEANUP TAB ──────────────────────────────────────────────────────────

    def _build_cleanup_tab(self, parent):
        self._section_header(parent, "System Cleanup",
                             "Free up disk space and clear cached junk.", row=0)

        items = [
            ("Temp Files",
             "Deletes everything in %TEMP% and C:\\Windows\\Temp.",
             lambda: self._run_op(clean_temp_files)),

            ("Windows Update Cache",
             "Clears the Software Distribution download folder. Safe to delete after updates install.",
             lambda: self._run_op(clean_windows_update_cache)),

            ("Prefetch Files",
             "Clears prefetch cache. Windows will rebuild it automatically.",
             lambda: self._run_op(clean_prefetch)),

            ("Windows Disk Cleanup",
             "Runs the built-in Windows Disk Cleanup tool silently with all categories selected.",
             lambda: self._run_op(run_disk_cleanup)),

            ("Flush DNS Cache",
             "Clears your DNS resolver cache. Useful if websites aren't loading correctly.",
             lambda: self._run_op(flush_dns)),

            ("Reset Network Stack",
             "Resets Winsock, TCP/IP, and flushes DNS. Good for persistent network issues. Needs restart.",
             lambda: self._run_op(reset_network), WARNING),
        ]

        for i, item in enumerate(items, start=1):
            title, desc, cmd = item[0], item[1], item[2]
            col = item[3] if len(item) > 3 else ACCENT
            card = self._card(parent, row=i, pady=(0, 10))
            card.grid_columnconfigure(0, weight=1)
            self._card_label(card, title, desc)
            ctk.CTkButton(
                card, text="Run",
                font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
                fg_color=col, hover_color=self._darken(col),
                text_color="#fff", corner_radius=8, height=34, width=100,
                command=cmd
            ).grid(row=2, column=0, padx=14, pady=10, sticky="w")

    # ─── DEPENDENCIES TAB ─────────────────────────────────────────────────────

    def _build_deps_tab(self, parent):
        self._section_header(parent, "Dependencies",
                             "Install common Windows runtimes and frameworks via winget.", row=0)

        items = [
            (".NET Runtime 6",    lambda: self._run_op(lambda cb: install_dotnet("6", cb))),
            (".NET Runtime 7",    lambda: self._run_op(lambda cb: install_dotnet("7", cb))),
            (".NET Runtime 8",    lambda: self._run_op(lambda cb: install_dotnet("8", cb))),
            (".NET Runtime 9",    lambda: self._run_op(lambda cb: install_dotnet("9", cb))),
            ("Visual C++ Redists 2015-2022 (x64 + x86)", lambda: self._run_op(install_vcredist)),
            ("DirectX",           lambda: self._run_op(install_directx)),
            ("WebView2 Runtime",  lambda: self._run_op(install_webview2)),
        ]

        descs = {
            ".NET Runtime 6":    "Required by many modern apps and games.",
            ".NET Runtime 7":    "Required by some newer apps.",
            ".NET Runtime 8":    "Latest LTS version. Install this if unsure.",
            ".NET Runtime 9":    "Cutting edge. Only if a specific app needs it.",
            "Visual C++ Redists 2015-2022 (x64 + x86)": "The most common fix for DLL errors in games and apps.",
            "DirectX":           "Core graphics API. Usually already installed but this ensures it's up to date.",
            "WebView2 Runtime":  "Required by many modern apps that embed web content.",
        }

        for i, (title, cmd) in enumerate(items, start=1):
            card = self._card(parent, row=i, pady=(0, 10))
            card.grid_columnconfigure(0, weight=1)
            self._card_label(card, title, descs.get(title, ""))
            ctk.CTkButton(
                card, text="Install",
                font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
                fg_color=ACCENT, hover_color=self._darken(ACCENT),
                text_color="#fff", corner_radius=8, height=34, width=100,
                command=cmd
            ).grid(row=2, column=0, padx=14, pady=10, sticky="w")

    # ─── TWEAKS TAB ───────────────────────────────────────────────────────────

    def _build_tweaks_tab(self, parent):
        self._section_header(parent, "Tweaks",
                             "Pick tweaks individually or load a preset, then apply.", row=0)

        # Presets row
        preset_frame = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10,
                                    border_width=1, border_color=BORDER)
        preset_frame.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        preset_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            preset_frame, text="Presets",
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            text_color=TEXT_PRI
        ).grid(row=0, column=0, padx=14, pady=(12, 4), sticky="w")

        ctk.CTkLabel(
            preset_frame, text="Loads recommended tweaks for a use case. You can still adjust before applying.",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT_SEC
        ).grid(row=1, column=0, padx=14, pady=(0, 8), sticky="w")

        btn_row = ctk.CTkFrame(preset_frame, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=14, pady=(0, 12), sticky="w")

        colors = [ACCENT, SUCCESS, WARNING, "#9b59b6"]
        for i, (preset_name, _) in enumerate(PRESETS.items()):
            col = colors[i % len(colors)]
            ctk.CTkButton(
                btn_row, text=preset_name,
                font=ctk.CTkFont(family="Consolas", size=12),
                fg_color=col, hover_color=self._darken(col),
                text_color="#fff", corner_radius=8, height=32,
                command=lambda p=preset_name: self._apply_preset(p)
            ).grid(row=0, column=i, padx=(0, 8))

        # Individual tweaks
        tweak_frame = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=10,
                                   border_width=1, border_color=BORDER)
        tweak_frame.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        tweak_frame.grid_columnconfigure(0, weight=1)
        tweak_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            tweak_frame, text="Individual Tweaks",
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            text_color=TEXT_PRI
        ).grid(row=0, column=0, columnspan=2, padx=14, pady=(12, 8), sticky="w")

        self._tweak_vars = {}
        tweak_ids = list(TWEAK_LABELS.keys())
        for idx, tweak_id in enumerate(tweak_ids):
            col = idx % 2
            row = (idx // 2) + 1
            var = ctk.BooleanVar(value=False)
            self._tweak_vars[tweak_id] = var
            ctk.CTkCheckBox(
                tweak_frame,
                text=TWEAK_LABELS[tweak_id],
                variable=var,
                font=ctk.CTkFont(family="Consolas", size=12),
                text_color=TEXT_PRI,
                fg_color=ACCENT,
                hover_color=ACCENT_DIM,
                checkmark_color="#fff",
                border_color=BORDER
            ).grid(row=row, column=col, padx=14, pady=5, sticky="w")

        # Apply/Clear buttons
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkButton(
            btn_frame, text="Apply Selected Tweaks",
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            fg_color=SUCCESS, hover_color=self._darken(SUCCESS),
            text_color="#fff", corner_radius=8, height=40, width=220,
            command=self._apply_tweaks
        ).grid(row=0, column=0, padx=(0, 10))

        ctk.CTkButton(
            btn_frame, text="Clear All",
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color=BG_CARD, hover_color=BG_HOVER,
            text_color=TEXT_SEC, corner_radius=8, height=40, width=100,
            command=self._clear_tweaks
        ).grid(row=0, column=1)

    def _apply_preset(self, preset_name):
        preset = PRESETS.get(preset_name, {})
        selected = preset.get("tweaks", [])
        for tweak_id, var in self._tweak_vars.items():
            var.set(tweak_id in selected)
        self._log(f"Preset '{preset_name}' loaded. Review and click Apply.")

    def _clear_tweaks(self):
        for var in self._tweak_vars.values():
            var.set(False)

    def _apply_tweaks(self):
        selected = [tid for tid, var in self._tweak_vars.items() if var.get()]
        if not selected:
            self._log("No tweaks selected.")
            return

        def run():
            self._log(f"Creating restore point before applying {len(selected)} tweak(s)...")
            create_restore_point("WinForge Tweaks", self._log)
            for tid in selected:
                fn = TWEAK_FUNCTIONS.get(tid)
                if fn:
                    fn(self._log)
            self._log("All selected tweaks applied.")

        threading.Thread(target=run, daemon=True).start()

    # ─── RESTORE POINT TAB ────────────────────────────────────────────────────

    def _build_restore_tab(self, parent):
        self._section_header(parent, "Restore Point",
                             "Manually create a Windows restore point before making changes.", row=0)

        card = self._card(parent, row=1)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card, text="Create Restore Point",
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            text_color=TEXT_PRI
        ).grid(row=0, column=0, padx=14, pady=(12, 4), sticky="w")

        ctk.CTkLabel(
            card,
            text="Creates a Windows System Restore point right now. Windows limits this to once per 24 hours\n"
                 "by default, but WinForge can bypass this. Recommended before applying tweaks or repairs.",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT_SEC, anchor="w", justify="left"
        ).grid(row=1, column=0, padx=14, pady=(0, 8), sticky="w")

        label_frame = ctk.CTkFrame(card, fg_color="transparent")
        label_frame.grid(row=2, column=0, padx=14, pady=(0, 4), sticky="w")

        ctk.CTkLabel(
            label_frame, text="Description:",
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color=TEXT_SEC
        ).grid(row=0, column=0, padx=(0, 8))

        self._rp_entry = ctk.CTkEntry(
            label_frame, width=300,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=BG_DARK, border_color=BORDER,
            text_color=TEXT_PRI,
            placeholder_text="WinForge Manual Restore Point"
        )
        self._rp_entry.grid(row=0, column=1)

        ctk.CTkButton(
            card, text="Create Now",
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            fg_color=SUCCESS, hover_color=self._darken(SUCCESS),
            text_color="#fff", corner_radius=8, height=36, width=140,
            command=self._create_rp
        ).grid(row=3, column=0, padx=14, pady=12, sticky="w")

        # Info card
        info = self._card(parent, row=2, pady=(8, 8))
        ctk.CTkLabel(
            info,
            text="ℹ  A restore point lets you roll Windows back to how it was right now.\n"
                 "   It does NOT affect your personal files, only system settings and registry.",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT_SEC, anchor="w", justify="left"
        ).grid(row=0, column=0, padx=14, pady=12, sticky="w")

    def _create_rp(self):
        desc = self._rp_entry.get().strip() or "WinForge Manual Restore Point"
        threading.Thread(
            target=lambda: self._run_op(lambda cb: create_restore_point(desc, cb)),
            daemon=True
        ).start()

    # ─── LOG ──────────────────────────────────────────────────────────────────

    def _log(self, message):
        def _write():
            self._log_box.configure(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self._log_box.insert("end", f"[{ts}] {message}\n")
            self._log_box.see("end")
            self._log_box.configure(state="disabled")
        self.after(0, _write)

    def _clear_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    def _run_op(self, fn):
        def run():
            try:
                fn(self._log)
            except Exception as e:
                self._log(f"Error: {e}")
        threading.Thread(target=run, daemon=True).start()
