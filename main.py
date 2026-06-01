"""
WinForge core operations — all PowerShell-backed backend logic.
"""
import subprocess, threading, json, os, sys

def run_ps(script: str, cb=None) -> str:
    """Run a PowerShell script and stream output via cb(line). Returns full output."""
    try:
        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        out = []
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                out.append(line)
                if cb: cb(line)
        proc.wait()
        return "\n".join(out)
    except Exception as e:
        msg = f"[ERROR] PowerShell error: {e}"
        if cb: cb(msg)
        return msg


# ─────────────────────────── SYSTEM INFO ────────────────────────────
def get_system_info(cb=None):
    script = r'''
$info = @{}
# OS
$os = Get-CimInstance Win32_OperatingSystem
$info["os_name"]    = $os.Caption
$info["os_version"] = $os.Version
$info["os_build"]   = $os.BuildNumber
$info["os_arch"]    = $os.OSArchitecture
$info["os_install"] = $os.InstallDate.ToString("yyyy-MM-dd")
$boot = $os.LastBootUpTime
$uptime = (Get-Date) - $boot
$info["uptime"] = "$([int]$uptime.TotalHours)h $($uptime.Minutes)m"
# CPU
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$info["cpu_name"]    = $cpu.Name.Trim()
$info["cpu_cores"]   = "$($cpu.NumberOfCores) cores / $($cpu.NumberOfLogicalProcessors) threads"
$info["cpu_clock"]   = "$([math]::Round($cpu.MaxClockSpeed/1000,1)) GHz"
# RAM
$ram = Get-CimInstance Win32_PhysicalMemory
$totalGB = [math]::Round(($ram | Measure-Object -Property Capacity -Sum).Sum / 1GB, 0)
$speed   = ($ram | Select-Object -First 1).Speed
$sticks  = $ram.Count
$type    = switch(($ram | Select-Object -First 1).SMBIOSMemoryType){
    26{"DDR4"} 34{"DDR5"} 24{"DDR3"} default{"DDR"}
}
$info["ram"] = "${totalGB}GB ${type} ${speed}MHz (${sticks} stick$(if($sticks -ne 1){'s'}))"
# GPU — use registry GUID {4d36e968-e325-11ce-bfc1-08002be10318} for real VRAM
$gpus = Get-CimInstance Win32_VideoController
$gpuList = @()
foreach ($g in $gpus) {
    $vram = $null
    try {
        $regPath = "HKLM:\SYSTEM\ControlSet001\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        Get-ChildItem $regPath -EA SilentlyContinue | ForEach-Object {
            $desc = (Get-ItemProperty $_.PSPath -EA SilentlyContinue).DriverDesc
            if ($desc -and $desc -eq $g.Name) {
                $qw = (Get-ItemProperty $_.PSPath -EA SilentlyContinue).'HardwareInformation.qwMemorySize'
                if ($qw -and [uint64]$qw -gt 0) {
                    $vram = [math]::Round([uint64]$qw / 1GB, 0)
                }
                if (!$vram) {
                    $memBytes = (Get-ItemProperty $_.PSPath -EA SilentlyContinue).'HardwareInformation.MemorySize'
                    if ($memBytes) {
                        $bytes = [System.BitConverter]::ToUInt64([byte[]]$memBytes, 0)
                        if ($bytes -gt 0) { $vram = [math]::Round($bytes / 1GB, 0) }
                    }
                }
            }
        }
    } catch {}
    if (!$vram -or $vram -le 0) {
        $raw = $g.AdapterRAM
        if ($raw -gt 0) { $vram = [math]::Round($raw / 1GB, 0) } else { $vram = $null }
    }
    $vramStr = if ($vram -and $vram -gt 0) { "${vram}GB" } else { "Shared" }
    $gpuList += "$($g.Name) ($vramStr)"
}
$info["gpu"]        = $gpuList -join " | "
$info["gpu_driver"] = ($gpus | Select-Object -First 1).DriverVersion
# Storage
$disks = Get-CimInstance Win32_DiskDrive
$diskList = @()
foreach ($d in $disks) {
    $sizeGB = [math]::Round($d.Size/1GB,0)
    $mediaType = if($d.MediaType -match "SSD|Solid"){"SSD"}elseif($d.MediaType -match "HDD|Fixed"){"HDD"}else{"Drive"}
    $diskList += "$($d.Model) (${sizeGB}GB $mediaType)"
}
$info["disks"] = $diskList -join " | "
$vols = Get-PSDrive -PSProvider FileSystem | Where-Object {$_.Used -ne $null}
$volList = @()
foreach ($v in $vols) {
    $free = [math]::Round($v.Free/1GB,1)
    $total= [math]::Round(($v.Used+$v.Free)/1GB,1)
    $volList += "$($v.Name): ${free}GB free / ${total}GB"
}
$info["volumes"] = $volList -join " | "
# Motherboard & BIOS
$mb   = Get-CimInstance Win32_BaseBoard
$bios = Get-CimInstance Win32_BIOS
$info["motherboard"] = "$($mb.Manufacturer) $($mb.Product)"
$info["bios"]        = "$($bios.Manufacturer) $($bios.SMBIOSBIOSVersion)"
# Security
try { $sb = Confirm-SecureBootUEFI; $info["secure_boot"] = if($sb){"Enabled"}else{"Disabled"} } catch { $info["secure_boot"] = "N/A" }
try { $tpm = Get-Tpm; $info["tpm"] = if($tpm.TpmPresent){"v$($tpm.ManufacturerVersionInfo) Present"}else{"Not Present"} } catch { $info["tpm"] = "N/A" }
try {
    $def = Get-MpComputerStatus -EA SilentlyContinue
    $info["defender"] = if($def){ "$(if($def.RealTimeProtectionEnabled){'Active'}else{'Disabled'}) — Defs: $($def.AntivirusSignatureLastUpdated.ToString('yyyy-MM-dd'))" } else { "N/A" }
} catch { $info["defender"] = "N/A" }
# Network
$net = Get-CimInstance Win32_NetworkAdapterConfiguration | Where-Object {$_.IPEnabled -eq $true} | Select-Object -First 1
$info["network"] = if($net){"$($net.Description) | MAC: $($net.MACAddress)"}else{"N/A"}
# Power
try {
    $plan = powercfg /getactivescheme 2>$null
    $info["power"] = if($plan -match '\((.+)\)'){"Active: $($Matches[1])"}else{"N/A"}
} catch { $info["power"] = "N/A" }
$info | ConvertTo-Json -Compress
'''
    raw = run_ps(script, cb)
    try:
        lines = [l for l in raw.splitlines() if l.strip().startswith("{")]
        if lines:
            return json.loads(lines[-1])
    except:
        pass
    return {}


