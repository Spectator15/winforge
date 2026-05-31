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
    updates_default, updates_security_only, updates_disable_all,
    remove_app, BLOATWARE, TWEAKS, PRESETS, open_panel
)

# ─── THEME ────────────────────────────────────────────────────────────────────
BG         = "#0c0c10"
PANEL      = "#111118"
CARD       = "#18181f"
CARD2      = "#1e1e28"
HOVER      = "#25252f"
ACCENT     = "#5b8dee"
ACCENT2    = "#3d6fd4"
SUCCESS    = "#3ecf6e"
WARNING    = "#f5a124"
DANGER     = "#e84040"
DANGER2    = "#a02020"
TEXT       = "#eeeef5"
TEXT2      = "#9090a8"
TEXT3      = "#555568"
BORDER     = "#28283a"
PURPLE     = "#9b5de5"


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = ctk.CTkToplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        self.tip.configure(fg_color=CARD2)
        frame = ctk.CTkFrame(self.tip, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=6)
        frame.pack(padx=1, pady=1)
        ctk.CTkLabel(
            frame, text=self.text,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT2, wraplength=320, justify="left"
        ).pack(padx=10, pady=6)

    def hide(self, event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class WinForgeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WinForge")
        self.geometry("1140x740")
        self.minsize(960, 640)
        self.configure(fg_color=BG)
        self._current_tab = None
        self._tweak_vars = {}
        self._bloat_vars = {}
        self._build_layout()
        self._show_tab("repair")

    # ─── LAYOUT ───────────────────────────────────────────────────────────────

    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, fg_color=PANEL, width=210, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_rowconfigure(12, weight=1)

        logo = ctk.CTkFrame(sb, fg_color="transparent")
        logo.grid(row=0, column=0, padx=18, pady=(22, 6), sticky="ew")
        ctk.CTkLabel(logo, text="⚙  WinForge",
                     font=ctk.CTkFont(family="Segoe UI", size=21, weight="bold"),
                     text_color=ACCENT).pack(anchor="w")
        ctk.CTkLabel(logo, text="Windows Toolkit  ·  Made by Danish",
                     font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=TEXT3).pack(anchor="w")

        ctk.CTkFrame(sb, fg_color=BORDER, height=1).grid(
            row=1, column=0, sticky="ew", padx=14, pady=(8, 14))

        nav = [
            ("repair",       "🔧   System Repair"),
            ("cleanup",      "🧹   Cleanup"),
            ("dependencies", "📦   Dependencies"),
            ("tweaks",       "⚡   Tweaks"),
            ("debloat",      "🗑   Debloat"),
            ("updates",      "🔄   Windows Updates"),
            ("tools",        "🛠   System Tools"),
            ("restore",      "🛡   Restore Point"),
        ]
        self._nav_btns = {}
        for i, (tid, label) in enumerate(nav, start=2):
            btn = ctk.CTkButton(
                sb, text=label, anchor="w",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                fg_color="transparent", hover_color=HOVER,
                text_color=TEXT2, corner_radius=8, height=40,
                command=lambda t=tid: self._show_tab(t)
            )
            btn.grid(row=i, column=0, padx=8, pady=2, sticky="ew")
            self._nav_btns[tid] = btn

        ctk.CTkLabel(sb, text="v2.0.0  ·  admin mode",
                     font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=TEXT3).grid(row=13, column=0, padx=18, pady=14, sticky="sw")

    def _build_main(self):
        self._main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._main.grid(row=0, column=1, sticky="nsew")
        self._main.grid_columnconfigure(0, weight=1)
        self._main.grid_rowconfigure(1, weight=1)
        self._build_log()

    def _build_log(self):
        lf = ctk.CTkFrame(self._main, fg_color=PANEL, corner_radius=10)
        lf.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 12))
        lf.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(lf, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 0))
        hdr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(hdr, text="Output Log",
                     font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                     text_color=TEXT2).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="Clear", width=58, height=22,
                      font=ctk.CTkFont(family="Segoe UI", size=11),
                      fg_color=CARD, hover_color=HOVER, text_color=TEXT2,
                      corner_radius=6, command=self._clear_log
                      ).grid(row=0, column=2, sticky="e")

        self._log = ctk.CTkTextbox(lf, height=150,
                                   font=ctk.CTkFont(family="Consolas", size=12),
                                   fg_color=BG, text_color=TEXT,
                                   corner_radius=8, wrap="word", state="disabled")
        self._log.grid(row=1, column=0, sticky="ew", padx=8, pady=8)
        self._log.tag_config("ok",   foreground=SUCCESS)
        self._log.tag_config("warn", foreground=WARNING)
        self._log.tag_config("err",  foreground=DANGER)
        self._log.tag_config("info", foreground=ACCENT)

    # ─── TAB SWITCHING ────────────────────────────────────────────────────────

    def _show_tab(self, tid):
        if self._current_tab:
            self._current_tab.destroy()
        for k, b in self._nav_btns.items():
            b.configure(fg_color=ACCENT2 if k == tid else "transparent",
                        text_color=TEXT if k == tid else TEXT2)
        frame = ctk.CTkScrollableFrame(self._main, fg_color="transparent", corner_radius=0)
        frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=(8, 6))
        frame.grid_columnconfigure(0, weight=1)
        self._current_tab = frame
        {
            "repair": self._tab_repair,
            "cleanup": self._tab_cleanup,
            "dependencies": self._tab_deps,
            "tweaks": self._tab_tweaks,
            "debloat": self._tab_debloat,
            "updates": self._tab_updates,
            "tools": self._tab_tools,
            "restore": self._tab_restore,
        }[tid](frame)

    # ─── SHARED HELPERS ───────────────────────────────────────────────────────

    def _header(self, parent, title, sub="", row=0):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=row, column=0, sticky="ew", pady=(2, 10))
        ctk.CTkLabel(f, text=title,
                     font=ctk.CTkFont(family="Segoe UI", size=19, weight="bold"),
                     text_color=TEXT).pack(anchor="w")
        if sub:
            ctk.CTkLabel(f, text=sub,
                         font=ctk.CTkFont(family="Segoe UI", size=12),
                         text_color=TEXT2).pack(anchor="w")

    def _card(self, parent, row, col=0, cs=1, py=(0, 8)):
        c = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10,
                         border_width=1, border_color=BORDER)
        c.grid(row=row, column=col, columnspan=cs, sticky="ew", pady=py)
        c.grid_columnconfigure(0, weight=1)
        return c

    def _clabel(self, card, title, desc, dangerous=False):
        tc = DANGER if dangerous else TEXT
        ctk.CTkLabel(card, text=title,
                     font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                     text_color=tc, anchor="w"
                     ).grid(row=0, column=0, padx=14, pady=(12, 0), sticky="w")
        ctk.CTkLabel(card, text=desc,
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=TEXT2, anchor="w", wraplength=520, justify="left"
                     ).grid(row=1, column=0, padx=14, pady=(2, 0), sticky="w")

    def _run_btn(self, card, label, cmd, color=ACCENT, row=2, dangerous=False):
        fc = DANGER if dangerous else color
        ctk.CTkButton(card, text=label,
                      font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                      fg_color=fc, hover_color=self._dk(fc),
                      text_color="#fff", corner_radius=8, height=34, width=110,
                      command=cmd
                      ).grid(row=row, column=0, padx=14, pady=10, sticky="w")

    def _dk(self, h):
        r, g, b = int(h[1:3],16), int(h[3:5],16), int(h[5:7],16)
        f = 0.72
        return "#{:02x}{:02x}{:02x}".format(int(r*f), int(g*f), int(b*f))

    def _op(self, fn):
        def run():
            try: fn(self._log_line)
            except Exception as e: self._log_line(f"[ERROR] {e}")
        threading.Thread(target=run, daemon=True).start()

    # ─── LOGGING ──────────────────────────────────────────────────────────────

    def _log_line(self, msg):
        def _w():
            self._log.configure(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            tag = "ok" if "[OK]" in msg or "success" in msg.lower() or "complete" in msg.lower() or "cleaned" in msg.lower() else \
                  "warn" if "[WARN]" in msg or "caution" in msg.lower() else \
                  "err" if "[ERROR]" in msg or "error" in msg.lower() or "fail" in msg.lower() else \
                  "info" if "[INFO]" in msg else None
            line = f"[{ts}] {msg}\n"
            if tag:
                self._log.insert("end", line, tag)
            else:
                self._log.insert("end", line)
            self._log.see("end")
            self._log.configure(state="disabled")
        self.after(0, _w)

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    # ─── REPAIR TAB ───────────────────────────────────────────────────────────

    def _tab_repair(self, p):
        self._header(p, "System Repair", "Fix corrupted Windows files and components.")
        items = [
            ("DISM RestoreHealth",
             "Repairs the Windows component store. Run this first if Windows is acting up. Takes 5-15 min.",
             lambda: self._op(run_dism), ACCENT, False),
            ("System File Checker (SFC)",
             "Scans and repairs corrupted Windows system files. Run after DISM.",
             lambda: self._op(run_sfc), ACCENT, False),
            ("Check Disk (CHKDSK)",
             "Schedules a disk integrity check on next boot.",
             lambda: self._op(run_chkdsk), WARNING, False),
            ("Full Repair  (DISM + SFC)",
             "Creates a restore point then runs DISM followed by SFC automatically.",
             lambda: self._op(run_full_repair), SUCCESS, False),
        ]
        for i, (t, d, c, col, dan) in enumerate(items, 1):
            card = self._card(p, i)
            self._clabel(card, t, d, dan)
            self._run_btn(card, "Run", c, col, dangerous=dan)

    # ─── CLEANUP TAB ──────────────────────────────────────────────────────────

    def _tab_cleanup(self, p):
        self._header(p, "System Cleanup", "Free up disk space and clear cached junk.")
        items = [
            ("Temp Files", "Deletes %TEMP% and C:\\Windows\\Temp.", lambda: self._op(clean_temp_files), ACCENT, False),
            ("Windows Update Cache", "Clears Software Distribution downloads. Safe after updates install.", lambda: self._op(clean_windows_update_cache), ACCENT, False),
            ("Prefetch Files", "Clears prefetch cache. Windows rebuilds it automatically.", lambda: self._op(clean_prefetch), ACCENT, False),
            ("Windows Disk Cleanup", "Runs built-in Disk Cleanup with all categories selected.", lambda: self._op(run_disk_cleanup), ACCENT, False),
            ("Flush DNS Cache", "Clears DNS resolver cache. Useful if websites aren't loading.", lambda: self._op(flush_dns), ACCENT, False),
            ("Reset Network Stack", "Resets Winsock, TCP/IP, flushes DNS. Good for persistent network issues. Restart required.", lambda: self._op(reset_network), WARNING, True),
        ]
        for i, (t, d, c, col, dan) in enumerate(items, 1):
            card = self._card(p, i)
            self._clabel(card, t, d, dan)
            self._run_btn(card, "Run", c, col, dangerous=dan)

    # ─── DEPS TAB ─────────────────────────────────────────────────────────────

    def _tab_deps(self, p):
        self._header(p, "Dependencies", "Install common Windows runtimes via winget.")
        items = [
            (".NET Runtime 6",  "Required by many apps and games.", lambda: self._op(lambda cb: install_dotnet("6", cb))),
            (".NET Runtime 7",  "Some newer apps require this.", lambda: self._op(lambda cb: install_dotnet("7", cb))),
            (".NET Runtime 8",  "Latest LTS version. Install this if unsure.", lambda: self._op(lambda cb: install_dotnet("8", cb))),
            (".NET Runtime 9",  "Cutting edge. Only if a specific app needs it.", lambda: self._op(lambda cb: install_dotnet("9", cb))),
            ("Visual C++ Redists 2015-2022 (x64 + x86)", "Most common fix for DLL errors in games.", lambda: self._op(install_vcredist)),
            ("DirectX",         "Core graphics API. Ensures it's up to date.", lambda: self._op(install_directx)),
            ("WebView2 Runtime","Required by many modern apps that embed web content.", lambda: self._op(install_webview2)),
        ]
        for i, (t, d, c) in enumerate(items, 1):
            card = self._card(p, i)
            self._clabel(card, t, d)
            self._run_btn(card, "Install", c)

    # ─── TWEAKS TAB ───────────────────────────────────────────────────────────

    def _tab_tweaks(self, p):
        self._header(p, "Tweaks", "Pick tweaks individually or load a preset. Hover any item for details.")

        # Presets
        pc = self._card(p, 1)
        ctk.CTkLabel(pc, text="Presets",
                     font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                     text_color=TEXT).grid(row=0, column=0, padx=14, pady=(12,2), sticky="w")
        ctk.CTkLabel(pc, text="Loads recommended tweaks. You can adjust before applying.",
                     font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT2
                     ).grid(row=1, column=0, padx=14, pady=(0,8), sticky="w")
        pr = ctk.CTkFrame(pc, fg_color="transparent")
        pr.grid(row=2, column=0, padx=14, pady=(0,12), sticky="w")
        colors = [ACCENT, SUCCESS, WARNING, PURPLE]
        for i, (name, _) in enumerate(PRESETS.items()):
            col = colors[i % len(colors)]
            b = ctk.CTkButton(pr, text=name,
                              font=ctk.CTkFont(family="Segoe UI", size=12),
                              fg_color=col, hover_color=self._dk(col),
                              text_color="#fff", corner_radius=8, height=32,
                              command=lambda n=name: self._load_preset(n))
            b.grid(row=0, column=i, padx=(0, 8))

        # Section builder
        self._tweak_vars = {}
        row = 2
        for section_label, cat in [("Essential Tweaks", "essential"),
                                    ("Advanced Tweaks  —  CAUTION", "advanced"),
                                    ("Preferences", "preference")]:
            items = {k: v for k, v in TWEAKS.items() if v["category"] == cat}
            if not items:
                continue
            danger_section = cat == "advanced"
            sc = self._card(p, row)
            row += 1
            lc = DANGER if danger_section else ACCENT
            ctk.CTkLabel(sc, text=section_label,
                         font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                         text_color=lc).grid(row=0, column=0, columnspan=2, padx=14, pady=(12,8), sticky="w")
            sc.grid_columnconfigure(0, weight=1)
            sc.grid_columnconfigure(1, weight=1)
            for idx, (tid, td) in enumerate(items.items()):
                c = idx % 2
                r = (idx // 2) + 1
                var = ctk.BooleanVar(value=False)
                self._tweak_vars[tid] = var
                fc = DANGER if td["dangerous"] else ACCENT
                cb = ctk.CTkCheckBox(sc, text=td["label"], variable=var,
                                     font=ctk.CTkFont(family="Segoe UI", size=12),
                                     text_color=DANGER if td["dangerous"] else TEXT,
                                     fg_color=fc, hover_color=self._dk(fc),
                                     checkmark_color="#fff", border_color=BORDER)
                cb.grid(row=r, column=c, padx=14, pady=5, sticky="w")
                ToolTip(cb, td["tooltip"])
            # padding row
            ctk.CTkFrame(sc, fg_color="transparent", height=4).grid(row=999, column=0)

        # Apply buttons
        bf = ctk.CTkFrame(p, fg_color="transparent")
        bf.grid(row=row, column=0, sticky="ew", pady=(4, 8))
        ctk.CTkButton(bf, text="Apply Selected Tweaks",
                      font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                      fg_color=SUCCESS, hover_color=self._dk(SUCCESS),
                      text_color="#fff", corner_radius=8, height=40, width=220,
                      command=self._apply_tweaks).grid(row=0, column=0, padx=(0,10))
        ctk.CTkButton(bf, text="Clear All",
                      font=ctk.CTkFont(family="Segoe UI", size=13),
                      fg_color=CARD, hover_color=HOVER,
                      text_color=TEXT2, corner_radius=8, height=40, width=100,
                      command=lambda: [v.set(False) for v in self._tweak_vars.values()]
                      ).grid(row=0, column=1)

    def _load_preset(self, name):
        preset = PRESETS.get(name, {})
        selected = preset.get("tweaks", [])
        for tid, var in self._tweak_vars.items():
            var.set(tid in selected)
        self._log_line(f"[INFO] Preset '{name}' loaded. Review and click Apply.")

    def _apply_tweaks(self):
        selected = [tid for tid, var in self._tweak_vars.items() if var.get()]
        if not selected:
            self._log_line("[WARN] No tweaks selected.")
            return
        dangerous = [tid for tid in selected if TWEAKS[tid]["dangerous"]]
        if dangerous:
            labels = ", ".join(TWEAKS[t]["label"] for t in dangerous)
            dialog = ctk.CTkToplevel(self)
            dialog.title("Confirm Dangerous Tweaks")
            dialog.geometry("480x220")
            dialog.configure(fg_color=CARD)
            dialog.grab_set()
            ctk.CTkLabel(dialog, text="⚠  Warning",
                         font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
                         text_color=DANGER).pack(pady=(20, 4))
            ctk.CTkLabel(dialog,
                         text=f"The following tweaks are marked as dangerous:\n{labels}\n\nA restore point will be created first. Continue?",
                         font=ctk.CTkFont(family="Segoe UI", size=12),
                         text_color=TEXT2, wraplength=420, justify="center").pack(pady=8)
            bf = ctk.CTkFrame(dialog, fg_color="transparent")
            bf.pack(pady=12)
            confirmed = [False]
            def yes():
                confirmed[0] = True
                dialog.destroy()
            def no():
                dialog.destroy()
            ctk.CTkButton(bf, text="Yes, Apply", fg_color=DANGER, hover_color=DANGER2,
                          text_color="#fff", corner_radius=8, height=36, width=120,
                          command=yes).grid(row=0, column=0, padx=8)
            ctk.CTkButton(bf, text="Cancel", fg_color=CARD2, hover_color=HOVER,
                          text_color=TEXT2, corner_radius=8, height=36, width=100,
                          command=no).grid(row=0, column=1, padx=8)
            dialog.wait_window()
            if not confirmed[0]:
                return

        def run():
            self._log_line(f"[INFO] Creating restore point before {len(selected)} tweak(s)...")
            create_restore_point("WinForge Tweaks", self._log_line)
            for tid in selected:
                TWEAKS[tid]["fn"](self._log_line)
            self._log_line(f"[OK] All {len(selected)} tweaks applied.")
        threading.Thread(target=run, daemon=True).start()

    # ─── DEBLOAT TAB ──────────────────────────────────────────────────────────

    def _tab_debloat(self, p):
        self._header(p, "Debloat", "Remove pre-installed Windows apps. Red items need extra caution.")

        info = self._card(p, 1)
        ctk.CTkLabel(info,
                     text="ℹ  A restore point is created before removal. Removed apps can be reinstalled from the Microsoft Store.",
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=TEXT2, wraplength=600, justify="left"
                     ).grid(row=0, column=0, padx=14, pady=10, sticky="w")

        safe_apps   = {k: v for k, v in BLOATWARE.items() if not v[1]}
        danger_apps = {k: v for k, v in BLOATWARE.items() if v[1]}

        self._bloat_vars = {}

        for section_title, apps, is_danger in [
            ("Standard Bloatware  —  Safe to Remove", safe_apps, False),
            ("Sensitive Apps  —  CAUTION", danger_apps, True),
        ]:
            sc = self._card(p, 2 if not is_danger else 3)
            lc = DANGER if is_danger else ACCENT
            ctk.CTkLabel(sc, text=section_title,
                         font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                         text_color=lc).grid(row=0, column=0, columnspan=2, padx=14, pady=(12,8), sticky="w")
            sc.grid_columnconfigure(0, weight=1)
            sc.grid_columnconfigure(1, weight=1)
            for idx, (pkg_id, (name, _, tooltip)) in enumerate(apps.items()):
                c = idx % 2
                r = (idx // 2) + 1
                var = ctk.BooleanVar(value=False)
                self._bloat_vars[pkg_id] = var
                fc = DANGER if is_danger else ACCENT
                cb = ctk.CTkCheckBox(sc, text=name, variable=var,
                                     font=ctk.CTkFont(family="Segoe UI", size=12),
                                     text_color=DANGER if is_danger else TEXT,
                                     fg_color=fc, hover_color=self._dk(fc),
                                     checkmark_color="#fff", border_color=BORDER)
                cb.grid(row=r, column=c, padx=14, pady=5, sticky="w")
                ToolTip(cb, tooltip)
            ctk.CTkFrame(sc, fg_color="transparent", height=4).grid(row=999, column=0)

        # Preset buttons
        qf = ctk.CTkFrame(p, fg_color="transparent")
        qf.grid(row=4, column=0, sticky="ew", pady=(4, 0))
        ctk.CTkButton(qf, text="Select All Safe",
                      font=ctk.CTkFont(family="Segoe UI", size=12),
                      fg_color=ACCENT, hover_color=self._dk(ACCENT),
                      text_color="#fff", corner_radius=8, height=32,
                      command=lambda: [self._bloat_vars[k].set(True) for k in BLOATWARE if not BLOATWARE[k][1]]
                      ).grid(row=0, column=0, padx=(0,8))
        ctk.CTkButton(qf, text="Clear All",
                      font=ctk.CTkFont(family="Segoe UI", size=12),
                      fg_color=CARD, hover_color=HOVER,
                      text_color=TEXT2, corner_radius=8, height=32,
                      command=lambda: [v.set(False) for v in self._bloat_vars.values()]
                      ).grid(row=0, column=1, padx=(0,8))

        ctk.CTkButton(p, text="Remove Selected Apps",
                      font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                      fg_color=DANGER, hover_color=DANGER2,
                      text_color="#fff", corner_radius=8, height=40, width=220,
                      command=self._run_debloat
                      ).grid(row=5, column=0, pady=(10, 8), sticky="w")

    def _run_debloat(self):
        selected = [pkg for pkg, var in self._bloat_vars.items() if var.get()]
        if not selected:
            self._log_line("[WARN] No apps selected.")
            return

        has_danger = any(BLOATWARE[p][1] for p in selected)
        names = ", ".join(BLOATWARE[p][0] for p in selected)

        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm App Removal")
        dialog.geometry("500x240")
        dialog.configure(fg_color=CARD)
        dialog.grab_set()
        ctk.CTkLabel(dialog,
                     text="⚠  Confirm Removal" if has_danger else "Confirm Removal",
                     font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
                     text_color=DANGER if has_danger else TEXT).pack(pady=(20, 4))
        ctk.CTkLabel(dialog,
                     text=f"You are about to remove {len(selected)} app(s):\n{names[:200]}{'...' if len(names) > 200 else ''}\n\nA restore point will be created first.",
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=TEXT2, wraplength=440, justify="center").pack(pady=8)
        bf = ctk.CTkFrame(dialog, fg_color="transparent")
        bf.pack(pady=12)
        confirmed = [False]
        def yes():
            confirmed[0] = True
            dialog.destroy()
        def no():
            dialog.destroy()
        ctk.CTkButton(bf, text="Yes, Remove", fg_color=DANGER, hover_color=DANGER2,
                      text_color="#fff", corner_radius=8, height=36, width=130,
                      command=yes).grid(row=0, column=0, padx=8)
        ctk.CTkButton(bf, text="Cancel", fg_color=CARD2, hover_color=HOVER,
                      text_color=TEXT2, corner_radius=8, height=36, width=100,
                      command=no).grid(row=0, column=1, padx=8)
        dialog.wait_window()
        if not confirmed[0]:
            return

        def run():
            self._log_line(f"[INFO] Creating restore point before removing {len(selected)} app(s)...")
            create_restore_point("WinForge Debloat", self._log_line)
            for pkg in selected:
                remove_app(pkg, self._log_line)
            self._log_line(f"[OK] Debloat complete. {len(selected)} app(s) removed.")
        threading.Thread(target=run, daemon=True).start()

    # ─── UPDATES TAB ──────────────────────────────────────────────────────────

    def _tab_updates(self, p):
        self._header(p, "Windows Updates", "Control how Windows installs updates.")

        configs = [
            ("Default Settings", ACCENT, False,
             "Resets Windows Update to its out-of-the-box defaults.\n\n• No custom policies\n• Normal update schedule\n• Removes any previous WinForge update changes",
             lambda: self._op(updates_default)),
            ("Security Settings", SUCCESS, False,
             "Balances security and stability.\n\n• Feature updates delayed 365 days\n• Security updates installed after 4 days\n• Driver updates via Windows Update disabled\n\nNote: Pro/Enterprise only (requires Group Policy)",
             lambda: self._op(updates_security_only)),
            ("Disable All Updates", DANGER, True,
             "!! Not Recommended !!\n\n• Disables ALL Windows Updates completely\n• Increases security risk significantly\n• Only use on isolated or test systems\n\nWarning: Your system will be vulnerable without security patches.",
             lambda: self._op(updates_disable_all)),
        ]

        for i, (title, col, danger, desc, cmd) in enumerate(configs, 1):
            card = self._card(p, i)
            card.grid_columnconfigure(0, weight=1)
            tc = DANGER if danger else TEXT
            ctk.CTkLabel(card, text=title,
                         font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
                         text_color=tc).grid(row=0, column=0, padx=14, pady=(14,4), sticky="w")
            ctk.CTkLabel(card, text=desc,
                         font=ctk.CTkFont(family="Segoe UI", size=11),
                         text_color=TEXT2 if not danger else WARNING,
                         anchor="w", justify="left", wraplength=560
                         ).grid(row=1, column=0, padx=14, pady=(0,0), sticky="w")
            self._run_btn(card, "Apply", cmd, col, row=2, dangerous=danger)

    # ─── TOOLS TAB ────────────────────────────────────────────────────────────

    def _tab_tools(self, p):
        self._header(p, "System Tools", "Quick access to legacy Windows panels and settings.")

        card = self._card(p, 1)
        ctk.CTkLabel(card, text="Legacy Windows Panels",
                     font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                     text_color=ACCENT).grid(row=0, column=0, columnspan=3, padx=14, pady=(12,8), sticky="w")
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=1)
        card.grid_columnconfigure(2, weight=1)

        panels = [
            ("Computer Management", "compmgmt.msc"),
            ("Control Panel",       "control"),
            ("Network Connections",  "ncpa.cpl"),
            ("Power Panel",         "powercfg.cpl"),
            ("Printer Panel",       "printui /s"),
            ("Region",              "intl.cpl"),
            ("Sound Settings",      "mmsys.cpl"),
            ("System Properties",   "sysdm.cpl"),
            ("Time and Date",       "timedate.cpl"),
            ("Windows Restore",     "rstrui.exe"),
        ]

        for idx, (name, cmd) in enumerate(panels):
            c = idx % 3
            r = (idx // 3) + 1
            ctk.CTkButton(card, text=name,
                          font=ctk.CTkFont(family="Segoe UI", size=12),
                          fg_color=CARD2, hover_color=HOVER,
                          text_color=TEXT, corner_radius=8, height=36,
                          command=lambda c=cmd: self._op(lambda cb, cc=c: open_panel(cc, cb))
                          ).grid(row=r, column=c, padx=10, pady=5, sticky="ew")
        ctk.CTkFrame(card, fg_color="transparent", height=8).grid(row=999, column=0)

    # ─── RESTORE POINT TAB ────────────────────────────────────────────────────

    def _tab_restore(self, p):
        self._header(p, "Restore Point", "Manually create a Windows restore point.")

        card = self._card(p, 1)
        self._clabel(card, "Create Restore Point",
                     "Creates a Windows System Restore point right now.\n"
                     "Does not affect personal files, only system settings and registry.\n"
                     "Windows normally limits this to once per 24 hours, but WinForge can bypass that.")

        lf = ctk.CTkFrame(card, fg_color="transparent")
        lf.grid(row=2, column=0, padx=14, pady=(10,4), sticky="w")
        ctk.CTkLabel(lf, text="Description:",
                     font=ctk.CTkFont(family="Segoe UI", size=12), text_color=TEXT2
                     ).grid(row=0, column=0, padx=(0,8))
        self._rp_entry = ctk.CTkEntry(lf, width=300,
                                      font=ctk.CTkFont(family="Segoe UI", size=12),
                                      fg_color=BG, border_color=BORDER, text_color=TEXT,
                                      placeholder_text="WinForge Manual Restore Point")
        self._rp_entry.grid(row=0, column=1)

        ctk.CTkButton(card, text="Create Now",
                      font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                      fg_color=SUCCESS, hover_color=self._dk(SUCCESS),
                      text_color="#fff", corner_radius=8, height=36, width=140,
                      command=self._create_rp
                      ).grid(row=3, column=0, padx=14, pady=12, sticky="w")

    def _create_rp(self):
        desc = self._rp_entry.get().strip() or "WinForge Manual Restore Point"
        threading.Thread(target=lambda: create_restore_point(desc, self._log_line), daemon=True).start()
