import subprocess, re, os
from datetime import datetime

_restore_created_this_session = False

def run_ps(command, cb=None):
    try:
        p = subprocess.Popen(["powershell","-NoProfile","-ExecutionPolicy","Bypass","-Command",command],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        lines = []
        for line in p.stdout:
            line = line.rstrip()
            if line and not _junk(line):
                lines.append(line)
                if cb: cb(line)
        p.wait()
        return p.returncode == 0, "\n".join(lines)
    except Exception as e: return False, str(e)

def run_cmd(command, cb=None):
    try:
        p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        lines = []
        for line in p.stdout:
            line = line.rstrip()
            if line and not _junk(line):
                lines.append(line)
                if cb: cb(line)
        p.wait()
        return p.returncode == 0, "\n".join(lines)
    except Exception as e: return False, str(e)

def _junk(line):
    s = line.strip()
    if not s: return True
    if re.match(r'^(\[\d{2}:\d{2}:\d{2}\]\s*){2,}$', s): return True
    if re.match(r'^(\[\d{2}:\d{2}:\d{2}\]\s*)+$', s): return True
    return False

# ═══ RESTORE POINT ════════════════════════════════════════════════════════════

def was_restore_created_this_session():
    return _restore_created_this_session

def create_restore_point(desc="WinForge Pre-Operation", cb=None):
    global _restore_created_this_session
    if cb: cb("[INFO] Creating system restore point...")
    cmd = f'''
    Enable-ComputerRestore -Drive "C:\\" -EA SilentlyContinue
    Set-ItemProperty "HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SystemRestore" -Name "SystemRestorePointCreationFrequency" -Value 0 -Type DWord -Force -EA SilentlyContinue
    $before = (Get-ComputerRestorePoint -EA SilentlyContinue | Measure-Object).Count
    try {{ Checkpoint-Computer -Description "{desc}" -RestorePointType "MODIFY_SETTINGS" -EA Stop }}
    catch {{ Write-Host "[ERROR] $($_.Exception.Message)"; exit 1 }}
    $after = (Get-ComputerRestorePoint -EA SilentlyContinue | Measure-Object).Count
    if ($after -gt $before) {{
        $rp = Get-ComputerRestorePoint | Sort-Object SequenceNumber -Descending | Select-Object -First 1
        Write-Host "Restore point created: $($rp.Description) (ID $($rp.SequenceNumber))"
    }} else {{ Write-Host "[WARN] Command ran but no new restore point detected." }}
    '''
    s, o = run_ps(cmd, cb)
    if s: _restore_created_this_session = True
    elif cb: cb("[WARN] Restore point may have failed. Check System Protection is ON for C:")
    return s

# ═══ SYSTEM REPAIR ════════════════════════════════════════════════════════════

def run_dism(cb=None):
    if cb: cb("[INFO] Running DISM RestoreHealth (5-15 min)...")
    return run_cmd("DISM /Online /Cleanup-Image /RestoreHealth", cb)

def run_sfc(cb=None):
    if cb: cb("[INFO] Running System File Checker...")
    s, o = run_cmd("sfc /scannow", cb)
    if cb: cb("[OK] SFC complete.")
    return s, o

def run_chkdsk(cb=None):
    if cb: cb("[INFO] Scheduling CHKDSK on next boot...")
    return run_cmd("echo Y | chkdsk C: /f /r /x", cb)

def run_full_repair(cb=None):
    if cb: cb("[INFO] Starting Full System Repair...")
    create_restore_point("WinForge Full Repair", cb)
    run_dism(cb)
    run_sfc(cb)
    if cb: cb("[OK] Full repair complete. Restart recommended.")
    return True, "Done"

# ═══ CLEANUP ══════════════════════════════════════════════════════════════════

CLEANUP_ITEMS = {
    "temp": ("Temp Files", "Deletes %TEMP% and C:\\Windows\\Temp contents.", False),
    "wucache": ("Update Cache", "Clears Windows Update download cache.", False),
    "prefetch": ("Prefetch", "Clears prefetch cache. Rebuilds automatically.", False),
    "diskclean": ("Disk Cleanup", "Runs built-in Disk Cleanup with all categories.", False),
    "dns": ("Flush DNS", "Clears the DNS resolver cache.", False),
    "network": ("Network Reset", "Resets Winsock, TCP/IP, DNS. Needs restart.", True),
}
def clean_temp(cb=None):
    if cb: cb("[INFO] Cleaning temp files...")
    return run_ps(r'Remove-Item "$env:TEMP\*" -Recurse -Force -EA SilentlyContinue; Remove-Item "C:\Windows\Temp\*" -Recurse -Force -EA SilentlyContinue; Write-Host "Temp files cleaned."', cb)
def clean_wucache(cb=None):
    if cb: cb("[INFO] Clearing update cache...")
    return run_ps(r'Stop-Service wuauserv,bits -Force -EA SilentlyContinue; Remove-Item "C:\Windows\SoftwareDistribution\Download\*" -Recurse -Force -EA SilentlyContinue; Start-Service wuauserv,bits -EA SilentlyContinue; Write-Host "Update cache cleared."', cb)
def clean_prefetch(cb=None):
    if cb: cb("[INFO] Clearing prefetch...")
    return run_ps(r"Remove-Item 'C:\Windows\Prefetch\*' -Force -EA SilentlyContinue; Write-Host 'Prefetch cleared.'", cb)
def clean_diskclean(cb=None):
    if cb: cb("[INFO] Running Disk Cleanup...")
    return run_ps(r'$k=Get-ChildItem "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\VolumeCaches"; foreach($i in $k){Set-ItemProperty $i.PSPath -Name StateFlags0064 -Value 2 -EA SilentlyContinue}; Start-Process cleanmgr -ArgumentList "/sagerun:64" -Wait; Write-Host "Disk Cleanup complete."', cb)
def clean_dns(cb=None):
    if cb: cb("[INFO] Flushing DNS...")
    return run_cmd("ipconfig /flushdns", cb)
def clean_network(cb=None):
    if cb: cb("[INFO] Resetting network stack...")
    for c in ["netsh winsock reset","netsh int ip reset","ipconfig /flushdns","ipconfig /release","ipconfig /renew"]:
        run_cmd(c, cb)
    if cb: cb("[OK] Network reset complete. Restart needed.")
    return True, "Done"
CLEANUP_FNS = {"temp":clean_temp,"wucache":clean_wucache,"prefetch":clean_prefetch,"diskclean":clean_diskclean,"dns":clean_dns,"network":clean_network}

# ═══ DEPENDENCIES ═════════════════════════════════════════════════════════════

DEP_ITEMS = [
    (".NET 6","Microsoft.DotNet.Runtime.6"),(".NET 7","Microsoft.DotNet.Runtime.7"),
    (".NET 8 (LTS)","Microsoft.DotNet.Runtime.8"),(".NET 9","Microsoft.DotNet.Runtime.9"),
    ("VC++ 2015-2022 x64","Microsoft.VCRedist.2015+.x64"),("VC++ 2015-2022 x86","Microsoft.VCRedist.2015+.x86"),
    ("DirectX","Microsoft.DirectX"),("WebView2","Microsoft.EdgeWebView2Runtime"),
]
def install_winget_pkg(pkg, cb=None):
    if cb: cb(f"[INFO] Installing {pkg}...")
    return run_cmd(f'winget install --id {pkg} --silent --accept-package-agreements --accept-source-agreements', cb)

# ═══ APP INSTALL ══════════════════════════════════════════════════════════════

APP_LIST = {
    "Brave Browser":{"winget":"Brave.Brave","choco":"brave","cat":"Browsers"},
    "Firefox":{"winget":"Mozilla.Firefox","choco":"firefox","cat":"Browsers"},
    "Google Chrome":{"winget":"Google.Chrome","choco":"googlechrome","cat":"Browsers"},
    "Zen Browser":{"winget":"Zen-Team.Zen-Browser","choco":None,"cat":"Browsers"},
    "Discord":{"winget":"Discord.Discord","choco":"discord","cat":"Communication"},
    "Telegram":{"winget":"Telegram.TelegramDesktop","choco":"telegram","cat":"Communication"},
    "Zoom":{"winget":"Zoom.Zoom","choco":"zoom","cat":"Communication"},
    "Spotify":{"winget":"Spotify.Spotify","choco":"spotify","cat":"Media"},
    "VLC":{"winget":"VideoLAN.VLC","choco":"vlc","cat":"Media"},
    "OBS Studio":{"winget":"OBSProject.OBSStudio","choco":"obs-studio","cat":"Media"},
    "Steam":{"winget":"Valve.Steam","choco":"steam","cat":"Gaming"},
    "Epic Games":{"winget":"EpicGames.EpicGamesLauncher","choco":"epicgameslauncher","cat":"Gaming"},
    "GOG Galaxy":{"winget":"GOG.Galaxy","choco":"goggalaxy","cat":"Gaming"},
    "Obsidian":{"winget":"Obsidian.Obsidian","choco":"obsidian","cat":"Productivity"},
    "Notion":{"winget":"Notion.Notion","choco":"notion","cat":"Productivity"},
    "VS Code":{"winget":"Microsoft.VisualStudioCode","choco":"vscode","cat":"Development"},
    "Git":{"winget":"Git.Git","choco":"git","cat":"Development"},
    "Python":{"winget":"Python.Python.3.12","choco":"python","cat":"Development"},
    "Node.js LTS":{"winget":"OpenJS.NodeJS.LTS","choco":"nodejs-lts","cat":"Development"},
    "Notepad++":{"winget":"Notepad++.Notepad++","choco":"notepadplusplus","cat":"Development"},
    "7-Zip":{"winget":"7zip.7zip","choco":"7zip","cat":"Utilities"},
    "WinRAR":{"winget":"RARLab.WinRAR","choco":"winrar","cat":"Utilities"},
    "PowerToys":{"winget":"Microsoft.PowerToys","choco":"powertoys","cat":"Utilities"},
    "qBittorrent":{"winget":"qBittorrent.qBittorrent","choco":"qbittorrent","cat":"Utilities"},
    "Everything Search":{"winget":"voidtools.Everything","choco":"everything","cat":"Utilities"},
    "ShareX":{"winget":"ShareX.ShareX","choco":"sharex","cat":"Utilities"},
    "Bitwarden":{"winget":"Bitwarden.Bitwarden","choco":"bitwarden","cat":"Utilities"},
    "TreeSize Free":{"winget":"JAMSoftware.TreeSize.Free","choco":"treesizefree","cat":"Utilities"},
}
def check_winget(cb=None): return run_cmd("winget --version", cb)[0]
def check_choco(cb=None): return run_cmd("choco --version", cb)[0]
def install_winget_itself(cb=None):
    if cb: cb("[INFO] Installing/repairing winget...")
    return run_ps(r'Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe -EA SilentlyContinue; Write-Host "Winget install attempted."', cb)
def install_choco_itself(cb=None):
    if cb: cb("[INFO] Installing Chocolatey...")
    return run_ps(r"Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))", cb)
def install_app(name, method="winget", cb=None):
    info = APP_LIST.get(name)
    if not info: return False, "Unknown"
    pkg = info.get(method)
    if not pkg:
        if cb: cb(f"[WARN] {name} not available via {method}")
        return False, "N/A"
    if method == "winget":
        return run_cmd(f'winget install --id {pkg} --silent --accept-package-agreements --accept-source-agreements', cb)
    else:
        return run_cmd(f'choco install {pkg} -y', cb)

# ═══ DNS ══════════════════════════════════════════════════════════════════════

DNS_SERVERS = {
    "Cloudflare (1.1.1.1)":("1.1.1.1","1.0.0.1"),
    "Google (8.8.8.8)":("8.8.8.8","8.8.4.4"),
    "Quad9 (9.9.9.9)":("9.9.9.9","149.112.112.112"),
    "OpenDNS (208.67.222.222)":("208.67.222.222","208.67.220.220"),
    "AdGuard (94.140.14.14)":("94.140.14.14","94.140.15.15"),
    "Cloudflare Family (1.1.1.3)":("1.1.1.3","1.0.0.3"),
    "Automatic (DHCP)":(None,None),
}
def set_dns(dns_name, cb=None):
    pri, sec = DNS_SERVERS.get(dns_name, (None,None))
    if pri is None:
        if cb: cb("[INFO] Setting DNS to automatic (DHCP)...")
        cmd = r'Get-NetAdapter | Where-Object {$_.Status -eq "Up"} | foreach { Set-DnsClientServerAddress -InterfaceIndex $_.ifIndex -ResetServerAddresses }; Write-Host "DNS set to DHCP."'
    else:
        if cb: cb(f"[INFO] Setting DNS to {dns_name}...")
        cmd = f'Get-NetAdapter | Where-Object {{$_.Status -eq "Up"}} | foreach {{ Set-DnsClientServerAddress -InterfaceIndex $_.ifIndex -ServerAddresses ("{pri}","{sec}") }}; Write-Host "DNS set to {dns_name}"'
    run_ps(cmd, cb); run_cmd("ipconfig /flushdns", cb)
    return True

# ═══ UPDATES ══════════════════════════════════════════════════════════════════

def updates_default(cb=None):
    if cb: cb("[INFO] Resetting Windows Update to defaults...")
    return run_ps(r'Remove-Item "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate" -Recurse -Force -EA SilentlyContinue; Set-Service wuauserv -StartupType Automatic -EA SilentlyContinue; Start-Service wuauserv -EA SilentlyContinue; Write-Host "Windows Update reset."', cb)
def updates_security(cb=None):
    if cb: cb("[INFO] Configuring security-only updates...")
    return run_ps(r'''$p="HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"; $p2="HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"; If(!(Test-Path $p)){New-Item $p -Force|Out-Null}; If(!(Test-Path $p2)){New-Item $p2 -Force|Out-Null}; Set-ItemProperty $p -Name NoAutoUpdate -Value 0 -Force; Set-ItemProperty $p -Name AUOptions -Value 3 -Force; Set-ItemProperty $p2 -Name DeferFeatureUpdates -Value 1 -Force; Set-ItemProperty $p2 -Name DeferFeatureUpdatesPeriodInDays -Value 365 -Force; Set-ItemProperty $p2 -Name DeferQualityUpdates -Value 1 -Force; Set-ItemProperty $p2 -Name DeferQualityUpdatesPeriodInDays -Value 4 -Force; Set-ItemProperty $p2 -Name ExcludeWUDriversInQualityUpdate -Value 1 -Force; Write-Host "Security-only updates configured."''', cb)
def updates_disable(cb=None):
    if cb: cb("[WARN] Disabling ALL Windows Updates...")
    return run_ps(r'''$p="HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"; $p2="HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"; If(!(Test-Path $p)){New-Item $p -Force|Out-Null}; If(!(Test-Path $p2)){New-Item $p2 -Force|Out-Null}; Set-ItemProperty $p -Name NoAutoUpdate -Value 1 -Force; Set-ItemProperty $p -Name AUOptions -Value 1 -Force; Set-ItemProperty $p2 -Name DisableWindowsUpdateAccess -Value 1 -Force; Stop-Service wuauserv -Force -EA SilentlyContinue; Set-Service wuauserv -StartupType Disabled -EA SilentlyContinue; Write-Host "All updates disabled."''', cb)

# ═══ SYSTEM TOOLS ═════════════════════════════════════════════════════════════

PANELS = [("Computer Management","compmgmt.msc"),("Control Panel","control"),("Network Connections","ncpa.cpl"),
    ("Power Panel","powercfg.cpl"),("Printer Panel","printui /s"),("Region","intl.cpl"),
    ("Sound Settings","mmsys.cpl"),("System Properties","sysdm.cpl"),("Time and Date","timedate.cpl"),("Windows Restore","rstrui.exe")]
def open_panel(cmd, cb=None):
    subprocess.Popen(cmd, shell=True)
    return True, "Done"

# ═══ DEBLOAT ══════════════════════════════════════════════════════════════════

BLOATWARE = {
    "Microsoft.3DBuilder":("3D Builder",False,"Old 3D printing app."),
    "Microsoft.BingWeather":("Bing Weather",False,"Weather widget app."),
    "Microsoft.BingNews":("Microsoft News",False,"News feed app."),
    "Microsoft.GetHelp":("Get Help",False,"Microsoft support app."),
    "Microsoft.Getstarted":("Tips",False,"Windows tips app."),
    "Microsoft.MicrosoftOfficeHub":("Office Hub",False,"Office promo hub."),
    "Microsoft.MicrosoftSolitaireCollection":("Solitaire",False,"Card games with ads."),
    "Microsoft.MixedReality.Portal":("Mixed Reality Portal",False,"VR/AR portal."),
    "Microsoft.Movies.TV":("Movies & TV",False,"Video player."),
    "Microsoft.MSPaint":("Paint 3D",False,"3D Paint, not classic."),
    "Microsoft.People":("People",False,"Contacts app."),
    "Microsoft.SkypeApp":("Skype",False,"Skype consumer."),
    "Microsoft.Todos":("Microsoft To Do",False,"Task manager."),
    "Microsoft.WindowsAlarms":("Alarms & Clock",False,"Alarm app."),
    "Microsoft.WindowsFeedbackHub":("Feedback Hub",False,"Feedback to MS."),
    "Microsoft.WindowsMaps":("Maps",False,"Microsoft Maps."),
    "Microsoft.WindowsSoundRecorder":("Sound Recorder",False,"Audio recorder."),
    "Microsoft.YourPhone":("Phone Link",False,"Phone companion."),
    "Microsoft.ZuneMusic":("Groove Music",False,"Old music player."),
    "Microsoft.ZuneVideo":("Groove Video",False,"Old video app."),
    "MicrosoftTeams":("Teams (Personal)",False,"Personal Teams."),
    "Microsoft.PowerAutomateDesktop":("Power Automate",False,"Automation tool."),
    "Microsoft.Whiteboard":("Whiteboard",False,"Digital whiteboard."),
    "Clipchamp.Clipchamp":("Clipchamp",False,"Video editor."),
    "Microsoft.WindowsCommunicationsApps":("Mail & Calendar",False,"Mail/Calendar."),
    "Microsoft.XboxSpeechToTextOverlay":("Xbox Speech",False,"Xbox speech overlay."),
    "Microsoft.GamingApp":("Xbox App",True,"May break Game Pass."),
    "Microsoft.XboxGameOverlay":("Xbox Game Overlay",True,"Part of Xbox services."),
    "Microsoft.XboxGamingOverlay":("Xbox Gaming Overlay",True,"Affects Game Bar."),
    "Microsoft.XboxIdentityProvider":("Xbox Identity",True,"Required for Xbox login."),
    "Microsoft.OneDrive":("OneDrive",True,"Backup data first."),
    "Microsoft.Cortana":("Cortana",True,"May affect search."),
}

def check_app_installed(pkg, cb=None):
    """Check if an app is actually installed before trying to remove it."""
    s, o = run_ps(f'$a = Get-AppxPackage -Name "{pkg}" -EA SilentlyContinue; if ($a) {{ Write-Host "INSTALLED" }} else {{ Write-Host "NOT_INSTALLED" }}', None)
    return "INSTALLED" in o

def remove_app(pkg, cb=None):
    name = BLOATWARE.get(pkg, (pkg,False,""))[0]
    if not check_app_installed(pkg):
        if cb: cb(f"[INFO] {name} is not installed. Skipping.")
        return True, "Not installed"
    if cb: cb(f"[INFO] Removing {name}...")
    s, o = run_ps(f'Get-AppxPackage -Name "{pkg}" -AllUsers | Remove-AppxPackage -AllUsers -EA SilentlyContinue; Get-AppxProvisionedPackage -Online | Where-Object DisplayName -like "{pkg}" | Remove-AppxProvisionedPackage -Online -EA SilentlyContinue; Write-Host "Removed: {name}"', cb)
    # Verify removal
    if not check_app_installed(pkg):
        if cb: cb(f"[OK] {name} removed successfully.")
        return True, "Removed"
    else:
        if cb: cb(f"[WARN] {name} may not have been fully removed.")
        return False, "Partial"

# ═══ BROWSER DEBLOAT (WinUtil exact) ═════════════════════════════════════════

def debloat_edge(cb=None):
    if cb: cb("[INFO] Debloating Microsoft Edge (WinUtil method)...")
    cmd = r'''
    $p="HKLM:\SOFTWARE\Policies\Microsoft\Edge"; $pu="HKLM:\SOFTWARE\Policies\Microsoft\EdgeUpdate"; $pb="HKLM:\SOFTWARE\Policies\Microsoft\Edge\ExtensionInstallBlocklist"
    If(!(Test-Path $p)){New-Item $p -Force|Out-Null}; If(!(Test-Path $pu)){New-Item $pu -Force|Out-Null}; If(!(Test-Path $pb)){New-Item $pb -Force|Out-Null}
    Set-ItemProperty $pu -Name CreateDesktopShortcutDefault -Value 0 -Type DWord -Force
    Set-ItemProperty $p -Name PersonalizationReportingEnabled -Value 0 -Type DWord -Force
    Set-ItemProperty $pb -Name "1" -Value "ofefcgjbeghpigppfmkologfjadafddi" -Type String -Force
    Set-ItemProperty $p -Name ShowRecommendationsEnabled -Value 0 -Type DWord -Force
    Set-ItemProperty $p -Name HideFirstRunExperience -Value 1 -Type DWord -Force
    Set-ItemProperty $p -Name UserFeedbackAllowed -Value 0 -Type DWord -Force
    Set-ItemProperty $p -Name ConfigureDoNotTrack -Value 1 -Type DWord -Force
    Set-ItemProperty $p -Name AlternateErrorPagesEnabled -Value 0 -Type DWord -Force
    Set-ItemProperty $p -Name EdgeCollectionsEnabled -Value 0 -Type DWord -Force
    Set-ItemProperty $p -Name EdgeShoppingAssistantEnabled -Value 0 -Type DWord -Force
    Set-ItemProperty $p -Name MicrosoftEdgeInsiderPromotionEnabled -Value 0 -Type DWord -Force
    Set-ItemProperty $p -Name ShowMicrosoftRewards -Value 0 -Type DWord -Force
    Set-ItemProperty $p -Name WebWidgetAllowed -Value 0 -Type DWord -Force
    Set-ItemProperty $p -Name DiagnosticData -Value 0 -Type DWord -Force
    Set-ItemProperty $p -Name EdgeAssetDeliveryServiceEnabled -Value 0 -Type DWord -Force
    Set-ItemProperty $p -Name WalletDonationEnabled -Value 0 -Type DWord -Force
    Set-ItemProperty $p -Name DefaultBrowserSettingsCampaignEnabled -Value 0 -Type DWord -Force
    Write-Host "Edge debloated (17 entries)."
    '''
    return run_ps(cmd, cb)

def debloat_brave(cb=None):
    if cb: cb("[INFO] Debloating Brave Browser (WinUtil method)...")
    cmd = r'''
    $p="HKLM:\SOFTWARE\Policies\BraveSoftware\Brave"; If(!(Test-Path $p)){New-Item $p -Force|Out-Null}
    Set-ItemProperty $p -Name BraveRewardsDisabled -Value 1 -Type DWord -Force
    Set-ItemProperty $p -Name BraveWalletDisabled -Value 1 -Type DWord -Force
    Set-ItemProperty $p -Name BraveVPNDisabled -Value 1 -Type DWord -Force
    Set-ItemProperty $p -Name BraveAIChatEnabled -Value 0 -Type DWord -Force
    Set-ItemProperty $p -Name BraveStatsPingEnabled -Value 0 -Type DWord -Force
    Set-ItemProperty $p -Name BraveNewsDisabled -Value 1 -Type DWord -Force
    Set-ItemProperty $p -Name BraveTalkDisabled -Value 1 -Type DWord -Force
    Set-ItemProperty $p -Name TorDisabled -Value 1 -Type DWord -Force
    Set-ItemProperty $p -Name BraveP3AEnabled -Value 0 -Type DWord -Force
    Set-ItemProperty $p -Name UrlKeyedAnonymizedDataCollectionEnabled -Value 0 -Type DWord -Force
    Set-ItemProperty $p -Name SafeBrowsingExtendedReportingEnabled -Value 0 -Type DWord -Force
    Set-ItemProperty $p -Name MetricsReportingEnabled -Value 0 -Type DWord -Force
    Write-Host "Brave debloated (12 entries)."
    '''
    return run_ps(cmd, cb)

# ═══ REGISTRY HEALTH ══════════════════════════════════════════════════════════

def registry_scan_broken_uninstalls(cb=None):
    if cb: cb("[INFO] Scanning for broken uninstall entries...")
    cmd = r'''
    $path = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    $broken = @()
    Get-ChildItem $path -EA SilentlyContinue | ForEach-Object {
        $name = $_.GetValue("DisplayName")
        $loc = $_.GetValue("InstallLocation")
        if ($name -and $loc -and $loc -ne "" -and !(Test-Path $loc)) {
            $broken += "$name|$loc|$($_.PSChildName)"
        }
    }
    $path2 = "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
    Get-ChildItem $path2 -EA SilentlyContinue | ForEach-Object {
        $name = $_.GetValue("DisplayName")
        $loc = $_.GetValue("InstallLocation")
        if ($name -and $loc -and $loc -ne "" -and !(Test-Path $loc)) {
            $broken += "$name|$loc|$($_.PSChildName)"
        }
    }
    if ($broken.Count -eq 0) { Write-Host "NO_BROKEN_FOUND" }
    else { foreach ($b in $broken) { Write-Host "BROKEN:$b" } }
    '''
    s, o = run_ps(cmd, cb)
    results = []
    for line in o.split("\n"):
        if line.startswith("BROKEN:"):
            parts = line[7:].split("|")
            if len(parts) >= 3:
                results.append({"name": parts[0], "path": parts[1], "key": parts[2]})
    return results

def registry_scan_empty_keys(cb=None):
    if cb: cb("[INFO] Scanning for empty registry keys from uninstalled software...")
    cmd = r'''
    $paths = @(
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    )
    $empty = @()
    foreach ($p in $paths) {
        Get-ChildItem $p -EA SilentlyContinue | ForEach-Object {
            $vals = $_.GetValueNames() | Where-Object { $_ -ne "" }
            $subs = $_.GetSubKeyNames()
            if ($vals.Count -eq 0 -and $subs.Count -eq 0) {
                $empty += "$p\$($_.PSChildName)"
            }
        }
    }
    if ($empty.Count -eq 0) { Write-Host "NO_EMPTY_FOUND" }
    else { foreach ($e in $empty) { Write-Host "EMPTY:$e" } }
    '''
    s, o = run_ps(cmd, cb)
    results = []
    for line in o.split("\n"):
        if line.startswith("EMPTY:"):
            results.append(line[6:])
    return results

def registry_backup(cb=None):
    if cb: cb("[INFO] Backing up registry before cleaning...")
    backup_path = os.path.join(os.path.expanduser("~"), "Desktop", f"WinForge_RegBackup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.reg")
    cmd = f'reg export HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall "{backup_path}" /y'
    run_cmd(cmd, cb)
    if cb: cb(f"[OK] Registry backup saved to Desktop.")
    return backup_path

def registry_clean_broken_uninstalls(keys_to_remove, cb=None):
    if cb: cb("[INFO] Removing broken uninstall entries...")
    for key in keys_to_remove:
        for root in ["HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
                      "HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall"]:
            run_ps(f'Remove-Item "{root}\\{key}" -Recurse -Force -EA SilentlyContinue', None)
    if cb: cb(f"[OK] Removed {len(keys_to_remove)} broken entries.")

def registry_clean_empty_keys(paths_to_remove, cb=None):
    if cb: cb("[INFO] Removing empty registry keys...")
    for path in paths_to_remove:
        run_ps(f'Remove-Item "{path}" -Recurse -Force -EA SilentlyContinue', None)
    if cb: cb(f"[OK] Removed {len(paths_to_remove)} empty keys.")

# ═══ TWEAKS (WinUtil aligned) ═════════════════════════════════════════════════

TWEAKS = {
    # ── ESSENTIAL (WinUtil) ──
    "activity_history": {"label":"Activity History - Disable","cat":"essential","tip":"Erases recent docs, clipboard, and run history. Sets 3 registry keys matching WinUtil.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows\System" -Name EnableActivityFeed -Value 0 -Type DWord -Force -EA SilentlyContinue; Set-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows\System" -Name PublishUserActivities -Value 0 -Type DWord -Force -EA SilentlyContinue; Set-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows\System" -Name UploadUserActivities -Value 0 -Type DWord -Force -EA SilentlyContinue; Write-Host "Activity History disabled."', cb)},
    "disable_bitlocker": {"label":"BitLocker - Disable","cat":"essential","tip":"Disables BitLocker drive encryption on C: drive.","danger":False,
        "fn": lambda cb: run_ps(r'manage-bde -off C: -EA SilentlyContinue; Write-Host "BitLocker disable initiated on C:. May take time to decrypt."', cb)},
    "consumer_features": {"label":"ConsumerFeatures - Disable","cat":"essential","tip":"Prevents Windows from silently installing suggested apps like Candy Crush. Some default apps become inaccessible.","danger":False,
        "fn": lambda cb: run_ps(r'$p="HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent"; If(!(Test-Path $p)){New-Item $p -Force|Out-Null}; Set-ItemProperty $p -Name DisableWindowsConsumerFeatures -Value 1 -Type DWord -Force; Write-Host "ConsumerFeatures disabled."', cb)},
    "end_task_rightclick": {"label":"End Task With Right Click - Enable","cat":"essential","tip":"Adds End Task to the taskbar right-click menu for killing frozen apps.","danger":False,
        "fn": lambda cb: run_ps(r'$p="HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced\TaskbarDeveloperSettings"; If(!(Test-Path $p)){New-Item $p -Force|Out-Null}; Set-ItemProperty $p -Name TaskbarEndTask -Value 1 -Type DWord -Force; Write-Host "End Task on right-click enabled."', cb)},
    "disable_folder_discovery": {"label":"File Explorer Folder Discovery - Disable","cat":"essential","tip":"Stops Explorer from auto-detecting folder types and applying templates. Speeds up folder loading.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\Bags\AllFolders\Shell" -Name FolderType -Value "NotSpecified" -Type String -Force -EA SilentlyContinue; Write-Host "Folder discovery disabled."', cb)},
    "disable_hibernation": {"label":"Hibernation - Disable","cat":"essential","tip":"Disables hibernation and frees several GB of disk. Not recommended on laptops.","danger":False,
        "fn": lambda cb: run_cmd("powercfg /h off", cb)},
    "disable_location": {"label":"Location Tracking - Disable","cat":"essential","tip":"Disables Windows location services, sensors, and auto map updates. WinUtil sets 3 registry + 1 service.","danger":False,
        "fn": lambda cb: run_ps(r'''Set-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location" -Name Value -Value "Deny" -Type String -Force -EA SilentlyContinue; Set-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Sensor\Overrides\{BFA794E4-F964-4FDB-90F6-51056BFE4B44}" -Name SensorPermissionState -Value 0 -Type DWord -Force -EA SilentlyContinue; Set-ItemProperty "HKLM:\SYSTEM\Maps" -Name AutoUpdateEnabled -Value 0 -Type DWord -Force -EA SilentlyContinue; Set-Service lfsvc -StartupType Disabled -EA SilentlyContinue; Write-Host "Location tracking disabled."''', cb)},
    "disable_store_search": {"label":"Store Search Results - Disable","cat":"essential","tip":"Stops Start Menu from showing Microsoft Store app suggestions.","danger":False,
        "fn": lambda cb: run_ps(r'$p="HKCU:\SOFTWARE\Policies\Microsoft\Windows\Explorer"; If(!(Test-Path $p)){New-Item $p -Force|Out-Null}; Set-ItemProperty $p -Name NoUseStoreOpenWith -Value 1 -Type DWord -Force; Write-Host "Store suggestions disabled."', cb)},
    "disable_ps7_telemetry": {"label":"PowerShell 7 Telemetry - Disable","cat":"essential","tip":"Sets environment variable to stop PowerShell 7 telemetry.","danger":False,
        "fn": lambda cb: run_ps(r'[Environment]::SetEnvironmentVariable("POWERSHELL_TELEMETRY_OPTOUT","1","Machine"); Write-Host "PS7 telemetry disabled."', cb)},
    "services_manual": {"label":"Services - Set to Manual","cat":"essential","tip":"Sets background services to Manual/Disabled matching WinUtil. Also adjusts SvcHostSplitThreshold based on RAM.","danger":False,
        "fn": lambda cb: run_ps(r'''$svcManual=@("MapsBroker","StorSvc"); $svcDisabled=@("CscService","DiagTrack","SharedAccess"); foreach($s in $svcManual){Set-Service $s -StartupType Manual -EA SilentlyContinue}; foreach($s in $svcDisabled){Set-Service $s -StartupType Disabled -EA SilentlyContinue}; $ram=[math]::Round((Get-CimInstance Win32_PhysicalMemory|Measure-Object Capacity -Sum).Sum/1KB); Set-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control" -Name SvcHostSplitThresholdInKB -Value $ram -Type DWord -Force -EA SilentlyContinue; Write-Host "Services configured. SvcHost threshold set to $ram KB."''', cb)},
    "start_menu_layout": {"label":"Start Menu Previous Layout - Enable","cat":"essential","tip":"Restores the previous Start Menu layout by enabling the 'More Pins' layout.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name Start_Layout -Value 1 -Type DWord -Force -EA SilentlyContinue; Write-Host "Start Menu layout set to More Pins."', cb)},
    "disable_telemetry": {"label":"Telemetry - Disable","cat":"essential","tip":"Disables diagnostic data collection and DiagTrack service.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection" -Name AllowTelemetry -Value 0 -Type DWord -Force -EA SilentlyContinue; Stop-Service DiagTrack -Force -EA SilentlyContinue; Set-Service DiagTrack -StartupType Disabled -EA SilentlyContinue; Write-Host "Telemetry disabled."', cb)},
    "remove_widgets": {"label":"Widgets - Remove","cat":"essential","tip":"Fully removes Widgets platform and WebExperience packages, matching WinUtil method.","danger":False,
        "fn": lambda cb: run_ps(r'Get-Process *Widget* -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue; Get-AppxPackage Microsoft.WidgetsPlatformRuntime -AllUsers -EA SilentlyContinue | Remove-AppxPackage -AllUsers -EA SilentlyContinue; Get-AppxPackage MicrosoftWindows.Client.WebExperience -AllUsers -EA SilentlyContinue | Remove-AppxPackage -AllUsers -EA SilentlyContinue; Stop-Process -Name explorer -Force -EA SilentlyContinue; Write-Host "Widgets removed."', cb)},
    "disable_wpbt": {"label":"WPBT - Disable","cat":"essential","tip":"Disables Windows Platform Binary Table. Prevents OEM firmware from executing code on boot.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager" -Name DisableWpbtExecution -Value 1 -Type DWord -Force -EA SilentlyContinue; Write-Host "WPBT disabled."', cb)},

    # ── ADVANCED / CAUTION (WinUtil) ──
    "adobe_block": {"label":"Adobe URL Block List - Enable","cat":"advanced","tip":"Blocks Adobe activation/telemetry servers via hosts file. May prevent Adobe license checks.","danger":True,
        "fn": lambda cb: run_ps(r'''$hosts="$env:WINDIR\System32\drivers\etc\hosts"; $urls=@("lmlicenses.wip4.adobe.com","lm.licenses.adobe.com","na1r.services.adobe.com","hlrcv.stage.adobe.com","practivate.adobe.com","activate.adobe.com"); foreach($u in $urls){$line="0.0.0.0 $u"; if(!(Select-String -Path $hosts -Pattern $u -Quiet -EA SilentlyContinue)){Add-Content $hosts $line}}; Write-Host "Adobe URLs blocked in hosts file."''', cb)},
    "disable_bg_apps": {"label":"Background Apps - Disable","cat":"advanced","tip":"Stops all apps from running in background. Saves RAM and battery.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications" -Name GlobalUserDisabled -Value 1 -Type DWord -Force -EA SilentlyContinue; Write-Host "Background apps disabled."', cb)},
    "utc_time": {"label":"Date & Time - Set to UTC","cat":"advanced","tip":"Sets hardware clock to UTC. Useful for dual-boot with Linux.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\TimeZoneInformation" -Name RealTimeIsUniversal -Value 1 -Type DWord -Force; Write-Host "Hardware clock set to UTC."', cb)},
    "disable_home_gallery": {"label":"File Explorer Home and Gallery - Disable","cat":"advanced","tip":"Removes the Home and Gallery tabs from Win11 File Explorer navigation.","danger":False,
        "fn": lambda cb: run_ps(r'''$p="HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer"; Set-ItemProperty $p -Name HubMode -Value 1 -Type DWord -Force -EA SilentlyContinue; $gp="HKCU:\Software\Classes\CLSID\{e88865ea-0e1c-4e20-9aa6-edcd0212c87c}"; If(!(Test-Path $gp)){New-Item $gp -Force|Out-Null}; Set-ItemProperty $gp -Name "System.IsPinnedToNameSpaceTree" -Value 0 -Type DWord -Force; Write-Host "Home and Gallery disabled."''', cb)},
    "disable_fullscreen_opt": {"label":"Fullscreen Optimizations - Disable","cat":"advanced","tip":"Can improve gaming performance and reduce input lag.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\System\GameConfigStore" -Name GameDVR_DXGIHonorFSEWindowsCompatible -Value 1 -Type DWord -Force -EA SilentlyContinue; Set-ItemProperty "HKCU:\System\GameConfigStore" -Name GameDVR_FSEBehavior -Value 2 -Type DWord -Force -EA SilentlyContinue; Write-Host "Fullscreen optimizations disabled."', cb)},
    "disable_ipv6": {"label":"IPv6 - Disable","cat":"advanced","tip":"Fully disables IPv6 on all adapters. Only if your network doesn't use it.","danger":True,
        "fn": lambda cb: run_ps(r'Get-NetAdapter | foreach { Disable-NetAdapterBinding -Name $_.Name -ComponentID ms_tcpip6 -EA SilentlyContinue }; Write-Host "IPv6 disabled."', cb)},
    "prefer_ipv4": {"label":"IPv6 - Prefer IPv4","cat":"advanced","tip":"Keeps IPv6 but prefers IPv4. Safer than full disable.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters" -Name DisabledComponents -Value 32 -Type DWord -Force -EA SilentlyContinue; Write-Host "IPv4 preferred."', cb)},
    "remove_edge": {"label":"Microsoft Edge - Remove","cat":"advanced","tip":"Fully removes Microsoft Edge from the system. Some Windows features may break.","danger":True,
        "fn": lambda cb: run_ps(r'''$edgePath = "${env:ProgramFiles(x86)}\Microsoft\Edge\Application"; if (Test-Path $edgePath) { $setup = Get-ChildItem $edgePath -Recurse -Filter "setup.exe" | Select-Object -First 1; if ($setup) { Start-Process $setup.FullName -ArgumentList "--uninstall --system-level --force-uninstall" -Wait } }; Write-Host "Edge removal attempted."''', cb)},
    "remove_onedrive": {"label":"OneDrive - Remove","cat":"advanced","tip":"Fully uninstalls OneDrive. Backup data first.","danger":True,
        "fn": lambda cb: run_ps(r'Stop-Process -Name OneDrive -Force -EA SilentlyContinue; Start-Process "$env:SYSTEMROOT\SysWOW64\OneDriveSetup.exe" -ArgumentList "/uninstall" -Wait -EA SilentlyContinue; Start-Process "$env:SYSTEMROOT\System32\OneDriveSetup.exe" -ArgumentList "/uninstall" -Wait -EA SilentlyContinue; Write-Host "OneDrive removed."', cb)},
    "disable_razer_auto": {"label":"Razer Auto-Install - Disable","cat":"advanced","tip":"Stops Razer Synapse from auto-installing when you plug in a Razer device.","danger":False,
        "fn": lambda cb: run_ps(r'$p="HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Device Installer"; Set-ItemProperty $p -Name DisableCoInstallers -Value 1 -Type DWord -Force -EA SilentlyContinue; Write-Host "Razer auto-install disabled."', cb)},
    "disable_rdp_warnings": {"label":"RDP Unsigned File Warnings - Disable","cat":"advanced","tip":"Stops the warning popup when opening unsigned RDP files.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\Software\Microsoft\Terminal Server Client" -Name AuthenticationLevelOverride -Value 0 -Type DWord -Force -EA SilentlyContinue; Write-Host "RDP warnings disabled."', cb)},
    "remove_copilot": {"label":"Remove Copilot","cat":"advanced","tip":"Disables and removes Windows Copilot entirely.","danger":False,
        "fn": lambda cb: run_ps(r'''$p="HKCU:\Software\Policies\Microsoft\Windows\WindowsCopilot"; If(!(Test-Path $p)){New-Item $p -Force|Out-Null}; Set-ItemProperty $p -Name TurnOffWindowsCopilot -Value 1 -Type DWord -Force; $p2="HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot"; If(!(Test-Path $p2)){New-Item $p2 -Force|Out-Null}; Set-ItemProperty $p2 -Name TurnOffWindowsCopilot -Value 1 -Type DWord -Force; Write-Host "Copilot disabled."''', cb)},
    "disable_notifications": {"label":"Notifications - Disable","cat":"advanced","tip":"Disables all Windows notification popups system-wide.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\PushNotifications" -Name ToastEnabled -Value 0 -Type DWord -Force -EA SilentlyContinue; Set-ItemProperty "HKCU:\Software\Policies\Microsoft\Windows\CurrentVersion\PushNotifications" -Name NoToastApplicationNotification -Value 1 -Type DWord -Force -EA SilentlyContinue; Write-Host "Notifications disabled."', cb)},
    "disable_storage_sense": {"label":"Storage Sense - Disable","cat":"advanced","tip":"Stops auto-deletion of temp files and recycle bin contents.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy" -Name 01 -Value 0 -Type DWord -Force -EA SilentlyContinue; Write-Host "Storage Sense disabled."', cb)},
    "disable_teredo": {"label":"Teredo - Disable","cat":"advanced","tip":"Disables IPv6 tunnelling protocol. Slight network improvement.","danger":False,
        "fn": lambda cb: run_cmd("netsh interface teredo set state disabled", cb)},
    "visual_performance": {"label":"Visual Effects - Best Performance","cat":"advanced","tip":"Disables all animations. Snappier but less pretty.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects" -Name VisualFXSetting -Value 2 -Type DWord -Force -EA SilentlyContinue; Write-Host "Visual effects set to performance."', cb)},
    "disable_windows_ai": {"label":"Windows AI / Recall - Disable","cat":"advanced","tip":"Disables Recall and AI features. Recommended for privacy.","danger":False,
        "fn": lambda cb: run_ps(r'$p="HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsAI"; If(!(Test-Path $p)){New-Item $p -Force|Out-Null}; Set-ItemProperty $p -Name AllowRecallEnablement -Value 0 -Type DWord -Force; Set-ItemProperty $p -Name DisableAIDataAnalysis -Value 1 -Type DWord -Force; Write-Host "Windows AI disabled."', cb)},
    "remove_xbox": {"label":"Xbox Components - Remove","cat":"advanced","tip":"Removes Xbox apps and overlay. Will break Game Pass.","danger":True,
        "fn": lambda cb: run_ps(r'@("Microsoft.XboxGameOverlay","Microsoft.XboxGamingOverlay","Microsoft.XboxIdentityProvider","Microsoft.XboxSpeechToTextOverlay") | foreach { Get-AppxPackage -Name $_ -EA SilentlyContinue | Remove-AppxPackage -EA SilentlyContinue }; Write-Host "Xbox components removed."', cb)},

    # ── PREFERENCES (WinUtil) ──
    "pref_bsod_verbose": {"label":"BSoD Verbose Mode","cat":"preference","tip":"Shows detailed BSOD info (error codes, driver names) instead of just a sad face.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\CrashControl" -Name DisplayParameters -Value 1 -Type DWord -Force; Write-Host "BSoD verbose mode enabled."', cb)},
    "pref_dark_mode": {"label":"Dark Theme","cat":"preference","tip":"Enables system-wide dark theme.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize" -Name AppsUseLightTheme -Value 0 -Type DWord -Force; Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize" -Name SystemUsesLightTheme -Value 0 -Type DWord -Force; Write-Host "Dark mode enabled."', cb)},
    "pref_file_ext": {"label":"Show File Extensions","cat":"preference","tip":"Shows .exe, .pdf, etc in Explorer. Highly recommended.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name HideFileExt -Value 0 -Type DWord -Force; Write-Host "File extensions visible."', cb)},
    "pref_hidden_files": {"label":"Show Hidden Files","cat":"preference","tip":"Shows hidden files in Explorer.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name Hidden -Value 1 -Type DWord -Force; Write-Host "Hidden files visible."', cb)},
    "pref_no_mouse_accel": {"label":"Disable Mouse Acceleration","cat":"preference","tip":"Removes pointer acceleration. Better for gaming.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\Control Panel\Mouse" -Name MouseSpeed -Value 0 -Type String -Force; Set-ItemProperty "HKCU:\Control Panel\Mouse" -Name MouseThreshold1 -Value 0 -Type String -Force; Set-ItemProperty "HKCU:\Control Panel\Mouse" -Name MouseThreshold2 -Value 0 -Type String -Force; Write-Host "Mouse accel disabled."', cb)},
    "pref_numlock": {"label":"Num Lock on Startup","cat":"preference","tip":"Enables Num Lock when Windows starts.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\Control Panel\Keyboard" -Name InitialKeyboardIndicators -Value 2 -Type String -Force; Write-Host "Num Lock enabled."', cb)},
    "pref_no_sticky_keys": {"label":"Disable Sticky Keys","cat":"preference","tip":"Stops the Shift x5 popup. Essential for gaming.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\Control Panel\Accessibility\StickyKeys" -Name Flags -Value "506" -Type String -Force; Write-Host "Sticky Keys disabled."', cb)},
    "pref_hide_search": {"label":"Hide Taskbar Search","cat":"preference","tip":"Hides search from taskbar. Win key still opens search.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Search" -Name SearchboxTaskbarMode -Value 0 -Type DWord -Force; Write-Host "Search hidden."', cb)},
    "pref_hide_taskview": {"label":"Hide Task View Button","cat":"preference","tip":"Hides Task View from the taskbar.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name ShowTaskViewButton -Value 0 -Type DWord -Force; Write-Host "Task View hidden."', cb)},
    "pref_left_taskbar": {"label":"Taskbar Icons - Move Left","cat":"preference","tip":"Moves taskbar icons to the left (Win11).","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name TaskbarAl -Value 0 -Type DWord -Force; Write-Host "Taskbar left-aligned."', cb)},
    "pref_classic_menu": {"label":"Classic Right-Click Menu","cat":"preference","tip":"Restores the full context menu in Win11.","danger":False,
        "fn": lambda cb: run_ps(r'$p="HKCU:\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32"; If(!(Test-Path $p)){New-Item $p -Force|Out-Null}; Set-ItemProperty $p -Name "(Default)" -Value "" -Force; Stop-Process -Name explorer -Force -EA SilentlyContinue; Write-Host "Classic context menu restored."', cb)},
    "pref_no_startup_delay": {"label":"Remove Startup Delay","cat":"preference","tip":"Removes the artificial delay before startup programs.","danger":False,
        "fn": lambda cb: run_ps(r'$p="HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize"; If(!(Test-Path $p)){New-Item $p -Force|Out-Null}; Set-ItemProperty $p -Name StartupDelayInMSec -Value 0 -Type DWord -Force; Write-Host "Startup delay removed."', cb)},
    "pref_high_perf": {"label":"High Performance Power Plan","cat":"preference","tip":"Best for desktops. Not recommended on battery.","danger":False,
        "fn": lambda cb: run_cmd("powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", cb)},
    "pref_no_bing_search": {"label":"Start Menu Bing Search - Disable","cat":"preference","tip":"Removes web/Bing results from Start Menu search. Only shows local results.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Search" -Name BingSearchEnabled -Value 0 -Type DWord -Force -EA SilentlyContinue; Set-ItemProperty "HKCU:\SOFTWARE\Policies\Microsoft\Windows\Explorer" -Name DisableSearchBoxSuggestions -Value 1 -Type DWord -Force -EA SilentlyContinue; Write-Host "Bing search disabled."', cb)},
    "pref_no_recommendations": {"label":"Start Menu Recommendations - Disable","cat":"preference","tip":"Disables the Recommended section in the Win11 Start Menu.","danger":False,
        "fn": lambda cb: run_ps(r'$p="HKLM:\SOFTWARE\Policies\Microsoft\Windows\Explorer"; If(!(Test-Path $p)){New-Item $p -Force|Out-Null}; Set-ItemProperty $p -Name HideRecommendedSection -Value 1 -Type DWord -Force; Write-Host "Start Menu recommendations disabled."', cb)},
    "pref_multiplane_overlay": {"label":"Multiplane Overlay - Disable","cat":"preference","tip":"Disables MPO which can cause flickering or rendering issues on some GPUs.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\Dwm" -Name OverlayTestMode -Value 5 -Type DWord -Force -EA SilentlyContinue; Write-Host "Multiplane Overlay disabled."', cb)},
    "pref_scrollbars_visible": {"label":"Scrollbars Always Visible","cat":"preference","tip":"Forces scrollbars to always be visible instead of auto-hiding.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\Control Panel\Accessibility" -Name DynamicScrollbars -Value 0 -Type DWord -Force -EA SilentlyContinue; Write-Host "Scrollbars always visible."', cb)},
    "pref_s0_sleep_net": {"label":"S0 Sleep Network - Disable","cat":"preference","tip":"Disables network connectivity during Modern Standby (S0). Saves battery and improves privacy.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Power\PowerSettings\f15576e8-98b7-4186-b944-eafa664402d9" -Name Attributes -Value 2 -Type DWord -Force -EA SilentlyContinue; powercfg /setdcvalueindex SCHEME_CURRENT f15576e8-98b7-4186-b944-eafa664402d9 12bbebe6-58d6-4636-95bb-3217ef867c1a 0; powercfg /setacvalueindex SCHEME_CURRENT f15576e8-98b7-4186-b944-eafa664402d9 12bbebe6-58d6-4636-95bb-3217ef867c1a 0; powercfg /setactive SCHEME_CURRENT; Write-Host "S0 sleep network disabled."', cb)},
    "pref_no_snap_flyout": {"label":"Snap Flyout - Disable","cat":"preference","tip":"Disables the snap layout popup when hovering over maximize button.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name EnableSnapAssistFlyout -Value 0 -Type DWord -Force -EA SilentlyContinue; Write-Host "Snap flyout disabled."', cb)},
    "pref_no_snap_suggestions": {"label":"Snap Suggestions - Disable","cat":"preference","tip":"Disables suggestions for what to snap next to a window.","danger":False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name SnapAssist -Value 0 -Type DWord -Force -EA SilentlyContinue; Write-Host "Snap suggestions disabled."', cb)},
}

PRESETS = {
    "Gaming PC": {"tweaks":["disable_telemetry","end_task_rightclick","disable_fullscreen_opt","pref_no_mouse_accel","pref_no_sticky_keys","disable_bg_apps","visual_performance","pref_no_startup_delay","pref_high_perf","remove_widgets","disable_windows_ai","pref_multiplane_overlay","pref_no_bing_search"]},
    "Privacy": {"tweaks":["disable_telemetry","activity_history","consumer_features","disable_location","disable_ps7_telemetry","disable_windows_ai","remove_onedrive","disable_store_search","remove_copilot","disable_notifications","pref_no_bing_search"]},
    "Fresh Install": {"tweaks":["pref_file_ext","pref_hidden_files","pref_dark_mode","pref_no_sticky_keys","disable_telemetry","consumer_features","pref_classic_menu","pref_no_startup_delay","end_task_rightclick","remove_widgets","start_menu_layout","pref_no_bing_search","pref_no_recommendations","pref_bsod_verbose"]},
    "Performance": {"tweaks":["pref_high_perf","disable_bg_apps","visual_performance","pref_no_startup_delay","disable_telemetry","services_manual","disable_storage_sense","disable_fullscreen_opt","pref_multiplane_overlay"]},
}