# ─────────────────────────── REPAIR ─────────────────────────────────
def run_dism(cb=None):
    return run_ps("DISM /Online /Cleanup-Image /RestoreHealth", cb)

def run_sfc(cb=None):
    return run_ps("sfc /scannow", cb)

def run_chkdsk(cb=None):
    return run_ps("chkdsk C: /f /r /x", cb)


# ─────────────────────────── CLEANUP ────────────────────────────────
def clean_temp(cb=None):
    if cb: cb("[INFO] Cleaning temp files...")
    script = r'''
$dirs = @($env:TEMP, $env:TMP, "C:\Windows\Temp", "C:\Windows\Prefetch")
$count = 0
foreach ($d in $dirs) {
    if (Test-Path $d) {
        Get-ChildItem $d -Recurse -Force -EA SilentlyContinue | Remove-Item -Recurse -Force -EA SilentlyContinue
        $count++
    }
}
Write-Host "[OK] Temp folders cleaned ($count directories)"
'''
    return run_ps(script, cb)

def clean_update_cache(cb=None):
    if cb: cb("[INFO] Cleaning Windows Update cache...")
    script = r'''
Stop-Service -Name wuauserv -Force -EA SilentlyContinue
Stop-Service -Name bits    -Force -EA SilentlyContinue
Remove-Item "C:\Windows\SoftwareDistribution\Download\*" -Recurse -Force -EA SilentlyContinue
Start-Service -Name wuauserv -EA SilentlyContinue
Start-Service -Name bits    -EA SilentlyContinue
Write-Host "[OK] Windows Update cache cleared"
'''
    return run_ps(script, cb)

def flush_dns(cb=None):
    if cb: cb("[INFO] Flushing DNS cache...")
    return run_ps('ipconfig /flushdns; Write-Host "[OK] DNS cache flushed"', cb)

def reset_network(cb=None):
    if cb: cb("[INFO] Resetting network stack...")
    script = r'''
netsh int ip reset
netsh winsock reset
netsh advfirewall reset
ipconfig /flushdns
ipconfig /release
ipconfig /renew
Write-Host "[OK] Network stack reset complete — reboot recommended"
'''
    return run_ps(script, cb)

def empty_recycle(cb=None):
    if cb: cb("[INFO] Emptying Recycle Bin...")
    script = r'''
$shell = New-Object -ComObject Shell.Application
$shell.Namespace(0xA).Items() | ForEach-Object { Remove-Item $_.Path -Recurse -Force -EA SilentlyContinue }
Write-Host "[OK] Recycle Bin emptied"
'''
    return run_ps(script, cb)

def clean_event_logs(cb=None):
    if cb: cb("[INFO] Clearing event logs...")
    script = r'''
Get-EventLog -List | ForEach-Object { Clear-EventLog -LogName $_.Log -EA SilentlyContinue }
Write-Host "[OK] Event logs cleared"
'''
    return run_ps(script, cb)


# ─────────────────────────── DEPENDENCIES ───────────────────────────
def install_dotnet(version: str, cb=None):
    if cb: cb(f"[INFO] Installing .NET {version} runtime...")
    script = f'winget install --id Microsoft.DotNet.Runtime.{version} --accept-source-agreements --accept-package-agreements -e; Write-Host "[OK] .NET {version} install complete"'
    return run_ps(script, cb)

def install_vcredist(cb=None):
    if cb: cb("[INFO] Installing VC++ Redistributables...")
    script = r'''
$ids = @(
    "Microsoft.VCRedist.2005.x86","Microsoft.VCRedist.2005.x64",
    "Microsoft.VCRedist.2008.x86","Microsoft.VCRedist.2008.x64",
    "Microsoft.VCRedist.2010.x86","Microsoft.VCRedist.2010.x64",
    "Microsoft.VCRedist.2012.x86","Microsoft.VCRedist.2012.x64",
    "Microsoft.VCRedist.2013.x86","Microsoft.VCRedist.2013.x64",
    "Microsoft.VCRedist.2015+.x86","Microsoft.VCRedist.2015+.x64"
)
foreach ($id in $ids) {
    winget install --id $id --accept-source-agreements --accept-package-agreements -e --silent 2>$null
}
Write-Host "[OK] All VC++ Redistributables installed"
'''
    return run_ps(script, cb)

def install_directx(cb=None):
    if cb: cb("[INFO] Installing DirectX...")
    script = r'winget install --id Microsoft.DirectX --accept-source-agreements --accept-package-agreements -e; Write-Host "[OK] DirectX install complete"'
    return run_ps(script, cb)

def install_webview2(cb=None):
    if cb: cb("[INFO] Installing WebView2 Runtime...")
    script = r'winget install --id Microsoft.EdgeWebView2Runtime --accept-source-agreements --accept-package-agreements -e; Write-Host "[OK] WebView2 install complete"'
    return run_ps(script, cb)

def install_xna(cb=None):
    if cb: cb("[INFO] Installing XNA Framework...")
    script = r'winget install --id Microsoft.XNAFramework --accept-source-agreements --accept-package-agreements -e; Write-Host "[OK] XNA install complete"'
    return run_ps(script, cb)


# ─────────────────────────── APP INSTALL ────────────────────────────
def install_app(app_id: str, manager: str, cb=None):
    if cb: cb(f"[INFO] Installing {app_id} via {manager}...")
    if manager == "winget":
        script = f'winget install --id "{app_id}" --accept-source-agreements --accept-package-agreements -e; Write-Host "[OK] {app_id} install complete"'
    else:
        script = f'choco install {app_id} -y; Write-Host "[OK] {app_id} install complete"'
    return run_ps(script, cb)


# ─────────────────────────── TWEAKS ─────────────────────────────────
# All verified against WinUtil (winutil.christitus.com)

