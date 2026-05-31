import sys
import os
import ctypes

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def relaunch_as_admin():
    script = os.path.abspath(sys.argv[0])
    params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
    sys.exit(0)

if __name__ == "__main__":
    if not is_admin():
        relaunch_as_admin()

    import customtkinter as ctk
    from ui.app import WinForgeApp

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = WinForgeApp()
    app.mainloop()
