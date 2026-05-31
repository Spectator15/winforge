import customtkinter as ctk
import threading, sys, os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.operations import *

# ─── THEME ────────────────────────────────────────────────────────────────────
BG      = "#0b0b0e"
PANEL   = "#101014"
CARD    = "#16161c"
CARD2   = "#1c1c24"
HOVER   = "#24242e"
ACCENT  = "#5b8dee"
ACCENT2 = "#3a5fb0"
OK      = "#3dcf6e"
WARN    = "#f0a020"
DANGER  = "#e04040"
DANGER2 = "#a02020"
TXT     = "#ededf5"
TXT2    = "#8888a0"
TXT3    = "#50506a"
BORD    = "#24243a"
PURPLE  = "#9b5de5"
FONT    = "Segoe UI"
MONO    = "Consolas"


class ToolTip:
    def __init__(self, widget, text):
        self.widget, self.text, self.tip, self._aid = widget, text, None, None
        self._bind_all(widget)

    def _bind_all(self, w):
        w.bind("<Enter>", self._sched_show, add="+")
        w.bind("<Leave>", self._do_hide, add="+")
        try:
            for c in w.winfo_children(): self._bind_all(c)
        except: pass

    def _sched_show(self, e=None):
        self._cancel()
        self._aid = self.widget.after(350, self._show)

    def _do_hide(self, e=None):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self._aid:
            self.widget.after_cancel(self._aid)
            self._aid = None

    def _show(self):
        self._hide()
        try:
            x, y = self.widget.winfo_rootx()+20, self.widget.winfo_rooty()+self.widget.winfo_height()+4
            self.tip = tw = ctk.CTkToplevel()
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            tw.configure(fg_color=CARD2)
            tw.attributes("-topmost", True)
            f = ctk.CTkFrame(tw, fg_color=CARD2, border_width=1, border_color=BORD, corner_radius=6)
            f.pack(padx=1, pady=1)
            ctk.CTkLabel(f, text=self.text, font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TXT2, wraplength=340, justify="left").pack(padx=10, pady=6)
        except: pass

    def _hide(self):
        if self.tip:
            try: self.tip.destroy()
            except: pass
            self.tip = None


class WinForgeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WinForge")
        self.geometry("1160x760")
        self.minsize(1000, 660)
        self.configure(fg_color=BG)
        self._tab = None
        self._tvars = {}
        self._bvars = {}
        self._avars = {}
        self._tips = []
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._sidebar()
        self._main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._main.grid(row=0, column=1, sticky="nsew")
        self._main.grid_columnconfigure(0, weight=1)
        self._main.grid_rowconfigure(1, weight=1)
        self._build_log()
        self._go("repair")

    # ─── SIDEBAR ──────────────────────────────────────────────────────────────

    def _sidebar(self):
        s = ctk.CTkFrame(self, fg_color=PANEL, width=215, corner_radius=0)
        s.grid(row=0, column=0, sticky="nsew"); s.grid_propagate(False); s.grid_rowconfigure(14, weight=1)
        lf = ctk.CTkFrame(s, fg_color="transparent")
        lf.grid(row=0, column=0, padx=16, pady=(20,4), sticky="ew")
        ctk.CTkLabel(lf, text="WinForge", font=ctk.CTkFont(family=FONT, size=22, weight="bold"),
                     text_color=ACCENT).pack(anchor="w")
        ctk.CTkLabel(lf, text="Made by Danish", font=ctk.CTkFont(family=FONT, size=10),
                     text_color=TXT3).pack(anchor="w")
        ctk.CTkFrame(s, fg_color=BORD, height=1).grid(row=1, column=0, sticky="ew", padx=12, pady=(6,12))
        tabs = [("repair","System Repair"),("cleanup","Cleanup"),("deps","Dependencies"),
                ("apps","Install Apps"),("tweaks","Tweaks"),("debloat","Debloat"),
                ("dns","DNS Settings"),("updates","Updates"),("tools","System Tools"),("restore","Restore Point")]
        self._btns = {}
        for i,(tid,lbl) in enumerate(tabs, 2):
            b = ctk.CTkButton(s, text=lbl, anchor="w", font=ctk.CTkFont(family=FONT, size=13),
                              fg_color="transparent", hover_color=HOVER, text_color=TXT2,
                              corner_radius=8, height=36, command=lambda t=tid: self._go(t))
            b.grid(row=i, column=0, padx=8, pady=1, sticky="ew")
            self._btns[tid] = b
        ctk.CTkLabel(s, text="v3.0  ·  admin", font=ctk.CTkFont(family=FONT, size=10),
                     text_color=TXT3).grid(row=15, column=0, padx=16, pady=12, sticky="sw")

    # ─── LOG ──────────────────────────────────────────────────────────────────

    def _build_log(self):
        lf = ctk.CTkFrame(self._main, fg_color=PANEL, corner_radius=8)
        lf.grid(row=2, column=0, sticky="ew", padx=12, pady=(0,10)); lf.grid_columnconfigure(0, weight=1)
        h = ctk.CTkFrame(lf, fg_color="transparent"); h.grid(row=0, column=0, sticky="ew", padx=10, pady=(6,0))
        h.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(h, text="Output Log", font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                     text_color=TXT2).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(h, text="Clear", width=50, height=20, font=ctk.CTkFont(family=FONT, size=10),
                      fg_color=CARD, hover_color=HOVER, text_color=TXT3, corner_radius=5,
                      command=self._clog).grid(row=0, column=2, sticky="e")
        self._logbox = ctk.CTkTextbox(lf, height=130, font=ctk.CTkFont(family=MONO, size=11),
                                      fg_color=BG, text_color=TXT, corner_radius=6, wrap="word", state="disabled")
        self._logbox.grid(row=1, column=0, sticky="ew", padx=6, pady=6)
        self._logbox.tag_config("ok", foreground=OK); self._logbox.tag_config("warn", foreground=WARN)
        self._logbox.tag_config("err", foreground=DANGER); self._logbox.tag_config("info", foreground=ACCENT)

    def _log(self, msg):
        def w():
            self._logbox.configure(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            tag = "ok" if any(x in msg for x in ["[OK]","success","complete","cleaned","created","enabled","disabled","removed","set to"]) else \
                  "warn" if "[WARN]" in msg else "err" if "[ERROR]" in msg or "fail" in msg.lower() else \
                  "info" if "[INFO]" in msg else None
            self._logbox.insert("end", f"[{ts}] {msg}\n", tag if tag else ())
            self._logbox.see("end"); self._logbox.configure(state="disabled")
        self.after(0, w)

    def _clog(self):
        self._logbox.configure(state="normal"); self._logbox.delete("1.0","end"); self._logbox.configure(state="disabled")

    # ─── NAV ──────────────────────────────────────────────────────────────────

    def _go(self, tid):
        for t in self._tips:
            t._cancel(); t._hide()
        self._tips = []
        if self._tab: self._tab.destroy()
        for k,b in self._btns.items():
            b.configure(fg_color=ACCENT2 if k==tid else "transparent", text_color=TXT if k==tid else TXT2)
        self.update_idletasks()
        f = ctk.CTkScrollableFrame(self._main, fg_color="transparent", corner_radius=0)
        f.grid(row=1, column=0, sticky="nsew", padx=12, pady=(6,4)); f.grid_columnconfigure(0, weight=1)
        self._tab = f
        {"repair":self._t_repair,"cleanup":self._t_cleanup,"deps":self._t_deps,
         "apps":self._t_apps,"tweaks":self._t_tweaks,"debloat":self._t_debloat,
         "dns":self._t_dns,"updates":self._t_updates,"tools":self._t_tools,"restore":self._t_restore}[tid](f)

    # ─── HELPERS ──────────────────────────────────────────────────────────────

    def _hdr(self, p, t, s="", r=0):
        f = ctk.CTkFrame(p, fg_color="transparent"); f.grid(row=r, column=0, sticky="ew", pady=(0,8))
        ctk.CTkLabel(f, text=t, font=ctk.CTkFont(family=FONT, size=18, weight="bold"), text_color=TXT).pack(anchor="w")
        if s: ctk.CTkLabel(f, text=s, font=ctk.CTkFont(family=FONT, size=11), text_color=TXT2).pack(anchor="w")

    def _crd(self, p, r, **kw):
        c = ctk.CTkFrame(p, fg_color=CARD, corner_radius=8, border_width=1, border_color=BORD)
        c.grid(row=r, column=0, sticky="ew", pady=kw.get("py",(0,6))); c.grid_columnconfigure(0, weight=1)
        return c

    def _dk(self, h):
        return "#{:02x}{:02x}{:02x}".format(*[int(int(h[i:i+2],16)*0.7) for i in (1,3,5)])

    def _op(self, fn):
        threading.Thread(target=lambda: fn(self._log), daemon=True).start()

    def _tt(self, w, t):
        tip = ToolTip(w, t); self._tips.append(tip)

    def _confirm(self, title, msg, danger=False):
        d = ctk.CTkToplevel(self); d.title(title); d.geometry("480x210"); d.configure(fg_color=CARD)
        d.grab_set(); ok = [False]
        ctk.CTkLabel(d, text=title, font=ctk.CTkFont(family=FONT, size=15, weight="bold"),
                     text_color=DANGER if danger else TXT).pack(pady=(18,4))
        ctk.CTkLabel(d, text=msg, font=ctk.CTkFont(family=FONT, size=11),
                     text_color=TXT2, wraplength=420, justify="center").pack(pady=6)
        bf = ctk.CTkFrame(d, fg_color="transparent"); bf.pack(pady=10)
        def y(): ok[0]=True; d.destroy()
        ctk.CTkButton(bf, text="Yes", fg_color=DANGER if danger else ACCENT, hover_color=DANGER2 if danger else ACCENT2,
                      text_color="#fff", corner_radius=8, height=34, width=110, command=y).grid(row=0, column=0, padx=6)
        ctk.CTkButton(bf, text="Cancel", fg_color=CARD2, hover_color=HOVER, text_color=TXT2,
                      corner_radius=8, height=34, width=90, command=d.destroy).grid(row=0, column=1, padx=6)
        d.wait_window(); return ok[0]

    # ─── REPAIR ───────────────────────────────────────────────────────────────

    def _t_repair(self, p):
        self._hdr(p, "System Repair", "Fix corrupted Windows files and components.")
        for i,(t,d,fn,c) in enumerate([
            ("DISM RestoreHealth","Repairs the component store. 5-15 min.",lambda: self._op(run_dism),ACCENT),
            ("System File Checker","Scans and repairs system files. Run after DISM.",lambda: self._op(run_sfc),ACCENT),
            ("Check Disk (CHKDSK)","Schedules disk integrity check on next boot.",lambda: self._op(run_chkdsk),WARN),
            ("Full Repair (DISM + SFC)","Creates restore point, runs DISM then SFC.",lambda: self._op(run_full_repair),OK),
        ], 1):
            cd = self._crd(p, i); cd.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(cd, text=t, font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                         text_color=TXT).grid(row=0, column=0, padx=12, pady=(10,0), sticky="w")
            ctk.CTkLabel(cd, text=d, font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TXT2).grid(row=1, column=0, padx=12, pady=(2,0), sticky="w")
            ctk.CTkButton(cd, text="Run", font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                          fg_color=c, hover_color=self._dk(c), text_color="#fff", corner_radius=7,
                          height=32, width=90, command=fn).grid(row=2, column=0, padx=12, pady=8, sticky="w")

    # ─── CLEANUP (GRID) ──────────────────────────────────────────────────────

    def _t_cleanup(self, p):
        self._hdr(p, "Cleanup", "Free up disk space and clear cached junk.")
        gf = ctk.CTkFrame(p, fg_color="transparent"); gf.grid(row=1, column=0, sticky="ew")
        gf.grid_columnconfigure(0, weight=1); gf.grid_columnconfigure(1, weight=1)
        items = list(CLEANUP_ITEMS.items())
        for idx,(cid,(name,desc,danger)) in enumerate(items):
            r, c = divmod(idx, 2)
            cd = ctk.CTkFrame(gf, fg_color=CARD, corner_radius=8, border_width=1, border_color=BORD)
            cd.grid(row=r, column=c, sticky="nsew", padx=(0 if c==0 else 4, 0 if c==1 else 4), pady=4)
            cd.grid_columnconfigure(0, weight=1)
            tc = DANGER if danger else TXT
            ctk.CTkLabel(cd, text=name, font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                         text_color=tc).grid(row=0, column=0, padx=12, pady=(10,0), sticky="w")
            ctk.CTkLabel(cd, text=desc, font=ctk.CTkFont(family=FONT, size=10),
                         text_color=TXT2, wraplength=280).grid(row=1, column=0, padx=12, pady=(2,0), sticky="w")
            fc = DANGER if danger else ACCENT
            ctk.CTkButton(cd, text="Run", font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                          fg_color=fc, hover_color=self._dk(fc), text_color="#fff", corner_radius=7,
                          height=30, width=80, command=lambda k=cid: self._op(CLEANUP_FNS[k])
                          ).grid(row=2, column=0, padx=12, pady=8, sticky="w")

    # ─── DEPS (GRID) ─────────────────────────────────────────────────────────

    def _t_deps(self, p):
        self._hdr(p, "Dependencies", "Install common Windows runtimes via winget.")
        gf = ctk.CTkFrame(p, fg_color="transparent"); gf.grid(row=1, column=0, sticky="ew")
        for c in range(3): gf.grid_columnconfigure(c, weight=1)
        for idx,(name,pkg) in enumerate(DEP_ITEMS):
            r, c = divmod(idx, 3)
            cd = ctk.CTkFrame(gf, fg_color=CARD, corner_radius=8, border_width=1, border_color=BORD)
            cd.grid(row=r, column=c, sticky="nsew", padx=3, pady=3); cd.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(cd, text=name, font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                         text_color=TXT).grid(row=0, column=0, padx=10, pady=(10,2), sticky="w")
            ctk.CTkLabel(cd, text=pkg, font=ctk.CTkFont(family=MONO, size=9),
                         text_color=TXT3).grid(row=1, column=0, padx=10, pady=(0,0), sticky="w")
            ctk.CTkButton(cd, text="Install", font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                          fg_color=ACCENT, hover_color=ACCENT2, text_color="#fff", corner_radius=7,
                          height=28, width=70, command=lambda pk=pkg: self._op(lambda cb: install_winget_pkg(pk, cb))
                          ).grid(row=2, column=0, padx=10, pady=8, sticky="w")

    # ─── INSTALL APPS ─────────────────────────────────────────────────────────

    def _t_apps(self, p):
        self._hdr(p, "Install Apps", "Select apps and install via winget or Chocolatey.")
        ctrl = ctk.CTkFrame(p, fg_color=CARD, corner_radius=8, border_width=1, border_color=BORD)
        ctrl.grid(row=1, column=0, sticky="ew", pady=(0,6)); ctrl.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(ctrl, text="Method:", font=ctk.CTkFont(family=FONT, size=12),
                     text_color=TXT2).grid(row=0, column=0, padx=(12,6), pady=10)
        self._method_var = ctk.StringVar(value="winget")
        ctk.CTkSegmentedButton(ctrl, values=["winget","chocolatey"], variable=self._method_var,
                               font=ctk.CTkFont(family=FONT, size=12), selected_color=ACCENT,
                               selected_hover_color=ACCENT2).grid(row=0, column=1, padx=4, pady=10, sticky="w")
        self._app_search = ctk.CTkEntry(ctrl, placeholder_text="Search apps...",
                                        font=ctk.CTkFont(family=FONT, size=12),
                                        fg_color=BG, border_color=BORD, text_color=TXT, width=220)
        self._app_search.grid(row=0, column=2, padx=12, pady=10, sticky="e")
        self._app_search.bind("<KeyRelease>", lambda e: self._filter_apps())
        bf = ctk.CTkFrame(ctrl, fg_color="transparent")
        bf.grid(row=0, column=3, padx=(0,12), pady=10)
        ctk.CTkButton(bf, text="Install Selected", font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                      fg_color=OK, hover_color=self._dk(OK), text_color="#fff", corner_radius=7,
                      height=32, width=130, command=self._install_apps).pack(side="left", padx=(0,6))
        ctk.CTkButton(bf, text="Clear", font=ctk.CTkFont(family=FONT, size=11),
                      fg_color=CARD2, hover_color=HOVER, text_color=TXT3, corner_radius=7,
                      height=32, width=60, command=lambda: [v.set(False) for v in self._avars.values()]).pack(side="left")

        self._app_frame = ctk.CTkFrame(p, fg_color="transparent")
        self._app_frame.grid(row=2, column=0, sticky="ew")
        self._build_app_grid()

    def _build_app_grid(self, filt=""):
        for w in self._app_frame.winfo_children(): w.destroy()
        for c in range(3): self._app_frame.grid_columnconfigure(c, weight=1)
        cats = {}
        for name, info in APP_LIST.items():
            if filt and filt.lower() not in name.lower(): continue
            cats.setdefault(info["cat"], []).append(name)
        row = 0
        for cat in sorted(cats.keys()):
            ctk.CTkLabel(self._app_frame, text=cat, font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                         text_color=ACCENT).grid(row=row, column=0, columnspan=3, padx=4, pady=(8,4), sticky="w")
            row += 1
            for idx, name in enumerate(sorted(cats[cat])):
                c = idx % 3; r = row + idx // 3
                if name not in self._avars: self._avars[name] = ctk.BooleanVar(value=False)
                ctk.CTkCheckBox(self._app_frame, text=name, variable=self._avars[name],
                                font=ctk.CTkFont(family=FONT, size=12), text_color=TXT,
                                fg_color=ACCENT, hover_color=ACCENT2, checkmark_color="#fff",
                                border_color=BORD).grid(row=r, column=c, padx=6, pady=3, sticky="w")
            row += (len(cats[cat]) + 2) // 3

    def _filter_apps(self):
        self._build_app_grid(self._app_search.get())

    def _install_apps(self):
        selected = [n for n,v in self._avars.items() if v.get()]
        if not selected: self._log("[WARN] No apps selected."); return
        method = self._method_var.get()
        def run():
            self._log(f"[INFO] Checking {method} availability...")
            if method == "winget":
                if not check_winget():
                    self._log("[INFO] winget not found. Installing...")
                    install_winget_itself(self._log)
            else:
                if not check_choco():
                    self._log("[INFO] Chocolatey not found. Installing...")
                    install_choco_itself(self._log)
            for name in selected:
                install_app(name, method, self._log)
            self._log(f"[OK] Installed {len(selected)} app(s).")
        threading.Thread(target=run, daemon=True).start()

    # ─── TWEAKS ───────────────────────────────────────────────────────────────

    def _t_tweaks(self, p):
        self._hdr(p, "Tweaks", "Hover any item for details. Use search or presets.")
        # Search + presets
        ctrl = ctk.CTkFrame(p, fg_color=CARD, corner_radius=8, border_width=1, border_color=BORD)
        ctrl.grid(row=1, column=0, sticky="ew", pady=(0,6)); ctrl.grid_columnconfigure(1, weight=1)
        self._tw_search = ctk.CTkEntry(ctrl, placeholder_text="Search tweaks...",
                                       font=ctk.CTkFont(family=FONT, size=12),
                                       fg_color=BG, border_color=BORD, text_color=TXT, width=220)
        self._tw_search.grid(row=0, column=0, padx=12, pady=10)
        self._tw_search.bind("<KeyRelease>", lambda e: self._filter_tweaks())
        pf = ctk.CTkFrame(ctrl, fg_color="transparent")
        pf.grid(row=0, column=1, padx=4, pady=10, sticky="w")
        for i,(name,_) in enumerate(PRESETS.items()):
            cols = [ACCENT, OK, WARN, PURPLE]
            c = cols[i%4]
            ctk.CTkButton(pf, text=name, font=ctk.CTkFont(family=FONT, size=11),
                          fg_color=c, hover_color=self._dk(c), text_color="#fff", corner_radius=7,
                          height=28, command=lambda n=name: self._load_preset(n)).pack(side="left", padx=2)
        bf = ctk.CTkFrame(ctrl, fg_color="transparent")
        bf.grid(row=0, column=2, padx=12, pady=10)
        ctk.CTkButton(bf, text="Apply", font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                      fg_color=OK, hover_color=self._dk(OK), text_color="#fff", corner_radius=7,
                      height=30, width=80, command=self._apply_tweaks).pack(side="left", padx=(0,4))
        ctk.CTkButton(bf, text="Clear", font=ctk.CTkFont(family=FONT, size=11),
                      fg_color=CARD2, hover_color=HOVER, text_color=TXT3, corner_radius=7,
                      height=30, width=55, command=lambda: [v.set(False) for v in self._tvars.values()]).pack(side="left")

        self._tw_frame = ctk.CTkFrame(p, fg_color="transparent")
        self._tw_frame.grid(row=2, column=0, sticky="ew")
        self._build_tweak_grid()

    def _build_tweak_grid(self, filt=""):
        for w in self._tw_frame.winfo_children(): w.destroy()
        self._tw_frame.grid_columnconfigure(0, weight=1); self._tw_frame.grid_columnconfigure(1, weight=1)
        row = 0
        for sect, cat, color in [("Essential Tweaks","essential",ACCENT),
                                  ("Advanced Tweaks  -  CAUTION","advanced",DANGER),
                                  ("Preferences","preference",PURPLE)]:
            items = [(k,v) for k,v in TWEAKS.items() if v["cat"]==cat and (not filt or filt.lower() in v["label"].lower())]
            if not items: continue
            ctk.CTkLabel(self._tw_frame, text=sect, font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
                         text_color=color).grid(row=row, column=0, columnspan=2, padx=4, pady=(8,4), sticky="w")
            row += 1
            for idx,(tid,td) in enumerate(items):
                c = idx % 2; r = row + idx // 2
                if tid not in self._tvars: self._tvars[tid] = ctk.BooleanVar(value=False)
                fc = DANGER if td["danger"] else ACCENT
                cb = ctk.CTkCheckBox(self._tw_frame, text=td["label"], variable=self._tvars[tid],
                                     font=ctk.CTkFont(family=FONT, size=12),
                                     text_color=DANGER if td["danger"] else TXT,
                                     fg_color=fc, hover_color=self._dk(fc), checkmark_color="#fff", border_color=BORD)
                cb.grid(row=r, column=c, padx=10, pady=4, sticky="w")
                self._tt(cb, td["tip"])
            row += (len(items)+1)//2

    def _filter_tweaks(self):
        self._build_tweak_grid(self._tw_search.get())

    def _load_preset(self, name):
        sel = PRESETS.get(name,{}).get("tweaks",[])
        for tid,var in self._tvars.items(): var.set(tid in sel)
        self._log(f"[INFO] Preset '{name}' loaded.")

    def _apply_tweaks(self):
        sel = [t for t,v in self._tvars.items() if v.get()]
        if not sel: self._log("[WARN] No tweaks selected."); return
        danger = [t for t in sel if TWEAKS[t]["danger"]]
        if danger:
            labels = ", ".join(TWEAKS[t]["label"] for t in danger)
            if not self._confirm("Dangerous Tweaks", f"These are marked dangerous:\n{labels}\n\nRestore point will be created first. Continue?", True):
                return
        def run():
            self._log(f"[INFO] Creating restore point...")
            create_restore_point("WinForge Tweaks", self._log)
            for tid in sel: TWEAKS[tid]["fn"](self._log)
            self._log(f"[OK] {len(sel)} tweak(s) applied.")
        threading.Thread(target=run, daemon=True).start()

    # ─── DEBLOAT ──────────────────────────────────────────────────────────────

    def _t_debloat(self, p):
        self._hdr(p, "Debloat", "Remove pre-installed apps and browser bloat.")
        # Browser debloat section
        bc = self._crd(p, 1)
        ctk.CTkLabel(bc, text="Browser Debloat", font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                     text_color=ACCENT).grid(row=0, column=0, columnspan=2, padx=12, pady=(10,4), sticky="w")
        ctk.CTkLabel(bc, text="Disables telemetry, shopping, sidebar, and other bloat baked into browsers.",
                     font=ctk.CTkFont(family=FONT, size=10), text_color=TXT2
                     ).grid(row=1, column=0, columnspan=2, padx=12, pady=(0,6), sticky="w")
        bc.grid_columnconfigure(0, weight=1); bc.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(bc, text="Debloat Edge", font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                      fg_color=ACCENT, hover_color=ACCENT2, text_color="#fff", corner_radius=7,
                      height=30, command=lambda: self._op(debloat_edge)).grid(row=2, column=0, padx=12, pady=8, sticky="w")
        ctk.CTkButton(bc, text="Debloat Brave", font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                      fg_color=ACCENT, hover_color=ACCENT2, text_color="#fff", corner_radius=7,
                      height=30, command=lambda: self._op(debloat_brave)).grid(row=2, column=1, padx=12, pady=8, sticky="w")

        # App removal
        self._bvars = {}
        for section_title, apps, is_danger, row in [
            ("Safe to Remove", {k:v for k,v in BLOATWARE.items() if not v[1]}, False, 2),
            ("Sensitive  -  CAUTION", {k:v for k,v in BLOATWARE.items() if v[1]}, True, 3),
        ]:
            sc = self._crd(p, row)
            lc = DANGER if is_danger else ACCENT
            ctk.CTkLabel(sc, text=section_title, font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                         text_color=lc).grid(row=0, column=0, columnspan=2, padx=12, pady=(10,6), sticky="w")
            sc.grid_columnconfigure(0, weight=1); sc.grid_columnconfigure(1, weight=1)
            for idx,(pkg,(name,_,tip)) in enumerate(apps.items()):
                c = idx%2; r = (idx//2)+1
                self._bvars[pkg] = ctk.BooleanVar(value=False)
                fc = DANGER if is_danger else ACCENT
                cb = ctk.CTkCheckBox(sc, text=name, variable=self._bvars[pkg],
                                     font=ctk.CTkFont(family=FONT, size=12),
                                     text_color=DANGER if is_danger else TXT,
                                     fg_color=fc, hover_color=self._dk(fc), checkmark_color="#fff", border_color=BORD)
                cb.grid(row=r, column=c, padx=10, pady=3, sticky="w")
                self._tt(cb, tip)
            ctk.CTkFrame(sc, fg_color="transparent", height=4).grid(row=999, column=0)

        bf = ctk.CTkFrame(p, fg_color="transparent"); bf.grid(row=4, column=0, sticky="ew", pady=(4,0))
        ctk.CTkButton(bf, text="Select All Safe", font=ctk.CTkFont(family=FONT, size=11),
                      fg_color=ACCENT, hover_color=ACCENT2, text_color="#fff", corner_radius=7,
                      height=30, command=lambda: [self._bvars[k].set(True) for k in BLOATWARE if not BLOATWARE[k][1]]
                      ).grid(row=0, column=0, padx=(0,6))
        ctk.CTkButton(bf, text="Clear", font=ctk.CTkFont(family=FONT, size=11),
                      fg_color=CARD2, hover_color=HOVER, text_color=TXT3, corner_radius=7,
                      height=30, command=lambda: [v.set(False) for v in self._bvars.values()]
                      ).grid(row=0, column=1, padx=(0,6))
        ctk.CTkButton(bf, text="Remove Selected", font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                      fg_color=DANGER, hover_color=DANGER2, text_color="#fff", corner_radius=7,
                      height=34, width=150, command=self._run_debloat).grid(row=0, column=2)

    def _run_debloat(self):
        sel = [p for p,v in self._bvars.items() if v.get()]
        if not sel: self._log("[WARN] No apps selected."); return
        names = ", ".join(BLOATWARE[p][0] for p in sel)
        if not self._confirm("Confirm Removal", f"Remove {len(sel)} app(s)?\n{names[:250]}{'...' if len(names)>250 else ''}\n\nRestore point created first.",
                             any(BLOATWARE[p][1] for p in sel)):
            return
        def run():
            create_restore_point("WinForge Debloat", self._log)
            for pkg in sel: remove_app(pkg, self._log)
            self._log(f"[OK] {len(sel)} app(s) removed.")
        threading.Thread(target=run, daemon=True).start()

    # ─── DNS ──────────────────────────────────────────────────────────────────

    def _t_dns(self, p):
        self._hdr(p, "DNS Settings", "Choose a DNS server and apply it to all active network adapters.")
        self._dns_var = ctk.StringVar(value="Cloudflare (1.1.1.1)")
        gf = ctk.CTkFrame(p, fg_color="transparent"); gf.grid(row=1, column=0, sticky="ew")
        for c in range(2): gf.grid_columnconfigure(c, weight=1)
        dns_info = {
            "Cloudflare (1.1.1.1)":       "Fast and privacy-focused. No logging.",
            "Google (8.8.8.8)":            "Very reliable. Google logs queries.",
            "Quad9 (9.9.9.9)":             "Blocks malware domains. Privacy-focused.",
            "OpenDNS (208.67.222.222)":    "Cisco-owned. Optional content filtering.",
            "AdGuard (94.140.14.14)":      "Blocks ads and trackers at DNS level.",
            "Cloudflare Family (1.1.1.3)": "Cloudflare + blocks malware and adult content.",
            "Automatic (DHCP)":            "Uses your router/ISP default DNS.",
        }
        for idx, (name, (pri, sec)) in enumerate(DNS_SERVERS.items()):
            r, c = divmod(idx, 2)
            cd = ctk.CTkFrame(gf, fg_color=CARD, corner_radius=8, border_width=1, border_color=BORD)
            cd.grid(row=r, column=c, sticky="nsew", padx=3, pady=3); cd.grid_columnconfigure(1, weight=1)
            rb = ctk.CTkRadioButton(cd, text=name, variable=self._dns_var, value=name,
                                    font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                                    text_color=TXT, fg_color=ACCENT, border_color=BORD)
            rb.grid(row=0, column=0, columnspan=2, padx=12, pady=(10,0), sticky="w")
            ips = f"{pri}, {sec}" if pri else "Automatic"
            ctk.CTkLabel(cd, text=ips, font=ctk.CTkFont(family=MONO, size=10),
                         text_color=TXT3).grid(row=1, column=0, columnspan=2, padx=28, pady=(0,0), sticky="w")
            ctk.CTkLabel(cd, text=dns_info.get(name,""), font=ctk.CTkFont(family=FONT, size=10),
                         text_color=TXT2, wraplength=280).grid(row=2, column=0, columnspan=2, padx=28, pady=(2,10), sticky="w")

        ctk.CTkButton(p, text="Apply DNS", font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                      fg_color=ACCENT, hover_color=ACCENT2, text_color="#fff", corner_radius=7,
                      height=36, width=140, command=lambda: self._op(lambda cb: set_dns(self._dns_var.get(), cb))
                      ).grid(row=2, column=0, pady=(8,4), sticky="w")

    # ─── UPDATES ──────────────────────────────────────────────────────────────

    def _t_updates(self, p):
        self._hdr(p, "Windows Updates", "Control how Windows installs updates.")
        configs = [
            ("Default Settings", ACCENT, False,
             "Resets Windows Update to out-of-the-box defaults.\nRemoves all custom update policies.",
             lambda: self._op(updates_default)),
            ("Security Settings", OK, False,
             "Feature updates delayed 365 days.\nSecurity updates after 4 days.\nDriver updates via WU disabled.\nNote: Pro/Enterprise only.",
             lambda: self._op(updates_security)),
            ("Disable All Updates", DANGER, True,
             "NOT RECOMMENDED\nDisables ALL updates completely.\nIncreases security risk.\nOnly for isolated/test systems.",
             lambda: self._op(updates_disable)),
        ]
        for i,(t,col,dan,d,cmd) in enumerate(configs, 1):
            cd = self._crd(p, i); cd.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(cd, text=t, font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
                         text_color=DANGER if dan else TXT).grid(row=0, column=0, padx=12, pady=(10,2), sticky="w")
            ctk.CTkLabel(cd, text=d, font=ctk.CTkFont(family=FONT, size=11),
                         text_color=WARN if dan else TXT2, justify="left"
                         ).grid(row=1, column=0, padx=12, pady=(0,0), sticky="w")
            fc = DANGER if dan else col
            ctk.CTkButton(cd, text="Apply", font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                          fg_color=fc, hover_color=self._dk(fc), text_color="#fff", corner_radius=7,
                          height=30, width=90, command=cmd).grid(row=2, column=0, padx=12, pady=8, sticky="w")

    # ─── TOOLS ────────────────────────────────────────────────────────────────

    def _t_tools(self, p):
        self._hdr(p, "System Tools", "Quick access to legacy Windows panels.")
        cd = self._crd(p, 1)
        ctk.CTkLabel(cd, text="Legacy Windows Panels", font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                     text_color=ACCENT).grid(row=0, column=0, columnspan=3, padx=12, pady=(10,6), sticky="w")
        for c in range(3): cd.grid_columnconfigure(c, weight=1)
        panels = [("Computer Management","compmgmt.msc"),("Control Panel","control"),
                  ("Network Connections","ncpa.cpl"),("Power Panel","powercfg.cpl"),
                  ("Printer Panel","printui /s"),("Region","intl.cpl"),
                  ("Sound Settings","mmsys.cpl"),("System Properties","sysdm.cpl"),
                  ("Time and Date","timedate.cpl"),("Windows Restore","rstrui.exe")]
        for idx,(name,cmd) in enumerate(panels):
            r, c = 1+idx//3, idx%3
            ctk.CTkButton(cd, text=name, font=ctk.CTkFont(family=FONT, size=11),
                          fg_color=CARD2, hover_color=HOVER, text_color=TXT, corner_radius=7,
                          height=34, command=lambda cc=cmd: self._op(lambda cb: open_panel(cc, cb))
                          ).grid(row=r, column=c, padx=6, pady=4, sticky="ew")
        ctk.CTkFrame(cd, fg_color="transparent", height=6).grid(row=99, column=0)

    # ─── RESTORE ──────────────────────────────────────────────────────────────

    def _t_restore(self, p):
        self._hdr(p, "Restore Point", "Manually create a Windows restore point.")
        cd = self._crd(p, 1)
        ctk.CTkLabel(cd, text="Create Restore Point", font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                     text_color=TXT).grid(row=0, column=0, padx=12, pady=(10,0), sticky="w")
        ctk.CTkLabel(cd, text="Creates a system restore point. Bypasses the 24-hour limit.\nDoes not affect personal files.",
                     font=ctk.CTkFont(family=FONT, size=11), text_color=TXT2, justify="left"
                     ).grid(row=1, column=0, padx=12, pady=(2,6), sticky="w")
        ef = ctk.CTkFrame(cd, fg_color="transparent"); ef.grid(row=2, column=0, padx=12, pady=(0,4), sticky="w")
        ctk.CTkLabel(ef, text="Label:", font=ctk.CTkFont(family=FONT, size=11), text_color=TXT2).grid(row=0, column=0, padx=(0,6))
        self._rpe = ctk.CTkEntry(ef, width=280, font=ctk.CTkFont(family=FONT, size=12),
                                 fg_color=BG, border_color=BORD, text_color=TXT,
                                 placeholder_text="WinForge Manual Restore Point")
        self._rpe.grid(row=0, column=1)
        ctk.CTkButton(cd, text="Create Now", font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                      fg_color=OK, hover_color=self._dk(OK), text_color="#fff", corner_radius=7,
                      height=32, width=120,
                      command=lambda: self._op(lambda cb: create_restore_point(self._rpe.get().strip() or "WinForge Manual", cb))
                      ).grid(row=3, column=0, padx=12, pady=10, sticky="w")