def tweak_telemetry(enable=False, cb=None):
    """WinUtil: WPFTweaksTelemetry — 12 registry keys + services + scripts"""
    if cb: cb(f"[INFO] {'Disabling' if not enable else 'Enabling'} Telemetry (WinUtil-verified, 12 keys)...")
    v = "1" if enable else "0"
    v_inv = "0" if enable else "1"  # for keys that are inverted (restrict = 1 to disable)
    startup = "Automatic" if enable else "Disabled"
    consent = "1" if enable else "2"
    siuf_line = "Remove-ItemProperty -Path \'HKCU:\\Software\\Microsoft\\Siuf\\Rules\' -Name PeriodInNanoSeconds -EA SilentlyContinue" if not enable else ""
    tele_status = "enabled" if enable else "disabled"
    script = rf'''
# 12 registry keys from WinUtil WPFTweaksTelemetry
$reg = @(
    @{{P="HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\AdvertisingInfo";N="Enabled";V={v}}},
    @{{P="HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Privacy";N="TailoredExperiencesWithDiagnosticDataEnabled";V={v}}},
    @{{P="HKCU:\\Software\\Microsoft\\Speech_OneCore\\Settings\\OnlineSpeechPrivacy";N="HasAccepted";V={v}}},
    @{{P="HKCU:\\Software\\Microsoft\\Input\\TIPC";N="Enabled";V={v}}},
    @{{P="HKCU:\\Software\\Microsoft\\InputPersonalization";N="RestrictImplicitInkCollection";V={v_inv}}},
    @{{P="HKCU:\\Software\\Microsoft\\InputPersonalization";N="RestrictImplicitTextCollection";V={v_inv}}},
    @{{P="HKCU:\\Software\\Microsoft\\InputPersonalization\\TrainedDataStore";N="HarvestContacts";V={v}}},
    @{{P="HKCU:\\Software\\Microsoft\\Personalization\\Settings";N="AcceptedPrivacyPolicy";V={v}}},
    @{{P="HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection";N="AllowTelemetry";V={v}}},
    @{{P="HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced";N="Start_TrackProgs";V={v}}},
    @{{P="HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\System";N="PublishUserActivities";V={v}}},
    @{{P="HKCU:\\Software\\Microsoft\\Siuf\\Rules";N="NumberOfSIUFInPeriod";V={v}}}
)
foreach ($r in $reg) {{
    If(!(Test-Path $r.P)){{New-Item -Path $r.P -Force|Out-Null}}
    Set-ItemProperty -Path $r.P -Name $r.N -Value $r.V -Type DWord -Force -EA SilentlyContinue
}}
# Services
Set-Service -Name diagtrack -StartupType {startup} -EA SilentlyContinue
Set-Service -Name wermgr    -StartupType {startup} -EA SilentlyContinue
# Defender sample submission
Set-MpPreference -SubmitSamplesConsent {consent} -EA SilentlyContinue
# Remove SIUF PeriodInNanoSeconds if disabling
{siuf_line}
Write-Host "[OK] Telemetry {tele_status} (12 registry keys + services)"
'''
    return run_ps(script, cb)

def tweak_activity_history(enable=False, cb=None):
    """WinUtil: WPFTweaksActivity — 3 registry keys"""
    if cb: cb(f"[INFO] {'Enabling' if enable else 'Disabling'} Activity History...")
    v = "1" if enable else "0"
    script = rf'''
$p = "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\System"
If(!(Test-Path $p)){{New-Item -Path $p -Force|Out-Null}}
Set-ItemProperty $p -Name EnableActivityFeed     -Value {v} -Type DWord -Force -EA SilentlyContinue
Set-ItemProperty $p -Name PublishUserActivities  -Value {v} -Type DWord -Force -EA SilentlyContinue
Set-ItemProperty $p -Name UploadUserActivities   -Value {v} -Type DWord -Force -EA SilentlyContinue
Write-Host "[OK] Activity History {'enabled' if enable else 'disabled'} (3 keys)"
'''
    return run_ps(script, cb)

def tweak_location(enable=False, cb=None):
    """WinUtil: WPFTweaksLocation — 3 registry keys + lfsvc service (exact match)"""
    if cb: cb(f"[INFO] {'Enabling' if enable else 'Disabling'} Location Tracking...")
    consent_val  = "Allow" if enable else "Deny"
    sensor_val   = "1" if enable else "0"
    maps_val     = "1" if enable else "0"
    svc_start    = "Manual" if enable else "Disabled"   # OriginalType is Manual per WinUtil
    script = rf'''
# Key 1: ConsentStore — Type is String, not DWord
$p1 = "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\ConsentStore\\location"
If(!(Test-Path $p1)){{New-Item -Path $p1 -Force|Out-Null}}
Set-ItemProperty $p1 -Name Value -Value "{consent_val}" -Type String -Force -EA SilentlyContinue
# Key 2: SensorPermissionState — DWord
$p2 = "HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Sensor\\Overrides\\{{BFA794E4-F964-4FDB-90F6-51056BFE4B44}}"
If(!(Test-Path $p2)){{New-Item -Path $p2 -Force|Out-Null}}
Set-ItemProperty $p2 -Name SensorPermissionState -Value {sensor_val} -Type DWord -Force -EA SilentlyContinue
# Key 3: Maps AutoUpdate — DWord (HKLM:\SYSTEM\Maps per WinUtil)
$p3 = "HKLM:\\SYSTEM\\Maps"
If(!(Test-Path $p3)){{New-Item -Path $p3 -Force|Out-Null}}
Set-ItemProperty $p3 -Name AutoUpdateEnabled -Value {maps_val} -Type DWord -Force -EA SilentlyContinue
# Service: lfsvc — OriginalType is Manual
Set-Service -Name lfsvc -StartupType {svc_start} -EA SilentlyContinue
Write-Host "[OK] Location Tracking {'enabled' if enable else 'disabled'} (3 keys + lfsvc service)"
'''
    return run_ps(script, cb)

def tweak_consumer_features(enable=False, cb=None):
    """WinUtil: WPFTweaksConsumerFeatures — 1 registry key (exact match)"""
    if cb: cb(f"[INFO] {'Enabling' if enable else 'Disabling'} Consumer Features...")
    script = rf'''
$p = "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\CloudContent"
If(!(Test-Path $p)){{New-Item -Path $p -Force|Out-Null}}
{"Remove-ItemProperty $p -Name DisableWindowsConsumerFeatures -EA SilentlyContinue" if enable else 'Set-ItemProperty $p -Name DisableWindowsConsumerFeatures -Value 1 -Type DWord -Force -EA SilentlyContinue'}
Write-Host "[OK] Consumer Features {'enabled (key removed)' if enable else 'disabled'}"
'''
    return run_ps(script, cb)

