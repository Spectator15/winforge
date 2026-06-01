"""
WinForge — Windows Toolkit by Danish
v5: Fixed toast notifications, GPU VRAM (correct GUID), WinUtil-verified telemetry (12 keys)
"""
import customtkinter as ctk
import threading, sys, os
from datetime import datetime
from core.operations import *

# ─── Theme ────────────────────────────────────────────────────────
BG     = "#0f1117"
PANEL  = "#161b22"
CARD   = "#1c2330"
CARD2  = "#21293a"
BORDER = "#30363d"
HOVER  = "#2d3748"

TEXT   = "#e6edf3"
TEXT2  = "#8b949e"
TEXT3  = "#6e7681"

ACCENT  = "#58a6ff"
SUCCESS = "#3fb950"
WARN    = "#d29922"
DANGER  = "#f85149"
PURPLE  = "#bc8cff"

FONT = "Segoe UI"
MONO = "Consolas"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ─── Re-launch as admin if needed ────────────────────────────────
def relaunch_as_admin():
    if sys.platform != "win32":
        return
    try:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            ctypes.windll.shell32.ShellExecuteW(None,"runas",sys.executable," ".join(sys.argv),None,1)
            sys.exit()
    except:
        pass

relaunch_as_admin()


class WinForge(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WinForge — Windows Toolkit by Danish")
        self.geometry("1100x750")
        self.minsize(900, 600)
        self.configure(fg_color=BG)

        self._restore_point_this_session = False
        self._toasts: list = []
        self._log_visible = True

        self._build_layout()
        self._build_nav()
        self._build_log()
        self._build_toast_area()
        self._show_tab("System Info")

    # ─── Layout skeleton ─────────────────────────────────────────
    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self._sidebar = ctk.CTkFrame(self, width=190, fg_color=PANEL, corner_radius=0)
        self._sidebar.grid(row=0, column=0, rowspan=2, sticky="nsw")
        self._sidebar.grid_propagate(False)
        self._sidebar.grid_rowconfigure(20, weight=1)

        # Main area
        self._main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._main.grid(row=0, column=1, sticky="nsew")
        self._main.grid_columnconfigure(0, weight=1)
        self._main.grid_rowconfigure(1, weight=1)

    def _build_nav(self):
        ctk.CTkLabel(self._sidebar, text="WinForge",
            font=ctk.CTkFont(family=FONT, size=20, weight="bold"),
            text_color=ACCENT).grid(row=0, column=0, padx=16, pady=(18,2), sticky="w")
        ctk.CTkLabel(self._sidebar, text="by Danish",
            font=ctk.CTkFont(family=FONT, size=11), text_color=TEXT3
            ).grid(row=1, column=0, padx=16, pady=(0,14), sticky="w")

        self._nav_btns = {}
        tabs = [
            ("System Info",   "💻"),
            ("Repair",        "🔧"),
            ("Cleanup",       "🧹"),
            ("Dependencies",  "📦"),
            ("Install Apps",  "⬇️"),
            ("Tweaks & Debloat","⚙️"),
            ("DNS Settings",  "🌐"),
            ("Win Updates",   "🔄"),
            ("Registry Health","🗂️"),
            ("System Tools",  "🛠️"),
            ("Restore Points","💾"),
        ]
        for i, (name, icon) in enumerate(tabs):
            btn = ctk.CTkButton(self._sidebar, text=f"  {icon}  {name}",
                font=ctk.CTkFont(family=FONT, size=12), anchor="w",
                fg_color="transparent", hover_color=HOVER, text_color=TEXT2,
                corner_radius=6, height=36,
                command=lambda n=name: self._show_tab(n))
            btn.grid(row=i+2, column=0, padx=8, pady=2, sticky="ew")
            self._nav_btns[name] = btn

    def _build_log(self):
        self._log_frame = ctk.CTkFrame(self._main, fg_color=PANEL, corner_radius=8)
        self._log_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))
        self._log_frame.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(self._log_frame, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 0))
        hdr.grid_columnconfigure(1, weight=1)

        self._log_toggle_btn = ctk.CTkButton(hdr, text="▼  Output Log", width=120, height=22,
            font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
            fg_color="transparent", hover_color=HOVER, text_color=TEXT2,
            corner_radius=5, anchor="w", command=self._toggle_log)
        self._log_toggle_btn.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(hdr, text="Clear", width=50, height=20,
            font=ctk.CTkFont(family=FONT, size=10),
            fg_color=CARD, hover_color=HOVER, text_color=TEXT3,
            corner_radius=5, command=self._clear_log
            ).grid(row=0, column=2, sticky="e")

        self._logbox_container = ctk.CTkFrame(self._log_frame, fg_color="transparent")
        self._logbox_container.grid(row=1, column=0, sticky="ew")
        self._logbox_container.grid_columnconfigure(0, weight=1)

        self._logbox = ctk.CTkTextbox(self._logbox_container, height=120,
            font=ctk.CTkFont(family=MONO, size=11), fg_color=BG, text_color=TEXT,
            corner_radius=6, wrap="word", state="disabled")
        self._logbox.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        self._logbox.tag_config("ok",   foreground=SUCCESS)
        self._logbox.tag_config("warn", foreground=WARN)
        self._logbox.tag_config("err",  foreground=DANGER)
        self._logbox.tag_config("info", foreground=ACCENT)

    def _toggle_log(self):
        self._log_visible = not self._log_visible
        if self._log_visible:
            self._logbox_container.grid()
            self._log_toggle_btn.configure(text="▼  Output Log")
        else:
            self._logbox_container.grid_remove()
            self._log_toggle_btn.configure(text="▶  Output Log")

    def _build_toast_area(self):
        # Overlay frame anchored to bottom-right of main area
        self._toast_overlay = ctk.CTkFrame(self._main, fg_color="transparent", width=340)
        self._toast_overlay.grid(row=0, column=0, rowspan=3, sticky="se", padx=16, pady=16)
        self._toast_overlay.grid_propagate(False)
        self._toast_overlay.lift()

    def _log_line(self, msg: str):
        def _write():
            self._logbox.configure(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            m = msg.lower()
            tag = (
                "ok"   if any(x in m for x in ["[ok]", "success", "complete", "cleaned", "created", "enabled", "disabled", "removed", "set to", "applied", "install"]) else
                "warn" if "[warn]" in m else
                "err"  if any(x in m for x in ["[error]", "fail", "cannot", "exception"]) else
                "info" if "[info]" in m else None
            )
            self._logbox.insert("end", f"[{ts}] {msg}\n", tag or ())
            self._logbox.see("end")
            self._logbox.configure(state="disabled")

            # Toast on completion
            if any(x in m for x in ["[ok]", "complete", "success"]):
                self._show_toast(msg, "ok")
            elif "[warn]" in m:
                self._show_toast(msg, "warn")
            elif any(x in m for x in ["[error]", "fail"]):
                self._show_toast(msg, "err")

        self.after(0, _write)

    def _clear_log(self):
        self._logbox.configure(state="normal")
        self._logbox.delete("1.0", "end")
        self._logbox.configure(state="disabled")

    # ─── Toast notifications ─────────────────────────────────────
    def _show_toast(self, message: str, kind: str = "ok"):
        # Strip log prefix for display
        clean = message
        for prefix in ["[OK] ", "[WARN] ", "[ERROR] ", "[INFO] "]:
            clean = clean.replace(prefix, "")
        clean = clean[:80] + ("..." if len(clean) > 80 else "")

        color = SUCCESS if kind == "ok" else WARN if kind == "warn" else DANGER

        # Toast container
        toast = ctk.CTkFrame(self._toast_overlay, fg_color=CARD2, corner_radius=8,
                             border_width=1, border_color=color)
        toast.pack(side="bottom", anchor="e", pady=3, fill="x")
        toast.grid_columnconfigure(1, weight=1)

        # Colored accent bar
        bar = ctk.CTkFrame(toast, fg_color=color, width=4, corner_radius=2)
        bar.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(0, 0), pady=0)

        # Icon
        icon = "✓" if kind == "ok" else "⚠" if kind == "warn" else "✗"
        ctk.CTkLabel(toast, text=icon, font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                     text_color=color, width=22).grid(row=0, column=1, padx=(8, 0), pady=(8, 0), sticky="nw")

        # Title
        title = "Done" if kind == "ok" else "Warning" if kind == "warn" else "Error"
        ctk.CTkLabel(toast, text=title, font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                     text_color=TEXT).grid(row=0, column=2, padx=(4, 40), pady=(8, 0), sticky="w")

        # Message
        ctk.CTkLabel(toast, text=clean, font=ctk.CTkFont(family=FONT, size=10),
                     text_color=TEXT2, wraplength=260, justify="left"
                     ).grid(row=1, column=1, columnspan=2, padx=(8, 40), pady=(0, 8), sticky="w")

        # Close button
        ctk.CTkButton(toast, text="✕", width=22, height=22,
            font=ctk.CTkFont(family=FONT, size=10),
            fg_color="transparent", hover_color=HOVER, text_color=TEXT3,
            corner_radius=4, command=lambda t=toast: self._dismiss_toast(t)
            ).grid(row=0, column=3, padx=(0, 6), pady=(6, 0), sticky="ne")

        self._toasts.append(toast)
        self.after(5000, lambda t=toast: self._dismiss_toast(t))

    def _dismiss_toast(self, toast):
        try:
            toast.destroy()
            if toast in self._toasts:
                self._toasts.remove(toast)
        except:
            pass

    # ─── Tab routing ─────────────────────────────────────────────
    def _show_tab(self, name: str):
        # Clear header and content
        for w in self._main.winfo_children():
            info = w.grid_info()
            if info.get("row") in ("0", "1", 0, 1):
                w.destroy()

        # Highlight nav button
        for n, b in self._nav_btns.items():
            b.configure(
                fg_color=HOVER if n == name else "transparent",
                text_color=TEXT if n == name else TEXT2
            )

        # Page header
        hdr = ctk.CTkFrame(self._main, fg_color=PANEL, corner_radius=8)
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        ctk.CTkLabel(hdr, text=name,
            font=ctk.CTkFont(family=FONT, size=16, weight="bold"),
            text_color=TEXT).pack(side="left", padx=14, pady=10)

        # Scrollable content area
        scroll = ctk.CTkScrollableFrame(self._main, fg_color=BG, scrollbar_button_color=CARD,
                                        scrollbar_button_hover_color=HOVER)
        scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=4)
        scroll.grid_columnconfigure(0, weight=1)

        builders = {
            "System Info":       self._tab_sysinfo,
            "Repair":            self._tab_repair,
            "Cleanup":           self._tab_cleanup,
            "Dependencies":      self._tab_deps,
            "Install Apps":      self._tab_install,
            "Tweaks & Debloat":  self._tab_tweaks,
            "DNS Settings":      self._tab_dns,
            "Win Updates":       self._tab_updates,
            "Registry Health":   self._tab_registry,
            "System Tools":      self._tab_systools,
            "Restore Points":    self._tab_restore,
        }
        if name in builders:
            builders[name](scroll)

    # ─── Helpers ─────────────────────────────────────────────────
    def _card(self, parent, row: int, col: int = 0, colspan: int = 1, title: str = ""):
        f = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=8)
        f.grid(row=row, column=col, columnspan=colspan, sticky="ew", padx=6, pady=5)
        f.grid_columnconfigure(0, weight=1)
        if title:
            ctk.CTkLabel(f, text=title,
                font=ctk.CTkFont(family=FONT, size=13, weight="bold"), text_color=TEXT
                ).grid(row=0, column=0, padx=14, pady=(10, 4), sticky="w")
        return f

    def _btn(self, parent, text, command, color=ACCENT, row=0, col=0, pady=10, padx=14):
        ctk.CTkButton(parent, text=text,
            font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
            fg_color=color, hover_color=self._dk(color),
            text_color="#fff", corner_radius=8, height=34, width=140,
            command=command
        ).grid(row=row, column=col, padx=padx, pady=pady, sticky="w")

    def _dk(self, hex_color: str) -> str:
        """Darken a hex color by ~15%"""
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        return "#{:02x}{:02x}{:02x}".format(max(0,r-38), max(0,g-38), max(0,b-38))

    def _run(self, fn, *args):
        threading.Thread(target=fn, args=args, daemon=True).start()

    def _lbl(self, parent, text, row, col=0, size=11, color=None, bold=False, pady=(2,2), padx=14):
        ctk.CTkLabel(parent, text=text,
            font=ctk.CTkFont(family=FONT, size=size, weight="bold" if bold else "normal"),
            text_color=color or TEXT2, justify="left", wraplength=680
        ).grid(row=row, column=col, padx=padx, pady=pady, sticky="w")

    # ─────────────────────────────────────────────────────────────
    # TAB: System Info
    # ─────────────────────────────────────────────────────────────
    def _tab_sysinfo(self, p):
        p.grid_columnconfigure(0, weight=1)
        card = self._card(p, 0, title="Loading system information...")

        self._sysinfo_card = card
        self._sysinfo_rows = []
        self._run(self._load_sysinfo, card)

    def _load_sysinfo(self, card):
        info = get_system_info(self._log_line)
        self.after(0, lambda: self._render_sysinfo(card, info))

    def _render_sysinfo(self, card, info):
        # Clear loading label
        for w in card.winfo_children():
            w.destroy()

        ctk.CTkLabel(card, text="System Information",
            font=ctk.CTkFont(family=FONT, size=13, weight="bold"), text_color=TEXT
        ).grid(row=0, column=0, columnspan=2, padx=14, pady=(10,6), sticky="w")

        sections = [
            ("🖥️  Operating System", [
                ("Name",          info.get("os_name","N/A")),
                ("Version",       f"{info.get('os_version','N/A')} (Build {info.get('os_build','N/A')})"),
                ("Architecture",  info.get("os_arch","N/A")),
                ("Installed",     info.get("os_install","N/A")),
                ("Uptime",        info.get("uptime","N/A")),
            ]),
            ("⚙️  Processor", [
                ("CPU",     info.get("cpu_name","N/A")),
                ("Cores",   info.get("cpu_cores","N/A")),
                ("Clock",   info.get("cpu_clock","N/A")),
            ]),
            ("🧠  Memory", [("RAM", info.get("ram","N/A"))]),
            ("🎮  Graphics", [
                ("GPU",    info.get("gpu","N/A")),
                ("Driver", info.get("gpu_driver","N/A")),
            ]),
            ("💽  Storage", [
                ("Disks",   info.get("disks","N/A")),
                ("Volumes", info.get("volumes","N/A")),
            ]),
            ("🔌  Motherboard & BIOS", [
                ("Board", info.get("motherboard","N/A")),
                ("BIOS",  info.get("bios","N/A")),
            ]),
            ("🔒  Security", [
                ("Secure Boot", info.get("secure_boot","N/A")),
                ("TPM",         info.get("tpm","N/A")),
                ("Defender",    info.get("defender","N/A")),
            ]),
            ("🌐  Network", [("Adapter", info.get("network","N/A"))]),
            ("⚡  Power",   [("Plan",    info.get("power","N/A"))]),
        ]

        row = 1
        for section_title, fields in sections:
            ctk.CTkLabel(card, text=section_title,
                font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                text_color=ACCENT
            ).grid(row=row, column=0, columnspan=2, padx=14, pady=(10,2), sticky="w")
            row += 1
            for key, val in fields:
                ctk.CTkLabel(card, text=key,
                    font=ctk.CTkFont(family=FONT, size=11),
                    text_color=TEXT3, width=120, anchor="w"
                ).grid(row=row, column=0, padx=(20,0), pady=1, sticky="w")
                ctk.CTkLabel(card, text=val,
                    font=ctk.CTkFont(family=FONT, size=11),
                    text_color=TEXT, anchor="w", wraplength=600
                ).grid(row=row, column=1, padx=(4,14), pady=1, sticky="w")
                row += 1

        def copy_all():
            lines = ["WinForge System Information", "="*40]
            for stitle, fields in sections:
                lines.append(f"\n{stitle}")
                for k, v in fields:
                    lines.append(f"  {k}: {v}")
            self.clipboard_clear()
            self.clipboard_append("\n".join(lines))
            self._log_line("[OK] System info copied to clipboard")

        ctk.CTkButton(card, text="Copy to Clipboard",
            font=ctk.CTkFont(family=FONT, size=12),
            fg_color=ACCENT, hover_color=self._dk(ACCENT),
            text_color="#fff", corner_radius=8, height=32,
            command=copy_all
        ).grid(row=row, column=0, columnspan=2, padx=14, pady=(14,12), sticky="w")

        ctk.CTkButton(card, text="Refresh",
            font=ctk.CTkFont(family=FONT, size=11),
            fg_color=CARD2, hover_color=HOVER,
            text_color=TEXT2, corner_radius=8, height=32,
            command=lambda: self._show_tab("System Info")
        ).grid(row=row, column=0, columnspan=2, padx=(160,14), pady=(14,12), sticky="w")

    # ─────────────────────────────────────────────────────────────
    # TAB: Repair
    # ─────────────────────────────────────────────────────────────
    def _tab_repair(self, p):
        p.grid_columnconfigure(0, weight=1)
        items = [
            ("DISM — Repair Windows Image", "Repairs the Windows component store from Windows Update.\nFixes corrupted system files that SFC can't repair on its own.", run_dism, SUCCESS),
            ("SFC — System File Checker",   "Scans and repairs corrupted Windows system files.\nRun after DISM for best results.", run_sfc, ACCENT),
            ("CHKDSK — Check Disk",         "Checks your C: drive for errors and bad sectors.\nWill schedule for next reboot if drive is in use.", run_chkdsk, WARN),
        ]
        for i, (title, desc, fn, color) in enumerate(items):
            card = self._card(p, i, title=title)
            self._lbl(card, desc, 1)
            self._btn(card, "Run", lambda f=fn: self._run(f, self._log_line), color=color, row=2)

    # ─────────────────────────────────────────────────────────────
    # TAB: Cleanup
    # ─────────────────────────────────────────────────────────────
    def _tab_cleanup(self, p):
        p.grid_columnconfigure((0,1), weight=1)
        items = [
            ("🗑️ Temp Files",        "Clears %TEMP%, Windows\\Temp, and Prefetch.",               clean_temp,         0,0),
            ("📦 Update Cache",      "Clears Windows Update download cache.",                      clean_update_cache, 0,1),
            ("🌐 Flush DNS",         "Flushes the DNS resolver cache.",                            flush_dns,          1,0),
            ("🔌 Reset Network",     "Resets TCP/IP stack, Winsock, firewall. Reboot needed.",     reset_network,      1,1),
            ("🗂️ Recycle Bin",       "Empties the Recycle Bin.",                                   empty_recycle,      2,0),
            ("📋 Event Logs",        "Clears all Windows event logs.",                             clean_event_logs,   2,1),
        ]
        for title, desc, fn, row, col in items:
            card = self._card(p, row, col=col, title=title)
            self._lbl(card, desc, 1)
            self._btn(card, "Run", lambda f=fn: self._run(f, self._log_line), row=2)

    # ─────────────────────────────────────────────────────────────
    # TAB: Dependencies
    # ─────────────────────────────────────────────────────────────
    def _tab_deps(self, p):
        p.grid_columnconfigure((0,1,2), weight=1)
        items = [
            (".NET 6",       lambda: install_dotnet("6",  self._log_line), 0,0),
            (".NET 7",       lambda: install_dotnet("7",  self._log_line), 0,1),
            (".NET 8",       lambda: install_dotnet("8",  self._log_line), 0,2),
            (".NET 9",       lambda: install_dotnet("9",  self._log_line), 1,0),
            ("VC++ All",     lambda: install_vcredist(    self._log_line), 1,1),
            ("DirectX",      lambda: install_directx(     self._log_line), 1,2),
            ("WebView2",     lambda: install_webview2(    self._log_line), 2,0),
            ("XNA Framework",lambda: install_xna(         self._log_line), 2,1),
        ]
        for title, fn, row, col in items:
            card = self._card(p, row, col=col, title=title)
            self._btn(card, "Install", lambda f=fn: self._run(f), row=1)

    # ─────────────────────────────────────────────────────────────
    # TAB: Install Apps
    # ─────────────────────────────────────────────────────────────
    def _tab_install(self, p):
        p.grid_columnconfigure(0, weight=1)

        APP_LIST = {
            "Browsers":        [("Firefox","Mozilla.Firefox"),("Chrome","Google.Chrome"),("Brave","Brave.Brave"),("Vivaldi","Vivaldi.Vivaldi")],
            "Communication":   [("Discord","Discord.Discord"),("Slack","SlackTechnologies.Slack"),("Teams","Microsoft.Teams"),("Telegram","Telegram.TelegramDesktop")],
            "Media":           [("VLC","VideoLAN.VLC"),("MPV","mpv.mpv"),("Spotify","Spotify.Spotify"),("HandBrake","HandBrake.HandBrake")],
            "Gaming":          [("Steam","Valve.Steam"),("Epic Games","EpicGames.EpicGamesLauncher"),("GOG Galaxy","GOG.Galaxy"),("Playnite","Playnite.Playnite")],
            "Development":     [("VS Code","Microsoft.VisualStudioCode"),("Git","Git.Git"),("Python","Python.Python.3"),("Node.js","OpenJS.NodeJS")],
            "Productivity":    [("Notion","Notion.Notion"),("Obsidian","Obsidian.Obsidian"),("7-Zip","7zip.7zip"),("ShareX","ShareX.ShareX")],
            "Utilities":       [("PowerToys","Microsoft.PowerToys"),("Bulk Rename Utility","TGRMNSoftware.BulkRenameUtility"),("CPU-Z","CPUID.CPU-Z"),("GPU-Z","TechPowerUp.GPU-Z")],
        }

        # Manager selector
        mgr_frame = ctk.CTkFrame(p, fg_color=CARD, corner_radius=8)
        mgr_frame.grid(row=0, column=0, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(mgr_frame, text="Package Manager:",
            font=ctk.CTkFont(family=FONT, size=12), text_color=TEXT2
        ).pack(side="left", padx=14, pady=10)
        self._mgr_var = ctk.StringVar(value="winget")
        for m in ("winget", "chocolatey"):
            ctk.CTkRadioButton(mgr_frame, text=m, variable=self._mgr_var, value=m.split()[0],
                font=ctk.CTkFont(family=FONT, size=12), text_color=TEXT,
                fg_color=ACCENT, hover_color=self._dk(ACCENT)
            ).pack(side="left", padx=10, pady=10)

        # Search
        search_frame = ctk.CTkFrame(p, fg_color=CARD, corner_radius=8)
        search_frame.grid(row=1, column=0, sticky="ew", padx=6, pady=5)
        search_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(search_frame, text="Search:", font=ctk.CTkFont(family=FONT, size=12), text_color=TEXT2
        ).grid(row=0, column=0, padx=14, pady=10)
        self._app_search = ctk.CTkEntry(search_frame, font=ctk.CTkFont(family=FONT, size=12),
            fg_color=BG, border_color=BORDER, text_color=TEXT, placeholder_text="Filter apps...")
        self._app_search.grid(row=0, column=1, padx=(0,14), pady=10, sticky="ew")
        self._app_search.bind("<KeyRelease>", lambda e: self._refresh_apps())
        self._app_list_parent = p
        self._app_list_data   = APP_LIST
        self._app_list_start_row = 2
        self._app_list_widgets = []
        self._refresh_apps()

    def _refresh_apps(self):
        query = self._app_search.get().lower() if hasattr(self, "_app_search") else ""
        for w in self._app_list_widgets:
            try: w.destroy()
            except: pass
        self._app_list_widgets.clear()

        row = self._app_list_start_row
        for cat, apps in self._app_list_data.items():
            filtered = [(name, pkg) for name, pkg in apps if not query or query in name.lower()]
            if not filtered: continue

            cat_lbl = ctk.CTkLabel(self._app_list_parent, text=cat,
                font=ctk.CTkFont(family=FONT, size=12, weight="bold"), text_color=ACCENT)
            cat_lbl.grid(row=row, column=0, padx=14, pady=(10,2), sticky="w")
            self._app_list_widgets.append(cat_lbl)
            row += 1

            grid_f = ctk.CTkFrame(self._app_list_parent, fg_color=CARD, corner_radius=8)
            grid_f.grid(row=row, column=0, sticky="ew", padx=6, pady=2)
            self._app_list_widgets.append(grid_f)
            for col_count in range(4):
                grid_f.grid_columnconfigure(col_count, weight=1)

            for idx, (name, pkg) in enumerate(filtered):
                col = idx % 4
                row_in = idx // 4
                btn = ctk.CTkButton(grid_f, text=name,
                    font=ctk.CTkFont(family=FONT, size=11),
                    fg_color=CARD2, hover_color=HOVER, text_color=TEXT,
                    corner_radius=6, height=32,
                    command=lambda n=name, pk=pkg: self._run(install_app, pk, self._mgr_var.get(), self._log_line))
                btn.grid(row=row_in, column=col, padx=4, pady=4, sticky="ew")
            row += 1

    # ─────────────────────────────────────────────────────────────
    # TAB: Tweaks & Debloat
    # ─────────────────────────────────────────────────────────────
    def _tab_tweaks(self, p):
        p.grid_columnconfigure(0, weight=1)

        # ── Essential Tweaks ──
        ess = self._card(p, 0, title="⚡ Essential Tweaks")
        tweaks_essential = [
            ("Disable Telemetry",           "WinUtil-verified: 12 registry keys + services. Disables all MS data collection.",
             lambda: self._run(tweak_telemetry, False, self._log_line),
             lambda: self._run(tweak_telemetry, True,  self._log_line)),
            ("Disable Activity History",    "WinUtil-verified: 3 registry keys. Stops Windows logging your activity.",
             lambda: self._run(tweak_activity_history, False, self._log_line),
             lambda: self._run(tweak_activity_history, True,  self._log_line)),
            ("Disable Location Tracking",   "WinUtil-verified: 3 registry keys + lfsvc service.",
             lambda: self._run(tweak_location, False, self._log_line),
             lambda: self._run(tweak_location, True,  self._log_line)),
            ("Disable Consumer Features",   "Stops Windows silently installing suggested apps and ads.",
             lambda: self._run(tweak_consumer_features, False, self._log_line),
             lambda: self._run(tweak_consumer_features, True,  self._log_line)),
            ("Disable Hibernation",         "Frees up ~4GB on your C: drive (hiberfil.sys). Safe if you don't use Sleep.",
             lambda: self._run(tweak_hibernation, False, self._log_line),
             lambda: self._run(tweak_hibernation, True,  self._log_line)),
            ("Disable Copilot",             "Removes Microsoft Copilot from taskbar and system.",
             lambda: self._run(tweak_copilot, False, self._log_line),
             lambda: self._run(tweak_copilot, True,  self._log_line)),
            ("Remove Widgets",              "WinUtil-verified: removes WebExperience + WidgetsPlatformRuntime AppX packages.",
             lambda: self._run(tweak_widgets, True,  self._log_line),
             lambda: self._run(tweak_widgets, False, self._log_line)),
            ("Optimize Services",           "Sets ~100 non-essential services to Manual. Speeds up boot. WinUtil list.",
             lambda: self._run(tweak_services, True,  self._log_line),
             lambda: self._run(tweak_services, False, self._log_line)),
        ]
        for i, (name, desc, apply_fn, undo_fn) in enumerate(tweaks_essential):
            row_base = (i * 3) + 1
            ctk.CTkLabel(ess, text=name,
                font=ctk.CTkFont(family=FONT, size=12, weight="bold"), text_color=TEXT
            ).grid(row=row_base, column=0, padx=14, pady=(8,0), sticky="w")
            ctk.CTkLabel(ess, text=desc,
                font=ctk.CTkFont(family=FONT, size=10), text_color=TEXT2, wraplength=640
            ).grid(row=row_base+1, column=0, padx=14, pady=(0,2), sticky="w")
            bf = ctk.CTkFrame(ess, fg_color="transparent")
            bf.grid(row=row_base+2, column=0, padx=10, pady=(0,4), sticky="w")
            ctk.CTkButton(bf, text="Apply", width=90, height=28,
                font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                fg_color=SUCCESS, hover_color=self._dk(SUCCESS), text_color="#fff",
                corner_radius=6, command=apply_fn).pack(side="left", padx=(0,6))
            ctk.CTkButton(bf, text="Undo", width=80, height=28,
                font=ctk.CTkFont(family=FONT, size=11),
                fg_color=CARD2, hover_color=HOVER, text_color=TEXT2,
                corner_radius=6, command=undo_fn).pack(side="left")

        # ── Preference Tweaks ──
        pref = self._card(p, 1, title="🎛️ Preferences")
        prefs = [
            ("Show File Extensions",  lambda: self._run(tweak_show_extensions, True,  self._log_line), lambda: self._run(tweak_show_extensions, False, self._log_line)),
            ("Show Hidden Files",     lambda: self._run(tweak_show_hidden,     True,  self._log_line), lambda: self._run(tweak_show_hidden,     False, self._log_line)),
            ("NumLock on Startup",    lambda: self._run(tweak_num_lock,        True,  self._log_line), lambda: self._run(tweak_num_lock,        False, self._log_line)),
            ("Verbose Logon Messages",lambda: self._run(tweak_verbose_logon,   True,  self._log_line), lambda: self._run(tweak_verbose_logon,   False, self._log_line)),
            ("Enable Fast Startup",   lambda: self._run(tweak_fast_startup,    True,  self._log_line), lambda: self._run(tweak_fast_startup,    False, self._log_line)),
            ("Dark Mode",             lambda: self._run(tweak_dark_mode,       True,  self._log_line), lambda: self._run(tweak_dark_mode,       False, self._log_line)),
        ]
        for i, (name, apply_fn, undo_fn) in enumerate(prefs):
            row_base = (i * 2) + 1
            ctk.CTkLabel(pref, text=name,
                font=ctk.CTkFont(family=FONT, size=12), text_color=TEXT
            ).grid(row=row_base, column=0, padx=14, pady=(6,2), sticky="w")
            bf = ctk.CTkFrame(pref, fg_color="transparent")
            bf.grid(row=row_base+1, column=0, padx=10, pady=(0,2), sticky="w")
            ctk.CTkButton(bf, text="Apply", width=90, height=26,
                fg_color=SUCCESS, hover_color=self._dk(SUCCESS), text_color="#fff",
                font=ctk.CTkFont(family=FONT, size=11), corner_radius=6, command=apply_fn
            ).pack(side="left", padx=(0,6))
            ctk.CTkButton(bf, text="Undo",  width=80, height=26,
                fg_color=CARD2, hover_color=HOVER, text_color=TEXT2,
                font=ctk.CTkFont(family=FONT, size=11), corner_radius=6, command=undo_fn
            ).pack(side="left")

        # ── Power Plans ──
        pw = self._card(p, 2, title="⚡ Power Plan")
        ctk.CTkLabel(pw, text="Ultimate Performance uses WinUtil's exact method (powercfg -duplicatescheme). Balanced restores Windows default.",
            font=ctk.CTkFont(family=FONT, size=10), text_color=TEXT2
        ).grid(row=1, column=0, columnspan=3, padx=14, pady=(0,6), sticky="w")
        for i, (name, plan) in enumerate([("Ultimate Performance","ultimate"),("Balanced (Default)","balanced"),("Power Saver","power_saver")]):
            ctk.CTkButton(pw, text=name, width=160, height=30,
                font=ctk.CTkFont(family=FONT, size=11),
                fg_color=CARD2, hover_color=HOVER, text_color=TEXT,
                corner_radius=6,
                command=lambda pl=plan: self._run(tweak_power_plan, pl, self._log_line)
            ).grid(row=2, column=i, padx=(14 if i==0 else 4, 4), pady=10, sticky="w")

        # ── Browser Debloat ──
        br = self._card(p, 3, title="🌐 Browser Debloat")
        ctk.CTkLabel(br, text="Applies WinUtil-verified registry policies to disable telemetry, sponsored content, and unnecessary features.",
            font=ctk.CTkFont(family=FONT, size=10), text_color=TEXT2
        ).grid(row=1, column=0, padx=14, pady=(0,6), sticky="w")
        bf2 = ctk.CTkFrame(br, fg_color="transparent")
        bf2.grid(row=2, column=0, padx=10, pady=(0,12), sticky="w")
        ctk.CTkButton(bf2, text="Debloat Edge",  width=130, height=32,
            fg_color=ACCENT, hover_color=self._dk(ACCENT), text_color="#fff",
            font=ctk.CTkFont(family=FONT, size=11), corner_radius=6,
            command=lambda: self._run(debloat_edge, self._log_line)
        ).pack(side="left", padx=(0,8))
        ctk.CTkButton(bf2, text="Debloat Brave", width=130, height=32,
            fg_color=PURPLE, hover_color=self._dk(PURPLE), text_color="#fff",
            font=ctk.CTkFont(family=FONT, size=11), corner_radius=6,
            command=lambda: self._run(debloat_brave, self._log_line)
        ).pack(side="left")

        # ── App Removal ──
        rm = self._card(p, 4, title="🗑️ Remove Bloatware Apps")
        ctk.CTkLabel(rm, text="Checks if each app is installed before attempting removal. Creates a restore point this session if not already done.",
            font=ctk.CTkFont(family=FONT, size=10), text_color=TEXT2
        ).grid(row=1, column=0, padx=14, pady=(0,6), sticky="w")

        bloatware = [
            ("Cortana",          "Microsoft.549981C3F5F10"),
            ("Xbox Apps",        "Microsoft.XboxApp"),
            ("Mixed Reality",    "Microsoft.MixedReality.Portal"),
            ("3D Viewer",        "Microsoft.Microsoft3DViewer"),
            ("Paint 3D",         "Microsoft.MSPaint"),
            ("Movies & TV",      "Microsoft.ZuneVideo"),
            ("Groove Music",     "Microsoft.ZuneMusic"),
            ("Your Phone",       "Microsoft.YourPhone"),
            ("Tips",             "Microsoft.Getstarted"),
            ("Solitaire",        "Microsoft.MicrosoftSolitaireCollection"),
            ("News",             "Microsoft.BingNews"),
            ("Weather",          "Microsoft.BingWeather"),
            ("Maps",             "Microsoft.WindowsMaps"),
            ("People",           "Microsoft.People"),
            ("Feedback Hub",     "Microsoft.WindowsFeedbackHub"),
            ("Teams (Personal)", "MicrosoftTeams"),
            ("OneDrive",         "Microsoft.OneDriveSync"),
            ("Bing Search",      "Microsoft.BingSearch"),
        ]
        rm.grid_columnconfigure((0,1,2,3), weight=1)
        for i, (name, pkg) in enumerate(bloatware):
            row = (i // 4) + 2
            col = i % 4
            ctk.CTkButton(rm, text=f"Remove {name}", height=28,
                font=ctk.CTkFont(family=FONT, size=10),
                fg_color=CARD2, hover_color="#5c1a1a", text_color=TEXT,
                corner_radius=6,
                command=lambda n=name, pk=pkg: self._remove_with_rp(n, pk)
            ).grid(row=row, column=col, padx=4, pady=4, sticky="ew")

    def _remove_with_rp(self, name: str, pkg: str):
        """Create a restore point the first time per session, then remove the app."""
        def _do():
            if not self._restore_point_this_session:
                self._log_line("[INFO] Creating session restore point before first removal...")
                create_restore_point("WinForge App Removal", self._log_line)
                self._restore_point_this_session = True
            remove_app(pkg, name, self._log_line)
        threading.Thread(target=_do, daemon=True).start()

    # ─────────────────────────────────────────────────────────────
    # TAB: DNS Settings
    # ─────────────────────────────────────────────────────────────
    def _tab_dns(self, p):
        p.grid_columnconfigure(0, weight=1)
        card = self._card(p, 0, title="DNS Provider")
        ctk.CTkLabel(card, text="Sets DNS on all active network adapters and flushes the cache.",
            font=ctk.CTkFont(family=FONT, size=11), text_color=TEXT2
        ).grid(row=1, column=0, padx=14, pady=(0,8), sticky="w")

        dns_info = {
            "Cloudflare":             ("1.1.1.1 / 1.0.0.1",           "Fastest public DNS. Privacy-focused. No filtering."),
            "Google":                 ("8.8.8.8 / 8.8.4.4",           "Reliable, fast. Google-owned."),
            "Quad9 (Malware Block)":  ("9.9.9.9 / 149.112.112.112",   "Blocks known malware/phishing domains."),
            "OpenDNS":                ("208.67.222.222 / 208.67.220.220","Cisco-owned. Optional content filtering."),
            "AdGuard":                ("94.140.14.14 / 94.140.15.15",  "Blocks ads and trackers at DNS level."),
            "Cloudflare Family":      ("1.1.1.3 / 1.0.0.3",           "Cloudflare with adult content filtering."),
            "Automatic (DHCP)":       ("Reset to automatic",           "Let your router assign DNS (default)."),
        }
        for i, (provider, (ips, desc)) in enumerate(dns_info.items()):
            row = i + 2
            f = ctk.CTkFrame(card, fg_color=CARD2, corner_radius=6)
            f.grid(row=row, column=0, sticky="ew", padx=10, pady=3)
            f.grid_columnconfigure(1, weight=1)
            ctk.CTkButton(f, text="Apply", width=70, height=28,
                fg_color=ACCENT, hover_color=self._dk(ACCENT), text_color="#fff",
                font=ctk.CTkFont(family=FONT, size=11), corner_radius=5,
                command=lambda prov=provider: self._run(set_dns, prov, self._log_line)
            ).grid(row=0, column=0, padx=(8,10), pady=8)
            ctk.CTkLabel(f, text=provider,
                font=ctk.CTkFont(family=FONT, size=12, weight="bold"), text_color=TEXT
            ).grid(row=0, column=1, sticky="w")
            ctk.CTkLabel(f, text=ips,
                font=ctk.CTkFont(family=MONO, size=10), text_color=ACCENT
            ).grid(row=0, column=2, padx=10)
            ctk.CTkLabel(f, text=desc,
                font=ctk.CTkFont(family=FONT, size=10), text_color=TEXT2
            ).grid(row=0, column=3, padx=(0,10))

    # ─────────────────────────────────────────────────────────────
    # TAB: Windows Updates
    # ─────────────────────────────────────────────────────────────
    def _tab_updates(self, p):
        p.grid_columnconfigure(0, weight=1)
        items = [
            ("Default (Automatic)",   "Restores Windows Update to Microsoft defaults — automatic updates enabled.",
             set_updates_default,  SUCCESS),
            ("Security Only",         "Receive security patches but defer feature updates by 365 days.",
             set_updates_security_only, ACCENT),
            ("Disable Updates",       "Disables Windows Update entirely. Not recommended for long-term use.",
             set_updates_disable,  WARN),
        ]
        for i, (title, desc, fn, color) in enumerate(items):
            card = self._card(p, i, title=title)
            self._lbl(card, desc, 1)
            self._btn(card, "Apply", lambda f=fn: self._run(f, self._log_line), color=color, row=2)

    # ─────────────────────────────────────────────────────────────
    # TAB: Registry Health
    # ─────────────────────────────────────────────────────────────
    def _tab_registry(self, p):
        p.grid_columnconfigure(0, weight=1)

        scan_card = self._card(p, 0, title="🔍 Scan Broken Uninstall Entries")
        self._lbl(scan_card, "Finds registry entries pointing to .exe files that no longer exist.\nSafe to clean — these are just orphaned leftovers from uninstalled software.", 1)
        self._btn(scan_card, "Scan", lambda: self._run(scan_broken_uninstall, self._log_line), color=ACCENT, row=2)

        clean_card = self._card(p, 1, title="🧹 Clean Broken Entries")
        self._lbl(clean_card, "Always backs up to a .reg file on your Desktop before removing anything.\nRun the scan first to see what will be removed.", 1)
        self._btn(clean_card, "Clean", lambda: self._run(clean_broken_uninstall, self._log_line), color=WARN, row=2)

    # ─────────────────────────────────────────────────────────────
    # TAB: System Tools
    # ─────────────────────────────────────────────────────────────
    def _tab_systools(self, p):
        p.grid_columnconfigure((0,1,2), weight=1)
        tools = [
            ("Device Manager",    "devmgmt.msc",   0,0),
            ("Disk Management",   "diskmgmt.msc",  0,1),
            ("Task Manager",      "taskmgr",       0,2),
            ("Services",          "services.msc",  1,0),
            ("Event Viewer",      "eventvwr.msc",  1,1),
            ("Registry Editor",   "regedit",       1,2),
            ("System Properties", "sysdm.cpl",     2,0),
            ("Network Adapter",   "ncpa.cpl",      2,1),
            ("Firewall",          "wf.msc",        2,2),
            ("Group Policy",      "gpedit.msc",    3,0),
            ("DirectX Diag",      "dxdiag",        3,1),
            ("Control Panel",     "control",       3,2),
            ("Programs & Features","appwiz.cpl",   4,0),
            ("Startup Apps",      "shell:startup", 4,1),
            ("Environment Vars",  "rundll32 sysdm.cpl,EditEnvironmentVariables", 4,2),
        ]
        for name, cmd, row, col in tools:
            card = self._card(p, row, col=col, title=name)
            self._btn(card, "Open",
                lambda c=cmd: self._run(lambda cc=c: run_ps(f'Start-Process "{cc}"')),
                color=CARD2, row=1)

    # ─────────────────────────────────────────────────────────────
    # TAB: Restore Points
    # ─────────────────────────────────────────────────────────────
    def _tab_restore(self, p):
        p.grid_columnconfigure(0, weight=1)
        card = self._card(p, 0, title="💾 Create System Restore Point")
        self._lbl(card, "Creates a Windows System Restore Point immediately.\nDoes not affect personal files — only system settings and registry.\nWinForge bypasses the Windows 24-hour limit so you can create multiple in one session.", 1)

        lf = ctk.CTkFrame(card, fg_color="transparent")
        lf.grid(row=2, column=0, padx=14, pady=(10,4), sticky="w")
        ctk.CTkLabel(lf, text="Description:",
            font=ctk.CTkFont(family=FONT, size=12), text_color=TEXT2
        ).grid(row=0, column=0, padx=(0,8))
        self._rp_entry = ctk.CTkEntry(lf, width=320,
            font=ctk.CTkFont(family=FONT, size=12),
            fg_color=BG, border_color=BORDER, text_color=TEXT,
            placeholder_text="WinForge Manual Restore Point")
        self._rp_entry.grid(row=0, column=1)
        self._btn(card, "Create Now",
            lambda: self._run(create_restore_point, self._rp_entry.get().strip() or "WinForge Manual Restore Point", self._log_line),
            color=SUCCESS, row=3)


def main():
    app = WinForge()
    app.mainloop()

if __name__ == "__main__":
    main()
