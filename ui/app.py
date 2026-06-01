import customtkinter as ctk
import threading, sys, os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.operations import *

# ─── THEME (artifact-free, solid fills, no gradients) ─────────────────────────
BG="#0b0b0e"; PANEL="#0f0f14"; CARD="#151519"; CARD2="#1a1a20"; HOVER="#222230"
ACCENT="#5b8dee"; ACCENT2="#3a5fb0"; OK="#3dcf6e"; WARN="#f0a020"
DANGER="#e04040"; DANGER2="#a02020"; TXT="#ededf5"; TXT2="#8888a0"; TXT3="#50506a"
BORD="#1e1e30"; PURPLE="#9b5de5"; FONT="Segoe UI"; MONO="Consolas"

class ToolTip:
    def __init__(s,w,t):
        s.w,s.t,s.tip,s._id=w,t,None,None; s._ba(w)
    def _ba(s,w):
        w.bind("<Enter>",s._ss,add="+"); w.bind("<Leave>",s._dh,add="+")
        try:
            for c in w.winfo_children(): s._ba(c)
        except: pass
    def _ss(s,e=None): s._c(); s._id=s.w.after(350,s._sh)
    def _dh(s,e=None): s._c(); s._h()
    def _c(s):
        if s._id: s.w.after_cancel(s._id); s._id=None
    def _sh(s):
        s._h()
        try:
            x,y=s.w.winfo_rootx()+20,s.w.winfo_rooty()+s.w.winfo_height()+4
            s.tip=tw=ctk.CTkToplevel(); tw.wm_overrideredirect(True); tw.wm_geometry(f"+{x}+{y}")
            tw.configure(fg_color=CARD2); tw.attributes("-topmost",True)
            f=ctk.CTkFrame(tw,fg_color=CARD2,border_width=1,border_color=BORD,corner_radius=6); f.pack(padx=1,pady=1)
            ctk.CTkLabel(f,text=s.t,font=ctk.CTkFont(family=FONT,size=11),text_color=TXT2,wraplength=340,justify="left").pack(padx=10,pady=6)
        except: pass
    def _h(s):
        if s.tip:
            try: s.tip.destroy()
            except: pass
            s.tip=None

class WinForgeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WinForge"); self.geometry("1160x760"); self.minsize(1000,660)
        self.configure(fg_color=BG)
        self._tab=None; self._tvars={}; self._bvars={}; self._avars={}; self._tips=[]
        self.grid_columnconfigure(1,weight=1); self.grid_rowconfigure(0,weight=1)
        self._sidebar()
        self._main=ctk.CTkFrame(self,fg_color=BG,corner_radius=0)
        self._main.grid(row=0,column=1,sticky="nsew")
        self._main.grid_columnconfigure(0,weight=1); self._main.grid_rowconfigure(1,weight=1)
        self._build_log()
        self._go("sysinfo")

    def _sidebar(self):
        s=ctk.CTkFrame(self,fg_color=PANEL,width=215,corner_radius=0)
        s.grid(row=0,column=0,sticky="nsew"); s.grid_propagate(False); s.grid_rowconfigure(14,weight=1)
        lf=ctk.CTkFrame(s,fg_color="transparent")
        lf.grid(row=0,column=0,padx=16,pady=(20,4),sticky="ew")
        ctk.CTkLabel(lf,text="WinForge",font=ctk.CTkFont(family=FONT,size=22,weight="bold"),text_color=ACCENT).pack(anchor="w")
        ctk.CTkLabel(lf,text="Made by Danish",font=ctk.CTkFont(family=FONT,size=10),text_color=TXT3).pack(anchor="w")
        ctk.CTkFrame(s,fg_color=BORD,height=1).grid(row=1,column=0,sticky="ew",padx=12,pady=(6,12))
        tabs=[("sysinfo","System Info"),("repair","System Repair"),("cleanup","Cleanup"),("deps","Dependencies"),
              ("apps","Install Apps"),("tweaks","Tweaks & Debloat"),
              ("dns","DNS Settings"),("updates","Updates"),("registry","Registry Health"),
              ("tools","System Tools"),("restore","Restore Point")]
        self._btns={}
        for i,(tid,lbl) in enumerate(tabs,2):
            b=ctk.CTkButton(s,text=lbl,anchor="w",font=ctk.CTkFont(family=FONT,size=13),
                fg_color="transparent",hover_color=HOVER,text_color=TXT2,corner_radius=8,height=36,
                command=lambda t=tid: self._go(t))
            b.grid(row=i,column=0,padx=8,pady=1,sticky="ew"); self._btns[tid]=b
        ctk.CTkLabel(s,text="v4.0  ·  admin",font=ctk.CTkFont(family=FONT,size=10),
            text_color=TXT3).grid(row=15,column=0,padx=16,pady=12,sticky="sw")

    def _build_log(self):
        self._log_visible = True
        self._log_frame = ctk.CTkFrame(self._main, fg_color=PANEL, corner_radius=8)
        self._log_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0,10))
        self._log_frame.grid_columnconfigure(0, weight=1)

        h = ctk.CTkFrame(self._log_frame, fg_color="transparent")
        h.grid(row=0, column=0, sticky="ew", padx=10, pady=(6,0))
        h.grid_columnconfigure(1, weight=1)

        self._log_toggle = ctk.CTkButton(h, text="▼ Output Log", width=120, height=22,
            font=ctk.CTkFont(family=FONT, size=11, weight="bold"), fg_color="transparent",
            hover_color=HOVER, text_color=TXT2, corner_radius=5, anchor="w",
            command=self._toggle_log)
        self._log_toggle.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(h, text="Clear", width=50, height=20,
            font=ctk.CTkFont(family=FONT, size=10), fg_color=CARD, hover_color=HOVER,
            text_color=TXT3, corner_radius=5, command=self._clog).grid(row=0, column=2, sticky="e")

        self._logbox = ctk.CTkTextbox(self._log_frame, height=130,
            font=ctk.CTkFont(family=MONO, size=11), fg_color=BG, text_color=TXT,
            corner_radius=6, wrap="word", state="disabled")
        self._logbox.grid(row=1, column=0, sticky="ew", padx=6, pady=6)
        self._logbox.tag_config("ok", foreground=OK)
        self._logbox.tag_config("warn", foreground=WARN)
        self._logbox.tag_config("err", foreground=DANGER)
        self._logbox.tag_config("info", foreground=ACCENT)

        # Toast container (bottom right)
        self._toast_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._toast_frame.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-20)
        self._toasts = []

    def _toggle_log(self):
        if self._log_visible:
            self._logbox.grid_remove()
            self._log_toggle.configure(text="▶ Output Log")
        else:
            self._logbox.grid()
            self._log_toggle.configure(text="▼ Output Log")
        self._log_visible = not self._log_visible

    def _log(self,msg):
        def w():
            self._logbox.configure(state="normal")
            ts=datetime.now().strftime("%H:%M:%S")
            tag="ok" if any(x in msg for x in ["[OK]","success","complete","cleaned","created","enabled","disabled","removed","set to"]) else \
                "warn" if "[WARN]" in msg else "err" if "[ERROR]" in msg or "fail" in msg.lower() else \
                "info" if "[INFO]" in msg else None
            self._logbox.insert("end",f"[{ts}] {msg}\n",tag if tag else ())
            self._logbox.see("end"); self._logbox.configure(state="disabled")
            # Trigger toast on completion messages
            if tag == "ok" and any(x in msg for x in ["complete","applied","removed","installed","cleaned","created","copied","reset","configured","debloated"]):
                clean_msg = msg.replace("[OK] ","").strip()
                self._show_toast(clean_msg, OK)
            elif tag == "warn" and "[WARN]" in msg:
                clean_msg = msg.replace("[WARN] ","").strip()
                self._show_toast(clean_msg, WARN)
        self.after(0,w)
    def _clog(self):
        self._logbox.configure(state="normal"); self._logbox.delete("1.0","end"); self._logbox.configure(state="disabled")

    def _show_toast(self, msg, color=OK):
        """Show a notification toast at bottom-right that fades after 5 seconds."""
        toast = ctk.CTkFrame(self._toast_frame, fg_color=CARD2, corner_radius=8,
                             border_width=1, border_color=color)
        toast.pack(side="bottom", anchor="e", pady=3, padx=0)

        bar = ctk.CTkFrame(toast, fg_color=color, width=4, corner_radius=2)
        bar.pack(side="left", fill="y", padx=(0,0))

        ctk.CTkLabel(toast, text=msg, font=ctk.CTkFont(family=FONT, size=11),
                     text_color=TXT, wraplength=300, justify="left").pack(side="left", padx=(8,12), pady=8)

        self._toasts.append(toast)
        self.after(5000, lambda t=toast: self._dismiss_toast(t))

    def _dismiss_toast(self, toast):
        try:
            toast.destroy()
            if toast in self._toasts:
                self._toasts.remove(toast)
        except: pass

    def _go(self,tid):
        for t in self._tips: t._c(); t._h()
        self._tips=[]
        if self._tab: self._tab.destroy()
        for k,b in self._btns.items():
            b.configure(fg_color=ACCENT2 if k==tid else "transparent",text_color=TXT if k==tid else TXT2)
        self.update_idletasks()
        f=ctk.CTkScrollableFrame(self._main,fg_color="transparent",corner_radius=0)
        f.grid(row=1,column=0,sticky="nsew",padx=12,pady=(6,4)); f.grid_columnconfigure(0,weight=1)
        self._tab=f
        {"sysinfo":self._t_sysinfo,"repair":self._t_repair,"cleanup":self._t_cleanup,"deps":self._t_deps,
         "apps":self._t_apps,"tweaks":self._t_tweaks,"dns":self._t_dns,
         "updates":self._t_updates,"registry":self._t_registry,
         "tools":self._t_tools,"restore":self._t_restore}[tid](f)

    # helpers
    def _hdr(s,p,t,sub="",r=0):
        f=ctk.CTkFrame(p,fg_color="transparent"); f.grid(row=r,column=0,sticky="ew",pady=(0,8))
        ctk.CTkLabel(f,text=t,font=ctk.CTkFont(family=FONT,size=18,weight="bold"),text_color=TXT).pack(anchor="w")
        if sub: ctk.CTkLabel(f,text=sub,font=ctk.CTkFont(family=FONT,size=11),text_color=TXT2).pack(anchor="w")
    def _crd(s,p,r,**kw):
        c=ctk.CTkFrame(p,fg_color=CARD,corner_radius=8,border_width=0); c.grid(row=r,column=0,sticky="ew",pady=kw.get("py",(0,6))); c.grid_columnconfigure(0,weight=1); return c
    def _dk(s,h): return "#{:02x}{:02x}{:02x}".format(*[int(int(h[i:i+2],16)*0.7) for i in (1,3,5)])
    def _op(s,fn): threading.Thread(target=lambda: fn(s._log),daemon=True).start()
    def _tt(s,w,t): tip=ToolTip(w,t); s._tips.append(tip)

    def _confirm(s,title,msg,danger=False):
        d=ctk.CTkToplevel(s); d.title(title); d.geometry("480x210"); d.configure(fg_color=CARD)
        d.grab_set(); ok=[False]
        ctk.CTkLabel(d,text=title,font=ctk.CTkFont(family=FONT,size=15,weight="bold"),
            text_color=DANGER if danger else TXT).pack(pady=(18,4))
        ctk.CTkLabel(d,text=msg,font=ctk.CTkFont(family=FONT,size=11),text_color=TXT2,wraplength=420,justify="center").pack(pady=6)
        bf=ctk.CTkFrame(d,fg_color="transparent"); bf.pack(pady=10)
        def y(): ok[0]=True; d.destroy()
        ctk.CTkButton(bf,text="Yes",fg_color=DANGER if danger else ACCENT,hover_color=DANGER2 if danger else ACCENT2,
            text_color="#fff",corner_radius=8,height=34,width=110,command=y).grid(row=0,column=0,padx=6)
        ctk.CTkButton(bf,text="Cancel",fg_color=CARD2,hover_color=HOVER,text_color=TXT2,
            corner_radius=8,height=34,width=90,command=d.destroy).grid(row=0,column=1,padx=6)
        d.wait_window(); return ok[0]

    def _maybe_restore_point(s, label="WinForge Operation"):
        """Smart restore point: asks user if one was already created this session."""
        if was_restore_created_this_session():
            return s._confirm("Restore Point", "A restore point was already created this session.\nCreate another one before proceeding?", False)
        create_restore_point(label, s._log)
        return True

    # ─── SYSTEM INFO ────────────────────────────────────────────────────────
    def _t_sysinfo(s,p):
        s._hdr(p,"System Info","Your hardware and system details.")
        loading=s._crd(p,1)
        ctk.CTkLabel(loading,text="Loading system information...",font=ctk.CTkFont(family=FONT,size=13),text_color=TXT2).grid(row=0,column=0,padx=12,pady=12,sticky="w")
        def fetch():
            info=get_system_info(s._log)
            s.after(0,lambda: s._render_sysinfo(p,info))
        threading.Thread(target=fetch,daemon=True).start()

    def _render_sysinfo(s,p,info):
        # Clear everything except header
        children = p.winfo_children()
        for w in children[1:]: w.destroy()

        sections=[
            ("Operating System",[
                ("OS",info.get("os_name","Unknown")),
                ("Version",f"{info.get('os_build','?')} (Build {info.get('os_version','?')})"),
                ("Architecture",info.get("os_arch","?")),
                ("Installed",info.get("install_date","?")),
                ("Uptime",info.get("uptime","?")),
            ]),
            ("Processor",[
                ("CPU",info.get("cpu_name","Unknown")),
                ("Cores / Threads",f"{info.get('cpu_cores','?')} cores / {info.get('cpu_threads','?')} threads"),
                ("Max Clock",f"{info.get('cpu_clock','?')} GHz"),
            ]),
            ("Memory",[
                ("Total RAM",info.get("ram_total","?")),
                ("Speed",info.get("ram_speed","?")),
                ("Type",info.get("ram_type","?")),
                ("Configuration",info.get("ram_sticks","?")),
            ]),
            ("Graphics",[
                ("GPU",info.get("gpu","Unknown")),
                ("Driver Version",info.get("gpu_driver","?")),
            ]),
            ("Storage",[
                ("Drives",info.get("storage_drives","?")),
                ("Partitions",info.get("partitions","?")),
            ]),
            ("Motherboard & BIOS",[
                ("Motherboard",info.get("motherboard","?")),
                ("BIOS",info.get("bios","?")),
            ]),
            ("Security",[
                ("Secure Boot",info.get("secure_boot","?")),
                ("TPM",info.get("tpm","?")),
                ("Windows Defender",info.get("defender","?")),
                ("Definitions Updated",info.get("defender_updated","?")),
            ]),
            ("Network",[
                ("Active Adapter",info.get("network_adapter","?")),
                ("Link Speed",info.get("network_speed","?")),
                ("MAC Address",info.get("mac","?")),
            ]),
            ("Power",[
                ("Active Plan",info.get("power_plan","?")),
            ]),
        ]
        row=1
        LABEL_W = 180
        for sect_name,fields in sections:
            cd=ctk.CTkFrame(p,fg_color=CARD,corner_radius=8)
            cd.grid(row=row,column=0,sticky="ew",pady=(0,4)); row+=1
            cd.grid_columnconfigure(0,minsize=LABEL_W)
            cd.grid_columnconfigure(1,weight=1)
            ctk.CTkLabel(cd,text=sect_name,font=ctk.CTkFont(family=FONT,size=13,weight="bold"),text_color=ACCENT).grid(row=0,column=0,columnspan=2,padx=12,pady=(8,2),sticky="w")
            for fi,(label,value) in enumerate(fields,1):
                ctk.CTkLabel(cd,text=label,font=ctk.CTkFont(family=FONT,size=11),text_color=TXT3,anchor="w").grid(row=fi,column=0,padx=(20,0),pady=2,sticky="w")
                ctk.CTkLabel(cd,text=value,font=ctk.CTkFont(family=FONT,size=11),text_color=TXT,anchor="w",wraplength=550,justify="left").grid(row=fi,column=1,padx=(0,12),pady=2,sticky="w")
            ctk.CTkFrame(cd,fg_color=CARD,height=6).grid(row=99,column=0,columnspan=2,sticky="ew")

        # Bind scroll to all children so scrolling works over cards
        s._bind_scroll_recursive(p)

        # Copy button
        def copy_all():
            text=[]
            for sect_name,fields in sections:
                text.append(f"── {sect_name} ──")
                for label,value in fields: text.append(f"  {label}: {value}")
                text.append("")
            s.clipboard_clear(); s.clipboard_append("\n".join(text))
            s._log("[OK] System info copied to clipboard.")
        ctk.CTkButton(p,text="Copy to Clipboard",font=ctk.CTkFont(family=FONT,size=12,weight="bold"),fg_color=ACCENT,hover_color=ACCENT2,text_color="#fff",corner_radius=7,height=34,width=160,command=copy_all).grid(row=row,column=0,pady=(6,4),sticky="w")

    def _bind_scroll_recursive(s, widget):
        """Bind mousewheel to all children so scrolling works over cards inside ScrollableFrame."""
        try:
            for child in widget.winfo_children():
                child.bind("<MouseWheel>", lambda e: s._tab._parent_canvas.yview_scroll(-int(e.delta/120), "units"), add="+")
                child.bind("<Button-4>", lambda e: s._tab._parent_canvas.yview_scroll(-1, "units"), add="+")
                child.bind("<Button-5>", lambda e: s._tab._parent_canvas.yview_scroll(1, "units"), add="+")
                s._bind_scroll_recursive(child)
        except: pass

    # ─── REPAIR ───────────────────────────────────────────────────────────────
    def _t_repair(s,p):
        s._hdr(p,"System Repair","Fix corrupted Windows files and components.")
        for i,(t,d,fn,c) in enumerate([
            ("DISM RestoreHealth","Repairs the component store. 5-15 min.",lambda: s._op(run_dism),ACCENT),
            ("System File Checker","Scans and repairs system files. Run after DISM.",lambda: s._op(run_sfc),ACCENT),
            ("Check Disk (CHKDSK)","Schedules disk check on next boot.",lambda: s._op(run_chkdsk),WARN),
            ("Full Repair (DISM + SFC)","Creates restore point, runs DISM then SFC.",lambda: s._op(run_full_repair),OK),
        ],1):
            cd=s._crd(p,i); cd.grid_columnconfigure(0,weight=1)
            ctk.CTkLabel(cd,text=t,font=ctk.CTkFont(family=FONT,size=13,weight="bold"),text_color=TXT).grid(row=0,column=0,padx=12,pady=(10,0),sticky="w")
            ctk.CTkLabel(cd,text=d,font=ctk.CTkFont(family=FONT,size=11),text_color=TXT2).grid(row=1,column=0,padx=12,pady=(2,0),sticky="w")
            ctk.CTkButton(cd,text="Run",font=ctk.CTkFont(family=FONT,size=12,weight="bold"),fg_color=c,hover_color=s._dk(c),text_color="#fff",corner_radius=7,height=32,width=90,command=fn).grid(row=2,column=0,padx=12,pady=8,sticky="w")

    # ─── CLEANUP (grid) ──────────────────────────────────────────────────────
    def _t_cleanup(s,p):
        s._hdr(p,"Cleanup","Free up disk space and clear cached junk.")
        gf=ctk.CTkFrame(p,fg_color="transparent"); gf.grid(row=1,column=0,sticky="ew")
        gf.grid_columnconfigure(0,weight=1); gf.grid_columnconfigure(1,weight=1)
        for idx,(cid,(name,desc,danger)) in enumerate(CLEANUP_ITEMS.items()):
            r,c=divmod(idx,2)
            cd=ctk.CTkFrame(gf,fg_color=CARD,corner_radius=8); cd.grid(row=r,column=c,sticky="nsew",padx=3,pady=3); cd.grid_columnconfigure(0,weight=1)
            tc=DANGER if danger else TXT; fc=DANGER if danger else ACCENT
            ctk.CTkLabel(cd,text=name,font=ctk.CTkFont(family=FONT,size=13,weight="bold"),text_color=tc).grid(row=0,column=0,padx=12,pady=(10,0),sticky="w")
            ctk.CTkLabel(cd,text=desc,font=ctk.CTkFont(family=FONT,size=10),text_color=TXT2,wraplength=280).grid(row=1,column=0,padx=12,pady=(2,0),sticky="w")
            ctk.CTkButton(cd,text="Run",font=ctk.CTkFont(family=FONT,size=12,weight="bold"),fg_color=fc,hover_color=s._dk(fc),text_color="#fff",corner_radius=7,height=30,width=80,command=lambda k=cid: s._op(CLEANUP_FNS[k])).grid(row=2,column=0,padx=12,pady=8,sticky="w")

    # ─── DEPS (grid) ──────────────────────────────────────────────────────────
    def _t_deps(s,p):
        s._hdr(p,"Dependencies","Install common Windows runtimes via winget.")
        gf=ctk.CTkFrame(p,fg_color="transparent"); gf.grid(row=1,column=0,sticky="ew")
        for c in range(3): gf.grid_columnconfigure(c,weight=1)
        for idx,(name,pkg) in enumerate(DEP_ITEMS):
            r,c=divmod(idx,3)
            cd=ctk.CTkFrame(gf,fg_color=CARD,corner_radius=8); cd.grid(row=r,column=c,sticky="nsew",padx=3,pady=3); cd.grid_columnconfigure(0,weight=1)
            ctk.CTkLabel(cd,text=name,font=ctk.CTkFont(family=FONT,size=12,weight="bold"),text_color=TXT).grid(row=0,column=0,padx=10,pady=(10,2),sticky="w")
            ctk.CTkLabel(cd,text=pkg,font=ctk.CTkFont(family=MONO,size=9),text_color=TXT3).grid(row=1,column=0,padx=10,sticky="w")
            ctk.CTkButton(cd,text="Install",font=ctk.CTkFont(family=FONT,size=11,weight="bold"),fg_color=ACCENT,hover_color=ACCENT2,text_color="#fff",corner_radius=7,height=28,width=70,command=lambda pk=pkg: s._op(lambda cb: install_winget_pkg(pk,cb))).grid(row=2,column=0,padx=10,pady=8,sticky="w")

    # ─── APPS ─────────────────────────────────────────────────────────────────
    def _t_apps(s,p):
        s._hdr(p,"Install Apps","Select apps and install via winget or Chocolatey.")
        ctrl=ctk.CTkFrame(p,fg_color=CARD,corner_radius=8); ctrl.grid(row=1,column=0,sticky="ew",pady=(0,6)); ctrl.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(ctrl,text="Method:",font=ctk.CTkFont(family=FONT,size=12),text_color=TXT2).grid(row=0,column=0,padx=(12,6),pady=10)
        s._method_var=ctk.StringVar(value="winget")
        ctk.CTkSegmentedButton(ctrl,values=["winget","chocolatey"],variable=s._method_var,font=ctk.CTkFont(family=FONT,size=12),selected_color=ACCENT,selected_hover_color=ACCENT2).grid(row=0,column=1,padx=4,pady=10,sticky="w")
        s._app_search=ctk.CTkEntry(ctrl,placeholder_text="Search apps...",font=ctk.CTkFont(family=FONT,size=12),fg_color=BG,border_color=BORD,text_color=TXT,width=220)
        s._app_search.grid(row=0,column=2,padx=12,pady=10,sticky="e")
        s._app_search.bind("<KeyRelease>",lambda e: s._filter_apps())
        bf=ctk.CTkFrame(ctrl,fg_color="transparent"); bf.grid(row=0,column=3,padx=(0,12),pady=10)
        ctk.CTkButton(bf,text="Install Selected",font=ctk.CTkFont(family=FONT,size=12,weight="bold"),fg_color=OK,hover_color=s._dk(OK),text_color="#fff",corner_radius=7,height=32,width=130,command=s._install_apps).pack(side="left",padx=(0,6))
        ctk.CTkButton(bf,text="Clear",font=ctk.CTkFont(family=FONT,size=11),fg_color=CARD2,hover_color=HOVER,text_color=TXT3,corner_radius=7,height=32,width=60,command=lambda: [v.set(False) for v in s._avars.values()]).pack(side="left")
        s._app_frame=ctk.CTkFrame(p,fg_color="transparent"); s._app_frame.grid(row=2,column=0,sticky="ew")
        s._build_app_grid()

    def _build_app_grid(s,filt=""):
        for w in s._app_frame.winfo_children(): w.destroy()
        for c in range(3): s._app_frame.grid_columnconfigure(c,weight=1)
        cats={}
        for name,info in APP_LIST.items():
            if filt and filt.lower() not in name.lower(): continue
            cats.setdefault(info["cat"],[]).append(name)
        row=0
        for cat in sorted(cats.keys()):
            ctk.CTkLabel(s._app_frame,text=cat,font=ctk.CTkFont(family=FONT,size=13,weight="bold"),text_color=ACCENT).grid(row=row,column=0,columnspan=3,padx=4,pady=(8,4),sticky="w"); row+=1
            for idx,name in enumerate(sorted(cats[cat])):
                c=idx%3; r=row+idx//3
                if name not in s._avars: s._avars[name]=ctk.BooleanVar(value=False)
                ctk.CTkCheckBox(s._app_frame,text=name,variable=s._avars[name],font=ctk.CTkFont(family=FONT,size=12),text_color=TXT,fg_color=ACCENT,hover_color=ACCENT2,checkmark_color="#fff",border_color=BORD).grid(row=r,column=c,padx=6,pady=3,sticky="w")
            row+=(len(cats[cat])+2)//3
    def _filter_apps(s): s._build_app_grid(s._app_search.get())
    def _install_apps(s):
        sel=[n for n,v in s._avars.items() if v.get()]
        if not sel: s._log("[WARN] No apps selected."); return
        method=s._method_var.get()
        def run():
            s._log(f"[INFO] Checking {method} availability...")
            if method=="winget":
                if not check_winget(): s._log("[INFO] winget not found. Installing..."); install_winget_itself(s._log)
            else:
                if not check_choco(): s._log("[INFO] Chocolatey not found. Installing..."); install_choco_itself(s._log)
            for name in sel: install_app(name,method,s._log)
            s._log(f"[OK] Installed {len(sel)} app(s).")
        threading.Thread(target=run,daemon=True).start()

    # ─── TWEAKS & DEBLOAT (merged) ────────────────────────────────────────────
    def _t_tweaks(s,p):
        s._hdr(p,"Tweaks & Debloat","Hover for details. Search, use presets, or pick individually.")
        # Search + presets
        ctrl=ctk.CTkFrame(p,fg_color=CARD,corner_radius=8); ctrl.grid(row=1,column=0,sticky="ew",pady=(0,6)); ctrl.grid_columnconfigure(1,weight=1)
        s._tw_search=ctk.CTkEntry(ctrl,placeholder_text="Search tweaks...",font=ctk.CTkFont(family=FONT,size=12),fg_color=BG,border_color=BORD,text_color=TXT,width=220)
        s._tw_search.grid(row=0,column=0,padx=12,pady=10)
        s._tw_search.bind("<KeyRelease>",lambda e: s._filter_tweaks())
        pf=ctk.CTkFrame(ctrl,fg_color="transparent"); pf.grid(row=0,column=1,padx=4,pady=10,sticky="w")
        for i,(name,_) in enumerate(PRESETS.items()):
            cols=[ACCENT,OK,WARN,PURPLE]; c=cols[i%4]
            ctk.CTkButton(pf,text=name,font=ctk.CTkFont(family=FONT,size=11),fg_color=c,hover_color=s._dk(c),text_color="#fff",corner_radius=7,height=28,command=lambda n=name: s._load_preset(n)).pack(side="left",padx=2)
        bf=ctk.CTkFrame(ctrl,fg_color="transparent"); bf.grid(row=0,column=2,padx=12,pady=10)
        ctk.CTkButton(bf,text="Apply",font=ctk.CTkFont(family=FONT,size=12,weight="bold"),fg_color=OK,hover_color=s._dk(OK),text_color="#fff",corner_radius=7,height=30,width=80,command=s._apply_tweaks).pack(side="left",padx=(0,4))
        ctk.CTkButton(bf,text="Clear",font=ctk.CTkFont(family=FONT,size=11),fg_color=CARD2,hover_color=HOVER,text_color=TXT3,corner_radius=7,height=30,width=55,command=lambda: [v.set(False) for v in s._tvars.values()]).pack(side="left")

        s._tw_frame=ctk.CTkFrame(p,fg_color="transparent"); s._tw_frame.grid(row=2,column=0,sticky="ew")
        s._build_tweak_grid()

        # Browser debloat section
        bc=s._crd(p,3)
        ctk.CTkLabel(bc,text="Browser Debloat",font=ctk.CTkFont(family=FONT,size=13,weight="bold"),text_color=ACCENT).grid(row=0,column=0,columnspan=2,padx=12,pady=(10,4),sticky="w")
        ctk.CTkLabel(bc,text="Disables telemetry, bloat, and tracking. Uses exact WinUtil registry entries.",font=ctk.CTkFont(family=FONT,size=10),text_color=TXT2).grid(row=1,column=0,columnspan=2,padx=12,pady=(0,6),sticky="w")
        bc.grid_columnconfigure(0,weight=1); bc.grid_columnconfigure(1,weight=1)
        ctk.CTkButton(bc,text="Debloat Edge (17 entries)",font=ctk.CTkFont(family=FONT,size=12,weight="bold"),fg_color=ACCENT,hover_color=ACCENT2,text_color="#fff",corner_radius=7,height=30,command=lambda: s._op(debloat_edge)).grid(row=2,column=0,padx=12,pady=8,sticky="w")
        ctk.CTkButton(bc,text="Debloat Brave (12 entries)",font=ctk.CTkFont(family=FONT,size=12,weight="bold"),fg_color=ACCENT,hover_color=ACCENT2,text_color="#fff",corner_radius=7,height=30,command=lambda: s._op(debloat_brave)).grid(row=2,column=1,padx=12,pady=8,sticky="w")

        # App removal (debloat merged here)
        s._bvars={}
        for section_title,apps,is_danger,row in [
            ("App Removal  —  Safe",{k:v for k,v in BLOATWARE.items() if not v[1]},False,4),
            ("App Removal  —  CAUTION",{k:v for k,v in BLOATWARE.items() if v[1]},True,5),]:
            sc=s._crd(p,row)
            lc=DANGER if is_danger else ACCENT
            ctk.CTkLabel(sc,text=section_title,font=ctk.CTkFont(family=FONT,size=13,weight="bold"),text_color=lc).grid(row=0,column=0,columnspan=2,padx=12,pady=(10,6),sticky="w")
            sc.grid_columnconfigure(0,weight=1); sc.grid_columnconfigure(1,weight=1)
            for idx,(pkg,(name,_,tip)) in enumerate(apps.items()):
                c=idx%2; r=(idx//2)+1
                s._bvars[pkg]=ctk.BooleanVar(value=False)
                fc=DANGER if is_danger else ACCENT
                cb=ctk.CTkCheckBox(sc,text=name,variable=s._bvars[pkg],font=ctk.CTkFont(family=FONT,size=12),text_color=DANGER if is_danger else TXT,fg_color=fc,hover_color=s._dk(fc),checkmark_color="#fff",border_color=BORD)
                cb.grid(row=r,column=c,padx=10,pady=3,sticky="w"); s._tt(cb,tip)
            ctk.CTkFrame(sc,fg_color="transparent",height=4).grid(row=999,column=0)

        dbf=ctk.CTkFrame(p,fg_color="transparent"); dbf.grid(row=6,column=0,sticky="ew",pady=(4,0))
        ctk.CTkButton(dbf,text="Select All Safe",font=ctk.CTkFont(family=FONT,size=11),fg_color=ACCENT,hover_color=ACCENT2,text_color="#fff",corner_radius=7,height=30,command=lambda: [s._bvars[k].set(True) for k in BLOATWARE if not BLOATWARE[k][1]]).grid(row=0,column=0,padx=(0,6))
        ctk.CTkButton(dbf,text="Clear Apps",font=ctk.CTkFont(family=FONT,size=11),fg_color=CARD2,hover_color=HOVER,text_color=TXT3,corner_radius=7,height=30,command=lambda: [v.set(False) for v in s._bvars.values()]).grid(row=0,column=1,padx=(0,6))
        ctk.CTkButton(dbf,text="Remove Selected Apps",font=ctk.CTkFont(family=FONT,size=12,weight="bold"),fg_color=DANGER,hover_color=DANGER2,text_color="#fff",corner_radius=7,height=34,width=180,command=s._run_debloat).grid(row=0,column=2)

    def _build_tweak_grid(s,filt=""):
        for w in s._tw_frame.winfo_children(): w.destroy()
        s._tw_frame.grid_columnconfigure(0,weight=1); s._tw_frame.grid_columnconfigure(1,weight=1)
        row=0
        for sect,cat,color in [("Essential Tweaks","essential",ACCENT),("Advanced Tweaks  —  CAUTION","advanced",DANGER),("Preferences","preference",PURPLE)]:
            items=[(k,v) for k,v in TWEAKS.items() if v["cat"]==cat and (not filt or filt.lower() in v["label"].lower())]
            if not items: continue
            ctk.CTkLabel(s._tw_frame,text=sect,font=ctk.CTkFont(family=FONT,size=14,weight="bold"),text_color=color).grid(row=row,column=0,columnspan=2,padx=4,pady=(8,4),sticky="w"); row+=1
            for idx,(tid,td) in enumerate(items):
                c=idx%2; r=row+idx//2
                if tid not in s._tvars: s._tvars[tid]=ctk.BooleanVar(value=False)
                fc=DANGER if td["danger"] else ACCENT
                cb=ctk.CTkCheckBox(s._tw_frame,text=td["label"],variable=s._tvars[tid],font=ctk.CTkFont(family=FONT,size=12),text_color=DANGER if td["danger"] else TXT,fg_color=fc,hover_color=s._dk(fc),checkmark_color="#fff",border_color=BORD)
                cb.grid(row=r,column=c,padx=10,pady=4,sticky="w"); s._tt(cb,td["tip"])
            row+=(len(items)+1)//2
    def _filter_tweaks(s): s._build_tweak_grid(s._tw_search.get())
    def _load_preset(s,name):
        sel=PRESETS.get(name,{}).get("tweaks",[])
        for tid,var in s._tvars.items(): var.set(tid in sel)
        s._log(f"[INFO] Preset '{name}' loaded.")
    def _apply_tweaks(s):
        sel=[t for t,v in s._tvars.items() if v.get()]
        if not sel: s._log("[WARN] No tweaks selected."); return
        danger=[t for t in sel if TWEAKS[t]["danger"]]
        if danger:
            labels=", ".join(TWEAKS[t]["label"] for t in danger)
            if not s._confirm("Dangerous Tweaks",f"These are marked dangerous:\n{labels}\n\nRestore point will be created. Continue?",True): return
        def run():
            s._maybe_restore_point("WinForge Tweaks")
            for tid in sel: TWEAKS[tid]["fn"](s._log)
            s._log(f"[OK] {len(sel)} tweak(s) applied.")
        threading.Thread(target=run,daemon=True).start()

    def _run_debloat(s):
        sel=[p for p,v in s._bvars.items() if v.get()]
        if not sel: s._log("[WARN] No apps selected."); return
        names=", ".join(BLOATWARE[p][0] for p in sel)
        if not s._confirm("Confirm Removal",f"Remove {len(sel)} app(s)?\n{names[:250]}{'...' if len(names)>250 else ''}",any(BLOATWARE[p][1] for p in sel)): return
        def run():
            s._maybe_restore_point("WinForge Debloat")
            for pkg in sel: remove_app(pkg,s._log)
            s._log(f"[OK] Debloat complete.")
        threading.Thread(target=run,daemon=True).start()

    # ─── DNS ──────────────────────────────────────────────────────────────────
    def _t_dns(s,p):
        s._hdr(p,"DNS Settings","Choose a DNS server for all active network adapters.")
        s._dns_var=ctk.StringVar(value="Cloudflare (1.1.1.1)")
        gf=ctk.CTkFrame(p,fg_color="transparent"); gf.grid(row=1,column=0,sticky="ew")
        for c in range(2): gf.grid_columnconfigure(c,weight=1)
        dns_info={"Cloudflare (1.1.1.1)":"Fast, privacy-focused, no logging.","Google (8.8.8.8)":"Reliable. Google logs queries.","Quad9 (9.9.9.9)":"Blocks malware domains. Privacy-focused.","OpenDNS (208.67.222.222)":"Cisco-owned. Optional content filtering.","AdGuard (94.140.14.14)":"Blocks ads and trackers at DNS level.","Cloudflare Family (1.1.1.3)":"Cloudflare + blocks malware/adult.","Automatic (DHCP)":"Uses router/ISP default."}
        for idx,(name,(pri,sec)) in enumerate(DNS_SERVERS.items()):
            r,c=divmod(idx,2)
            cd=ctk.CTkFrame(gf,fg_color=CARD,corner_radius=8); cd.grid(row=r,column=c,sticky="nsew",padx=3,pady=3); cd.grid_columnconfigure(1,weight=1)
            ctk.CTkRadioButton(cd,text=name,variable=s._dns_var,value=name,font=ctk.CTkFont(family=FONT,size=12,weight="bold"),text_color=TXT,fg_color=ACCENT,border_color=BORD).grid(row=0,column=0,columnspan=2,padx=12,pady=(10,0),sticky="w")
            ctk.CTkLabel(cd,text=f"{pri}, {sec}" if pri else "Automatic",font=ctk.CTkFont(family=MONO,size=10),text_color=TXT3).grid(row=1,column=0,columnspan=2,padx=28,sticky="w")
            ctk.CTkLabel(cd,text=dns_info.get(name,""),font=ctk.CTkFont(family=FONT,size=10),text_color=TXT2,wraplength=280).grid(row=2,column=0,columnspan=2,padx=28,pady=(2,10),sticky="w")
        ctk.CTkButton(p,text="Apply DNS",font=ctk.CTkFont(family=FONT,size=13,weight="bold"),fg_color=ACCENT,hover_color=ACCENT2,text_color="#fff",corner_radius=7,height=36,width=140,command=lambda: s._op(lambda cb: set_dns(s._dns_var.get(),cb))).grid(row=2,column=0,pady=(8,4),sticky="w")

    # ─── UPDATES ──────────────────────────────────────────────────────────────
    def _t_updates(s,p):
        s._hdr(p,"Windows Updates","Control how Windows installs updates.")
        for i,(t,col,dan,d,cmd) in enumerate([
            ("Default Settings",ACCENT,False,"Resets Windows Update to defaults.\nRemoves all custom policies.",lambda: s._op(updates_default)),
            ("Security Settings",OK,False,"Feature updates delayed 365 days.\nSecurity after 4 days. No driver updates.\nNote: Pro/Enterprise only.",lambda: s._op(updates_security)),
            ("Disable All Updates",DANGER,True,"NOT RECOMMENDED\nDisables ALL updates. Security risk.\nOnly for isolated/test systems.",lambda: s._op(updates_disable)),],1):
            cd=s._crd(p,i); cd.grid_columnconfigure(0,weight=1)
            ctk.CTkLabel(cd,text=t,font=ctk.CTkFont(family=FONT,size=14,weight="bold"),text_color=DANGER if dan else TXT).grid(row=0,column=0,padx=12,pady=(10,2),sticky="w")
            ctk.CTkLabel(cd,text=d,font=ctk.CTkFont(family=FONT,size=11),text_color=WARN if dan else TXT2,justify="left").grid(row=1,column=0,padx=12,sticky="w")
            fc=DANGER if dan else col
            ctk.CTkButton(cd,text="Apply",font=ctk.CTkFont(family=FONT,size=12,weight="bold"),fg_color=fc,hover_color=s._dk(fc),text_color="#fff",corner_radius=7,height=30,width=90,command=cmd).grid(row=2,column=0,padx=12,pady=8,sticky="w")

    # ─── REGISTRY HEALTH ─────────────────────────────────────────────────────
    def _t_registry(s,p):
        s._hdr(p,"Registry Health","Safe registry maintenance. Backs up before any changes.")
        info=s._crd(p,1)
        ctk.CTkLabel(info,text="Only performs targeted, safe operations. Always backs up before cleaning.\nDoes NOT scan for 'invalid paths' or COM references — that's where damage happens.",font=ctk.CTkFont(family=FONT,size=11),text_color=TXT2,justify="left",wraplength=600).grid(row=0,column=0,padx=12,pady=10,sticky="w")

        cd1=s._crd(p,2)
        ctk.CTkLabel(cd1,text="Broken Uninstall Entries",font=ctk.CTkFont(family=FONT,size=13,weight="bold"),text_color=TXT).grid(row=0,column=0,padx=12,pady=(10,0),sticky="w")
        ctk.CTkLabel(cd1,text="Finds programs in Add/Remove Programs whose install folder no longer exists on disk.",font=ctk.CTkFont(family=FONT,size=11),text_color=TXT2,wraplength=500).grid(row=1,column=0,padx=12,pady=(2,0),sticky="w")
        ctk.CTkButton(cd1,text="Scan",font=ctk.CTkFont(family=FONT,size=12,weight="bold"),fg_color=ACCENT,hover_color=ACCENT2,text_color="#fff",corner_radius=7,height=30,width=80,command=s._scan_broken).grid(row=2,column=0,padx=12,pady=8,sticky="w")

        cd2=s._crd(p,3)
        ctk.CTkLabel(cd2,text="Empty Registry Keys",font=ctk.CTkFont(family=FONT,size=13,weight="bold"),text_color=TXT).grid(row=0,column=0,padx=12,pady=(10,0),sticky="w")
        ctk.CTkLabel(cd2,text="Finds completely empty keys left behind by uninstalled software. Very low risk.",font=ctk.CTkFont(family=FONT,size=11),text_color=TXT2,wraplength=500).grid(row=1,column=0,padx=12,pady=(2,0),sticky="w")
        ctk.CTkButton(cd2,text="Scan",font=ctk.CTkFont(family=FONT,size=12,weight="bold"),fg_color=ACCENT,hover_color=ACCENT2,text_color="#fff",corner_radius=7,height=30,width=80,command=s._scan_empty).grid(row=2,column=0,padx=12,pady=8,sticky="w")

    def _scan_broken(s):
        def run():
            results=registry_scan_broken_uninstalls(s._log)
            if not results:
                s._log("[OK] No broken uninstall entries found. Registry is clean.")
                return
            s._log(f"[INFO] Found {len(results)} broken entries:")
            for r in results: s._log(f"  - {r['name']} (path: {r['path']})")
            # Ask to clean
            s.after(0, lambda: s._ask_clean_broken(results))
        threading.Thread(target=run,daemon=True).start()

    def _ask_clean_broken(s,results):
        names = ", ".join(r["name"] for r in results[:10])
        if s._confirm("Clean Broken Entries",f"Remove {len(results)} broken uninstall entries?\n{names}{'...' if len(results)>10 else ''}\n\nRegistry will be backed up first."):
            def run():
                registry_backup(s._log)
                registry_clean_broken_uninstalls([r["key"] for r in results],s._log)
            threading.Thread(target=run,daemon=True).start()

    def _scan_empty(s):
        def run():
            results=registry_scan_empty_keys(s._log)
            if not results:
                s._log("[OK] No empty registry keys found.")
                return
            s._log(f"[INFO] Found {len(results)} empty keys.")
            s.after(0, lambda: s._ask_clean_empty(results))
        threading.Thread(target=run,daemon=True).start()

    def _ask_clean_empty(s,results):
        if s._confirm("Clean Empty Keys",f"Remove {len(results)} empty registry keys?\n\nRegistry will be backed up first."):
            def run():
                registry_backup(s._log)
                registry_clean_empty_keys(results,s._log)
            threading.Thread(target=run,daemon=True).start()

    # ─── TOOLS ────────────────────────────────────────────────────────────────
    def _t_tools(s,p):
        s._hdr(p,"System Tools","Quick access to legacy Windows panels.")
        cd=s._crd(p,1)
        ctk.CTkLabel(cd,text="Legacy Windows Panels",font=ctk.CTkFont(family=FONT,size=13,weight="bold"),text_color=ACCENT).grid(row=0,column=0,columnspan=3,padx=12,pady=(10,6),sticky="w")
        for c in range(3): cd.grid_columnconfigure(c,weight=1)
        for idx,(name,cmd) in enumerate(PANELS):
            r,c=1+idx//3,idx%3
            ctk.CTkButton(cd,text=name,font=ctk.CTkFont(family=FONT,size=11),fg_color=CARD2,hover_color=HOVER,text_color=TXT,corner_radius=7,height=34,command=lambda cc=cmd: s._op(lambda cb: open_panel(cc,cb))).grid(row=r,column=c,padx=4,pady=3,sticky="ew")
        # Padding to prevent artifact below last row
        ctk.CTkFrame(cd,fg_color=CARD,height=6).grid(row=99,column=0,columnspan=3,sticky="ew")

    # ─── RESTORE ──────────────────────────────────────────────────────────────
    def _t_restore(s,p):
        s._hdr(p,"Restore Point","Manually create a Windows restore point.")
        cd=s._crd(p,1)
        ctk.CTkLabel(cd,text="Create Restore Point",font=ctk.CTkFont(family=FONT,size=13,weight="bold"),text_color=TXT).grid(row=0,column=0,padx=12,pady=(10,0),sticky="w")
        ctk.CTkLabel(cd,text="Bypasses the 24-hour limit. Does not affect personal files.",font=ctk.CTkFont(family=FONT,size=11),text_color=TXT2).grid(row=1,column=0,padx=12,pady=(2,6),sticky="w")
        ef=ctk.CTkFrame(cd,fg_color="transparent"); ef.grid(row=2,column=0,padx=12,pady=(0,4),sticky="w")
        ctk.CTkLabel(ef,text="Label:",font=ctk.CTkFont(family=FONT,size=11),text_color=TXT2).grid(row=0,column=0,padx=(0,6))
        s._rpe=ctk.CTkEntry(ef,width=280,font=ctk.CTkFont(family=FONT,size=12),fg_color=BG,border_color=BORD,text_color=TXT,placeholder_text="WinForge Manual Restore Point")
        s._rpe.grid(row=0,column=1)
        ctk.CTkButton(cd,text="Create Now",font=ctk.CTkFont(family=FONT,size=12,weight="bold"),fg_color=OK,hover_color=s._dk(OK),text_color="#fff",corner_radius=7,height=32,width=120,command=lambda: s._op(lambda cb: create_restore_point(s._rpe.get().strip() or "WinForge Manual",cb))).grid(row=3,column=0,padx=12,pady=10,sticky="w")