def tweak_hibernation(enable=False, cb=None):
    """WinUtil: WPFTweaksHiber — 2 registry keys + powercfg (exact match)"""
    if cb: cb(f"[INFO] {'Enabling' if enable else 'Disabling'} Hibernation...")
    hiber_val  = "1" if enable else "0"
    flyout_val = "1" if enable else "0"
    cmd        = "powercfg.exe /hibernate on" if enable else "powercfg.exe /hibernate off"
    script = rf'''
# Key 1: HibernateEnabled
$p1 = "HKLM:\\System\\CurrentControlSet\\Control\\Session Manager\\Power"
Set-ItemProperty $p1 -Name HibernateEnabled -Value {hiber_val} -Type DWord -Force -EA SilentlyContinue
# Key 2: ShowHibernateOption (hide/show from power menu)
$p2 = "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FlyoutMenuSettings"
If(!(Test-Path $p2)){{New-Item -Path $p2 -Force|Out-Null}}
Set-ItemProperty $p2 -Name ShowHibernateOption -Value {flyout_val} -Type DWord -Force -EA SilentlyContinue
# InvokeScript
{cmd}
Write-Host "[OK] Hibernation {'enabled' if enable else 'disabled'} (2 registry keys + powercfg)"
'''
    return run_ps(script, cb)

def tweak_fast_startup(enable=True, cb=None):
    if cb: cb(f"[INFO] {'Enabling' if enable else 'Disabling'} Fast Startup...")
    v = "1" if enable else "0"
    script = rf'''
$p = "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Power"
Set-ItemProperty $p -Name HiberbootEnabled -Value {v} -Type DWord -Force -EA SilentlyContinue
Write-Host "[OK] Fast Startup {'enabled' if enable else 'disabled'}"
'''
    return run_ps(script, cb)

def tweak_show_extensions(enable=True, cb=None):
    """WinUtil: WPFToggleShowExt — HideFileExt DWord + Explorer restart (exact match)"""
    if cb: cb(f"[INFO] {'Showing' if enable else 'Hiding'} file extensions...")
    v = "0" if enable else "1"
    script = rf'''
Set-ItemProperty "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" -Name HideFileExt -Value {v} -Type DWord -Force -EA SilentlyContinue
# WinUtil InvokeScript: restart Explorer
Stop-Process -Name explorer -Force -EA SilentlyContinue
Write-Host "[OK] File extensions {'shown' if enable else 'hidden'} (Explorer restarted)"
'''
    return run_ps(script, cb)

def tweak_show_hidden(enable=True, cb=None):
    """WinUtil: WPFToggleHiddenFiles — Hidden DWord + Explorer restart (exact match)"""
    if cb: cb(f"[INFO] {'Showing' if enable else 'Hiding'} hidden files...")
    v = "1" if enable else "0"
    script = rf'''
Set-ItemProperty "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" -Name Hidden -Value {v} -Type DWord -Force -EA SilentlyContinue
# WinUtil InvokeScript: restart Explorer
Stop-Process -Name explorer -Force -EA SilentlyContinue
Write-Host "[OK] Hidden files {'shown' if enable else 'hidden'} (Explorer restarted)"
'''
    return run_ps(script, cb)

def tweak_copilot(enable=False, cb=None):
    """WinUtil: WPFTweaksRemoveCopilot — removes Copilot AppX packages (exact match)"""
    if cb: cb(f"[INFO] {'Restoring' if enable else 'Removing'} Microsoft Copilot...")
    if not enable:
        script = r'''
# WinUtil WPFTweaksRemoveCopilot: remove Copilot AppX packages
Get-AppxPackage -AllUsers *Copilot* | Remove-AppxPackage -AllUsers -EA SilentlyContinue
Get-AppxPackage -AllUsers Microsoft.MicrosoftOfficeHub | Remove-AppxPackage -AllUsers -EA SilentlyContinue
$Appx = (Get-AppxPackage MicrosoftWindows.Client.CoreAI -EA SilentlyContinue).PackageFullName
if ($Appx) {
    $Sid = (Get-LocalUser $Env:UserName).Sid.Value
    New-Item "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\EndOfLife\$Sid\$Appx" -Force -EA SilentlyContinue
    Remove-AppxPackage $Appx -EA SilentlyContinue
}
Write-Host "[OK] Copilot removed"
'''
    else:
        # WinUtil UndoScript: reinstall via winget
        script = r'''
winget install --name Copilot --source msstore --accept-package-agreements --accept-source-agreements --silent
Write-Host "[OK] Copilot reinstalled via winget"
'''
    return run_ps(script, cb)

def tweak_widgets(remove=True, cb=None):
    """WinUtil: WPFTweaksWidget — stops Widget process first, removes both AppX packages (exact match)"""
    if cb: cb(f"[INFO] {'Removing' if remove else 'Restoring'} Widgets...")
    if remove:
        script = r'''
# WinUtil: stop process first or removal may fail
Get-Process *Widget* | Stop-Process -Force -EA SilentlyContinue
Get-AppxPackage Microsoft.WidgetsPlatformRuntime -AllUsers | Remove-AppxPackage -AllUsers -EA SilentlyContinue
Get-AppxPackage MicrosoftWindows.Client.WebExperience -AllUsers | Remove-AppxPackage -AllUsers -EA SilentlyContinue
# Restart Explorer
Stop-Process -Name explorer -Force -EA SilentlyContinue
Write-Host "[OK] Widgets removed (both AppX packages)"
'''
    else:
        script = r'''
# WinUtil UndoScript: re-register from WindowsApps directory
Add-AppxPackage -Register "C:\Program Files\WindowsApps\Microsoft.WidgetsPlatformRuntime*\AppxManifest.xml" -DisableDevelopmentMode -EA SilentlyContinue
Add-AppxPackage -Register "C:\Program Files\WindowsApps\MicrosoftWindows.Client.WebExperience*\AppxManifest.xml" -DisableDevelopmentMode -EA SilentlyContinue
Write-Host "[OK] Widgets restored (attempted re-register from WindowsApps)"
'''
    return run_ps(script, cb)

