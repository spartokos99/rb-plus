param([string]$OutputPath = (Join-Path $PSScriptRoot '..\artifacts\rekordbox-window.png'))
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class RbWindowCapture {
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
 public struct RECT { public int L,T,R,B; }
}
'@
[void][RbWindowCapture]::SetProcessDPIAware()
$rbHandle=(Get-Process -Name rekordbox).MainWindowHandle
$rect=New-Object RbWindowCapture+RECT
[void][RbWindowCapture]::GetWindowRect($rbHandle,[ref]$rect)
$bmp=New-Object System.Drawing.Bitmap(($rect.R-$rect.L),($rect.B-$rect.T))
$graphics=[System.Drawing.Graphics]::FromImage($bmp)
$dc=$graphics.GetHdc()
try { $ok=[RbWindowCapture]::PrintWindow($rbHandle,$dc,2) } finally { $graphics.ReleaseHdc($dc) }
try { if (-not $ok) { throw 'PrintWindow failed' }; $bmp.Save([IO.Path]::GetFullPath($OutputPath)) }
finally { $graphics.Dispose(); $bmp.Dispose() }