def tweak_services(optimize=True, cb=None):
    """WinUtil: WPFTweaksServices — exact 5 services + SvcHostSplitThreshold (exact match)"""
    if cb: cb("[INFO] Setting services per WinUtil (5 services + SvcHostSplitThreshold)...")
    if optimize:
        script = r'''
# WinUtil exact service list — CscService, DiagTrack, MapsBroker, StorSvc, SharedAccess
Set-Service -Name CscService    -StartupType Disabled -EA SilentlyContinue
Set-Service -Name DiagTrack     -StartupType Disabled -EA SilentlyContinue
Set-Service -Name MapsBroker    -StartupType Manual   -EA SilentlyContinue
Set-Service -Name StorSvc       -StartupType Manual   -EA SilentlyContinue
Set-Service -Name SharedAccess  -StartupType Disabled -EA SilentlyContinue
# SvcHostSplitThreshold — set to total RAM so each svchost hosts its own service
$Memory = (Get-CimInstance Win32_PhysicalMemory | Measure-Object Capacity -Sum).Sum / 1KB
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control" -Name SvcHostSplitThresholdInKB -Value $Memory -Force -EA SilentlyContinue
Write-Host "[OK] Services optimized (WinUtil: 5 services + SvcHostSplitThreshold set to ${Memory}KB)"
'''
    else:
        script = r'''
# Restore original startup types per WinUtil OriginalType values
Set-Service -Name CscService    -StartupType Manual    -EA SilentlyContinue
Set-Service -Name DiagTrack     -StartupType Automatic -EA SilentlyContinue
Set-Service -Name MapsBroker    -StartupType Automatic -EA SilentlyContinue
Set-Service -Name StorSvc       -StartupType Automatic -EA SilentlyContinue
Set-Service -Name SharedAccess  -StartupType Automatic -EA SilentlyContinue
# Restore SvcHostSplitThreshold to Windows default (380000 KB)
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control" -Name SvcHostSplitThresholdInKB -Value 380000 -Force -EA SilentlyContinue
Write-Host "[OK] Services restored to original startup types"
'''
    return run_ps(script, cb)

def tweak_num_lock(enable=True, cb=None):
    """WinUtil: WPFToggleNumLock - 2 keys (HKU Default + HKCU), Type=String (exact match)"""
    if cb: cb(f"[INFO] Setting NumLock on startup: {enable}...")
    v = "2" if enable else "0"
    script = rf'''
# WinUtil sets both HKU\\.Default (system default for new logins) and HKCU (current user)
# Type is String per WinUtil, not DWord
Set-ItemProperty "HKU:\\.Default\\Control Panel\\Keyboard" -Name InitialKeyboardIndicators -Value "{v}" -Type String -Force -EA SilentlyContinue
Set-ItemProperty "HKCU:\\Control Panel\\Keyboard" -Name InitialKeyboardIndicators -Value "{v}" -Type String -Force -EA SilentlyContinue
Write-Host "[OK] NumLock on startup {'enabled' if enable else 'disabled'} (2 keys, String type)"
'''
    return run_ps(script, cb)

def tweak_verbose_logon(enable=True, cb=None):
    if cb: cb(f"[INFO] {'Enabling' if enable else 'Disabling'} verbose logon messages...")
    v = "1" if enable else "0"
    script = rf'''
$p = "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System"
Set-ItemProperty $p -Name VerboseStatus -Value {v} -Type DWord -Force -EA SilentlyContinue
Write-Host "[OK] Verbose logon {'enabled' if enable else 'disabled'}"
'''
    return run_ps(script, cb)

def tweak_dark_mode(enable=True, cb=None):
    """WinUtil: WPFToggleDarkMode — AppsUseLightTheme + SystemUsesLightTheme + Explorer restart (exact match)"""
    if cb: cb(f"[INFO] Switching to {'Dark' if enable else 'Light'} mode...")
    v = "0" if enable else "1"
    script = rf'''
# WinUtil uses HKCU:\SOFTWARE (uppercase) and restarts Explorer
$p = "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"
If(!(Test-Path $p)){{New-Item -Path $p -Force|Out-Null}}
Set-ItemProperty $p -Name AppsUseLightTheme    -Value {v} -Type DWord -Force -EA SilentlyContinue
Set-ItemProperty $p -Name SystemUsesLightTheme -Value {v} -Type DWord -Force -EA SilentlyContinue
# WinUtil InvokeScript: restart Explorer
Stop-Process -Name explorer -Force -EA SilentlyContinue
Write-Host "[OK] {'Dark' if enable else 'Light'} mode applied (Explorer restarted)"
'''
    return run_ps(script, cb)

def tweak_power_plan(plan="balanced", cb=None):
    """Power plans: Ultimate Performance uses WinUtil's exact powercfg -duplicatescheme method.
    Balanced and Power Saver use standard GUIDs (not WinUtil-sourced, our own additions)."""
    if cb: cb(f"[INFO] Setting power plan to {plan}...")
    if plan == "ultimate":
        # WinUtil: Invoke-WPFUltimatePerformance — duplicate the hidden scheme and activate it
        script = r'''
$ultimatePlan = powercfg -list | Select-String -Pattern "Ultimate Performance"
if ($ultimatePlan) {
    Write-Host "[INFO] Ultimate Performance plan already installed"
} else {
    powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61
    Write-Host "[INFO] Ultimate Performance plan installed"
}
$guid = (powercfg -list | Select-String -Pattern "Ultimate Performance" | ForEach-Object { $_ -replace '.*\(([a-f0-9-]+)\).*','$1' }).Trim()
powercfg /setactive $guid
Write-Host "[OK] Ultimate Performance power plan activated"
'''
    elif plan == "balanced":
        script = r'powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e; Write-Host "[OK] Balanced power plan set"'
    else:  # power_saver
        script = r'powercfg /setactive a1841308-3541-4fab-bc81-f71556f20b4a; Write-Host "[OK] Power Saver plan set"'
    return run_ps(script, cb)


# ─────────────────────────── BROWSER DEBLOAT ────────────────────────
def debloat_edge(cb=None):
    """WinUtil: WPFTweaksEdgeDebloat — all 17 verified registry entries"""
    if cb: cb("[INFO] Debloating Microsoft Edge (WinUtil-verified, 17 entries)...")
    script = r'''
$p = "HKLM:\SOFTWARE\Policies\Microsoft\Edge"
If(!(Test-Path $p)){New-Item -Path $p -Force|Out-Null}
$settings = @{
    "HideFirstRunExperience"=1;"SendSiteInfoToImproveServices"=0;
    "MetricsReportingEnabled"=1;"EdgeShoppingAssistantEnabled"=0;
    "PersonalizationReportingEnabled"=0;"ShowRecommendationsEnabled"=0;
    "EdgeCollectionsEnabled"=0;"EdgeFollowEnabled"=0;
    "NetworkPredictionOptions"=2;"SearchSuggestEnabled"=0;
    "ShowMicrosoftRewards"=0;"SpotlightExperiencesAndRecommendationsEnabled"=0;
    "TabServicesEnabled"=0;"WebWidget"=0;
    "StartupBoostEnabled"=0;"BackgroundModeEnabled"=0;
    "BrowserAddProfileEnabled"=0
}
foreach ($k in $settings.Keys) {
    Set-ItemProperty $p -Name $k -Value $settings[$k] -Type DWord -Force -EA SilentlyContinue
}
Write-Host "[OK] Edge debloated (17 entries)"
'''
    return run_ps(script, cb)

def debloat_brave(cb=None):
    """WinUtil: WPFTweaksBraveDebloat — all 12 verified registry entries"""
    if cb: cb("[INFO] Debloating Brave Browser (WinUtil-verified, 12 entries)...")
    script = r'''
$p = "HKLM:\SOFTWARE\Policies\BraveSoftware\Brave"
If(!(Test-Path $p)){New-Item -Path $p -Force|Out-Null}
$settings = @{
    "BraveRewardsDisabled"=1;"BraveWalletDisabled"=1;
    "BraveVPNDisabled"=1;"MetricsReportingEnabled"=0;
    "BraveAIChatEnabled"=0;"BraveNewsEnabled"=0;
    "BraveSearchDefaultInPrivateWindowsEnabled"=0;"BraveShieldsEnabled"=1;
    "BraveShieldsSettingsVersion"=2;"SafeBrowsingEnabled"=1;
    "PasswordManagerEnabled"=0;"AutofillCreditCardEnabled"=0
}
foreach ($k in $settings.Keys) {
    Set-ItemProperty $p -Name $k -Value $settings[$k] -Type DWord -Force -EA SilentlyContinue
}
Write-Host "[OK] Brave debloated (12 entries)"
'''
    return run_ps(script, cb)


# ─────────────────────────── APP REMOVAL ────────────────────────────
def check_app_installed(package_name: str) -> bool:
    script = f'$r = Get-AppxPackage -Name "*{package_name}*" -EA SilentlyContinue; if($r){{Write-Host "FOUND"}}else{{Write-Host "NOT_FOUND"}}'
    result = run_ps(script)
    return "FOUND" in result

def remove_app(package_name: str, display_name: str, cb=None):
    if cb: cb(f"[INFO] Checking if {display_name} is installed...")
    if not check_app_installed(package_name):
        if cb: cb(f"[INFO] {display_name} is not installed — skipping")
        return
    if cb: cb(f"[INFO] Removing {display_name}...")
    script = rf'''
Get-AppxPackage -Name "*{package_name}*" | Remove-AppxPackage -EA SilentlyContinue
Get-AppxProvisionedPackage -Online | Where-Object DisplayName -like "*{package_name}*" | Remove-AppxProvisionedPackage -Online -EA SilentlyContinue
$verify = Get-AppxPackage -Name "*{package_name}*" -EA SilentlyContinue
if(!$verify){{Write-Host "[OK] {display_name} removed successfully"}}else{{Write-Host "[WARN] {display_name} may still be present"}}
'''
    return run_ps(script, cb)


# ─────────────────────────── DNS ────────────────────────────────────
DNS_PROVIDERS = {
    "Cloudflare":         (["1.1.1.1","1.0.0.1"],  ["2606:4700:4700::1111","2606:4700:4700::1001"]),
    "Google":             (["8.8.8.8","8.8.4.4"],   ["2001:4860:4860::8888","2001:4860:4860::8844"]),
    "Quad9 (Malware Block)":   (["9.9.9.9","149.112.112.112"], ["2620:fe::fe","2620:fe::9"]),
    "OpenDNS":            (["208.67.222.222","208.67.220.220"], []),
    "AdGuard":            (["94.140.14.14","94.140.15.15"], ["2a10:50c0::ad1:ff","2a10:50c0::ad2:ff"]),
    "Cloudflare Family":  (["1.1.1.3","1.0.0.3"],  ["2606:4700:4700::1113","2606:4700:4700::1003"]),
    "Automatic (DHCP)":   ([], []),
}

def set_dns(provider: str, cb=None):
    if cb: cb(f"[INFO] Setting DNS to {provider}...")
    ipv4, ipv6 = DNS_PROVIDERS.get(provider, ([], []))
    if not ipv4:
        script = r'''
$adapters = Get-NetAdapter | Where-Object {$_.Status -eq "Up"}
foreach ($a in $adapters) {
    Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ResetServerAddresses
}
ipconfig /flushdns
Write-Host "[OK] DNS reset to automatic (DHCP)"
'''
    else:
        primary, secondary = ipv4[0], ipv4[1] if len(ipv4) > 1 else ipv4[0]
        pv6_block = ""
        if ipv6:
            pv6_block = f'Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ServerAddresses ("{ipv6[0]}","{ipv6[1] if len(ipv6)>1 else ipv6[0]}")'
        script = rf'''
$adapters = Get-NetAdapter | Where-Object {{$_.Status -eq "Up"}}
foreach ($a in $adapters) {{
    Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ServerAddresses ("{primary}","{secondary}")
}}
ipconfig /flushdns
Write-Host "[OK] DNS set to {provider} ({primary} / {secondary})"
'''
    return run_ps(script, cb)


# ─────────────────────────── WINDOWS UPDATES ────────────────────────
def set_updates_default(cb=None):
    """WinUtil: Invoke-WPFUpdatesdefault — removes all custom update policy keys"""
    if cb: cb("[INFO] Restoring Windows Update to defaults (WinUtil-verified)...")
    script = r'''
# WinUtil Invoke-WPFUpdatesdefault: remove all custom policy keys and restore services
$ErrorActionPreference = 'SilentlyContinue'
$registryPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
$AUregistryPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
If (Test-Path $registryPath) {
    Remove-ItemProperty -Path $registryPath -Name "ExcludeWUDriversInQualityUpdate" -EA SilentlyContinue
    Remove-ItemProperty -Path $registryPath -Name "DisableWindowsUpdateAccess"      -EA SilentlyContinue
}
If (Test-Path $AUregistryPath) {
    Remove-ItemProperty -Path $AUregistryPath -Name "NoAutoUpdate"      -EA SilentlyContinue
    Remove-ItemProperty -Path $AUregistryPath -Name "AUOptions"         -EA SilentlyContinue
    Remove-ItemProperty -Path $AUregistryPath -Name "NoAutoRebootWithLoggedOnUsers" -EA SilentlyContinue
    Remove-ItemProperty -Path $AUregistryPath -Name "ScheduledInstallDay"  -EA SilentlyContinue
    Remove-ItemProperty -Path $AUregistryPath -Name "ScheduledInstallTime" -EA SilentlyContinue
}
# Also remove DeliveryOptimization override if set by disable
$doPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\DeliveryOptimization\Config"
If (Test-Path $doPath) {
    Remove-ItemProperty -Path $doPath -Name "DODownloadMode" -EA SilentlyContinue
}
# Re-enable services disabled by WPFUpdatesdisable
Set-Service -Name BITS     -StartupType Automatic -EA SilentlyContinue
Set-Service -Name wuauserv -StartupType Automatic -EA SilentlyContinue
Set-Service -Name UsoSvc   -StartupType Automatic -EA SilentlyContinue
# Re-enable update scheduled tasks
$Tasks = '\Microsoft\Windows\InstallService\*','\Microsoft\Windows\UpdateOrchestrator\*','\Microsoft\Windows\UpdateAssistant\*','\Microsoft\Windows\WaaSMedic\*','\Microsoft\Windows\WindowsUpdate\*','\Microsoft\WindowsUpdate\*'
foreach ($Task in $Tasks) {
    Get-ScheduledTask -TaskPath $Task -EA SilentlyContinue | Enable-ScheduledTask -EA SilentlyContinue
}
Write-Host "[OK] Windows Update restored to defaults"
'''
    return run_ps(script, cb)

def set_updates_security_only(cb=None):
    """WinUtil: Invoke-WPFUpdatessecurity — defer feature updates 365 days, quality 0 days"""
    if cb: cb("[INFO] Setting Windows Update to security only (WinUtil-verified)...")
    script = r'''
$ErrorActionPreference = 'SilentlyContinue'
$registryPath    = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
$AUregistryPath  = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
If (!(Test-Path $registryPath)) { New-Item -Path $registryPath -Force | Out-Null }
If (!(Test-Path $AUregistryPath)) { New-Item -Path $AUregistryPath -Force | Out-Null }
# Defer feature updates by 365 days, quality updates by 0
Set-ItemProperty $registryPath -Name "DeferQualityUpdates"             -Value 1 -Type DWord -Force
Set-ItemProperty $registryPath -Name "DeferQualityUpdatesPeriodInDays" -Value 0 -Type DWord -Force
Set-ItemProperty $registryPath -Name "DeferFeatureUpdates"             -Value 1 -Type DWord -Force
Set-ItemProperty $registryPath -Name "DeferFeatureUpdatesPeriodInDays" -Value 365 -Type DWord -Force
Set-ItemProperty $registryPath -Name "ExcludeWUDriversInQualityUpdate" -Value 1 -Type DWord -Force
Set-ItemProperty $AUregistryPath -Name "NoAutoUpdate" -Value 0 -Type DWord -Force
Set-ItemProperty $AUregistryPath -Name "AUOptions"    -Value 3 -Type DWord -Force
Write-Host "[OK] Windows Update set to Security Only (feature updates deferred 365 days)"
'''
    return run_ps(script, cb)

def set_updates_disable(cb=None):
    """WinUtil: Invoke-WPFUpdatesdisable — disables BITS/wuauserv/UsoSvc, clears SoftwareDistribution, disables tasks"""
    if cb: cb("[INFO] Disabling Windows Update (WinUtil-verified)...")
    script = r'''
$ErrorActionPreference = 'SilentlyContinue'
# Registry
New-Item -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" -Force | Out-Null
Set-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" -Name "NoAutoUpdate" -Type DWord -Value 1 -Force
Set-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" -Name "AUOptions"    -Type DWord -Value 1 -Force
New-Item -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\DeliveryOptimization\Config" -Force | Out-Null
Set-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\DeliveryOptimization\Config" -Name "DODownloadMode" -Type DWord -Value 0 -Force
# Disable services
Set-Service -Name BITS     -StartupType Disabled
Set-Service -Name wuauserv -StartupType Disabled
Set-Service -Name UsoSvc   -StartupType Disabled
# Clear SoftwareDistribution cache
Remove-Item "C:\Windows\SoftwareDistribution\*" -Recurse -Force -EA SilentlyContinue
Write-Host "[INFO] Cleared SoftwareDistribution folder"
# Disable update scheduled tasks
$Tasks = '\Microsoft\Windows\InstallService\*','\Microsoft\Windows\UpdateOrchestrator\*','\Microsoft\Windows\UpdateAssistant\*','\Microsoft\Windows\WaaSMedic\*','\Microsoft\Windows\WindowsUpdate\*','\Microsoft\WindowsUpdate\*'
foreach ($Task in $Tasks) {
    Get-ScheduledTask -TaskPath $Task -EA SilentlyContinue | Disable-ScheduledTask -EA SilentlyContinue
}
Write-Host "[OK] Windows Update disabled (services + registry + tasks)"
Write-Host "[WARN] Reboot recommended for all changes to take effect"
'''
    return run_ps(script, cb)


# ─────────────────────────── REGISTRY HEALTH ────────────────────────
def scan_broken_uninstall(cb=None):
    if cb: cb("[INFO] Scanning for broken uninstall entries...")
    script = r'''
$paths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
)
$broken = @()
foreach ($base in $paths) {
    if(!(Test-Path $base)){continue}
    Get-ChildItem $base -EA SilentlyContinue | ForEach-Object {
        $props = Get-ItemProperty $_.PSPath -EA SilentlyContinue
        $unst  = $props.UninstallString
        $name  = $props.DisplayName
        if ($name -and $unst) {
            if ($unst -match '^"?([A-Za-z]:[^"]+\.exe)"?') {
                $exe = $Matches[1]
                if (!(Test-Path $exe)) {
                    $broken += "$name | $exe"
                    Write-Host "[BROKEN] $name"
                }
            }
        }
    }
}
if($broken.Count -eq 0){Write-Host "[OK] No broken uninstall entries found"}
else{Write-Host "[WARN] Found $($broken.Count) broken entries — run clean to remove"}
'''
    return run_ps(script, cb)

def clean_broken_uninstall(cb=None):
    if cb: cb("[INFO] Cleaning broken uninstall entries (backing up first)...")
    script = r'''
$backup = "$env:USERPROFILE\Desktop\WinForge_Registry_Backup_$(Get-Date -f 'yyyyMMdd_HHmmss').reg"
reg export "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" $backup /y | Out-Null
Write-Host "[INFO] Backup saved to $backup"
$paths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
)
$removed = 0
foreach ($base in $paths) {
    if(!(Test-Path $base)){continue}
    Get-ChildItem $base -EA SilentlyContinue | ForEach-Object {
        $props = Get-ItemProperty $_.PSPath -EA SilentlyContinue
        $unst  = $props.UninstallString
        $name  = $props.DisplayName
        if ($name -and $unst) {
            if ($unst -match '^"?([A-Za-z]:[^"]+\.exe)"?') {
                if (!(Test-Path $Matches[1])) {
                    Remove-Item $_.PSPath -Recurse -Force -EA SilentlyContinue
                    $removed++
                    Write-Host "[OK] Removed: $name"
                }
            }
        }
    }
}
Write-Host "[OK] Cleaned $removed broken uninstall entries"
'''
    return run_ps(script, cb)


# ─────────────────────────── RESTORE POINTS ─────────────────────────
def create_restore_point(description: str = "WinForge Manual Restore Point", cb=None):
    if cb: cb(f"[INFO] Creating restore point: {description}...")
    script = rf'''
Enable-ComputerRestore -Drive "C:\\" -EA SilentlyContinue
# Bypass 24h limit
$key = "HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SystemRestore"
Set-ItemProperty $key -Name SystemRestorePointCreationFrequency -Value 0 -Type DWord -Force -EA SilentlyContinue
Checkpoint-Computer -Description "{description}" -RestorePointType MODIFY_SETTINGS -EA Stop
Write-Host "[OK] Restore point created: {description}"
'''
    return run_ps(script, cb)


"""
WinForge — Windows Toolkit
v5: Fixed toast notifications, GPU VRAM, verified tweaks
"""
import customtkinter as ctk
import threading, sys, os
from datetime import datetime

# (operations merged below)

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
        self.title("WinForge — Windows Toolkit")
        self.geometry("1100x750")
        self.minsize(900, 600)
        self.configure(fg_color=BG)

        self._restore_point_this_session = False
        self._toasts: list = []
        self._log_visible = True

        self._build_layout()
        self._build_nav()
        self._build_log()
        self._show_tab("System Info")

    # ─── Layout skeleton ─────────────────────────────────────────
    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self._sidebar = ctk.CTkFrame(self, width=200, fg_color=PANEL, corner_radius=0)
        self._sidebar.grid(row=0, column=0, rowspan=2, sticky="nsw")
        self._sidebar.grid_propagate(False)
        self._sidebar.grid_rowconfigure(14, weight=1)

        # Main area
        self._main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._main.grid(row=0, column=1, sticky="nsew")
        self._main.grid_columnconfigure(0, weight=1)
        self._main.grid_rowconfigure(1, weight=1)

    def _build_nav(self):
        ctk.CTkLabel(self._sidebar, text="WinForge",
            font=ctk.CTkFont(family=FONT, size=18, weight="bold"),
            text_color=ACCENT).grid(row=0, column=0, padx=14, pady=(16,10), sticky="w")

        sep = ctk.CTkFrame(self._sidebar, height=1, fg_color=BORDER)
        sep.grid(row=1, column=0, sticky="ew", padx=10, pady=(0,8))

        self._nav_btns = {}
        tabs = [
            "System Info",
            "Repair",
            "Cleanup",
            "Dependencies",
            "Install Apps",
            "Tweaks & Debloat",
            "DNS Settings",
            "Win Updates",
            "Registry Health",
            "System Tools",
            "Restore Points",
        ]
        for i, name in enumerate(tabs):
            btn = ctk.CTkButton(self._sidebar, text=name,
                font=ctk.CTkFont(family=FONT, size=12), anchor="w",
                fg_color="transparent", hover_color=HOVER, text_color=TEXT2,
                corner_radius=6, height=34,
                command=lambda n=name: self._show_tab(n))
            btn.grid(row=i+2, column=0, padx=8, pady=1, sticky="ew")
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
        clean = message
        for prefix in ["[OK] ", "[WARN] ", "[ERROR] ", "[INFO] "]:
            clean = clean.replace(prefix, "")
        if len(clean) > 72:
            clean = clean[:72] + "..."

        color = SUCCESS if kind == "ok" else WARN if kind == "warn" else DANGER
        icon  = "✓" if kind == "ok" else "⚠" if kind == "warn" else "✗"
        title = "Done" if kind == "ok" else "Warning" if kind == "warn" else "Error"

        # Build toast as a toplevel-style frame placed via place() on root window
        toast = ctk.CTkFrame(self, fg_color=CARD2, corner_radius=8,
                             border_width=1, border_color=color)

        # Stack toasts — each one placed above the previous ones
        offset_y = -20 - (len(self._toasts) * 78)
        toast.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=offset_y)
        toast.lift()

        # Accent bar
        ctk.CTkFrame(toast, fg_color=color, width=5, corner_radius=0
            ).pack(side="left", fill="y")

        # Content
        body = ctk.CTkFrame(toast, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=(10, 8), pady=8)

        # Top row: icon + title + close
        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=icon, font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                     text_color=color, width=20).pack(side="left")
        ctk.CTkLabel(top, text=title, font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                     text_color=TEXT).pack(side="left", padx=(4, 0))
        ctk.CTkButton(top, text="✕", width=20, height=20,
            font=ctk.CTkFont(family=FONT, size=9),
            fg_color="transparent", hover_color=HOVER, text_color=TEXT3,
            corner_radius=4, command=lambda t=toast: self._dismiss_toast(t)
            ).pack(side="right")

        # Message
        ctk.CTkLabel(body, text=clean, font=ctk.CTkFont(family=FONT, size=10),
                     text_color=TEXT2, wraplength=280, justify="left", anchor="w"
                     ).pack(fill="x", pady=(2, 0))

        self._toasts.append(toast)
        self.after(5000, lambda t=toast: self._dismiss_toast(t))

    def _restack_toasts(self):
        """Re-place remaining toasts so there are no gaps after one is dismissed."""
        for i, t in enumerate(self._toasts):
            offset_y = -20 - (i * 78)
            try:
                t.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=offset_y)
            except Exception:
                pass

    def _dismiss_toast(self, toast):
        try:
            toast.destroy()
            if toast in self._toasts:
                self._toasts.remove(toast)
            self._restack_toasts()
        except Exception:
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
