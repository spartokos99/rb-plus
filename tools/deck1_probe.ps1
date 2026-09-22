# Local integration-test helper for the prepared, single-loaded-deck 4Deck layout.
# Uses the live BPM field in the Performance deck, never the collection BPM column.
param(
    [ValidateSet('Bpm','PlayPause','Drag')][string]$Action,
    [ValidateRange(1,999)][double]$Bpm = 174
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class RbProbeInput {
 [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X,Y; }
 [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);
 [DllImport("user32.dll")] public static extern void mouse_event(uint flags,uint x,uint y,uint data,UIntPtr extra);
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
 [StructLayout(LayoutKind.Sequential)] public struct GUI {
  public uint size,flags; public IntPtr active,focus,capture,menu,move,caret; public RECT rect;
 }
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
 [DllImport("user32.dll")] public static extern bool GetGUIThreadInfo(uint thread, ref GUI info);
 [DllImport("user32.dll", SetLastError=true)] public static extern IntPtr SendMessageTimeoutW(IntPtr h,uint msg,UIntPtr w,IntPtr l,uint flags,uint ms,out UIntPtr result);
}
'@
[void][RbProbeInput]::SetProcessDPIAware()
$rbProc=Get-Process -Name rekordbox
$rbRoot=[System.Windows.Automation.AutomationElement]::FromHandle($rbProc.MainWindowHandle)
$elements=$rbRoot.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
if (-not ($elements | Where-Object { $_.Current.Name -eq 'PERFORMANCE' })) { throw 'PERFORMANCE not detected' }
if ($Action -eq 'PlayPause') {
    $buttons=@($elements | Where-Object { $_.Current.Name -eq 'Play/Pause' })
    if ($buttons.Count -ne 4) { throw 'Expected four deck Play/Pause controls' }
    $buttons[0].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    exit
}
$edits=@($elements | Where-Object { $_.Current.ControlType -eq [System.Windows.Automation.ControlType]::Edit -and $_.Current.Name -match '^\s+\d+\.\d{2}$' })
if ($edits.Count -ne 1) { throw 'Expected exactly one loaded deck with a live BPM field' }
if ($Action -eq 'Drag') {
    [void][RbProbeInput]::SetForegroundWindow($rbProc.MainWindowHandle)
    $bounds=$edits[0].Current.BoundingRectangle
    $start=New-Object RbProbeInput+POINT
    $saved=New-Object RbProbeInput+POINT
    $start.X=[int]($bounds.X+$bounds.Width/2); $start.Y=[int]($bounds.Y+$bounds.Height/2)
    $pointPid=0
    [void][RbProbeInput]::GetWindowThreadProcessId([RbProbeInput]::WindowFromPoint($start),[ref]$pointPid)
    if ($pointPid -ne $rbProc.Id) { throw 'Live BPM field is covered by another application' }
    [void][RbProbeInput]::GetCursorPos([ref]$saved)
    try {
        [void][RbProbeInput]::SetCursorPos($start.X,$start.Y)
        [RbProbeInput]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
        for($i=1;$i -le 80;$i++) {
            [void][RbProbeInput]::SetCursorPos($start.X,$start.Y-$i)
            Start-Sleep -Milliseconds 15
        }
    } finally {
        [RbProbeInput]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
        [void][RbProbeInput]::SetCursorPos($saved.X,$saved.Y)
    }
    exit
}
$edits[0].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
$windowPid=0
$thread=[RbProbeInput]::GetWindowThreadProcessId($rbProc.MainWindowHandle,[ref]$windowPid)
$gui=New-Object RbProbeInput+GUI
$gui.size=[Runtime.InteropServices.Marshal]::SizeOf($gui)
if (-not [RbProbeInput]::GetGUIThreadInfo($thread,[ref]$gui) -or $windowPid -ne $rbProc.Id) { throw 'Invalid GUI thread' }
$focusPid=0
[void][RbProbeInput]::GetWindowThreadProcessId($gui.focus,[ref]$focusPid)
if ($focusPid -ne $rbProc.Id) { throw 'Focus belongs to another process' }
$result=[UIntPtr]::Zero
$text=$Bpm.ToString('F2',[Globalization.CultureInfo]::InvariantCulture)
foreach($character in $text.ToCharArray()) {
    if ([RbProbeInput]::SendMessageTimeoutW($gui.focus,0x102,[UIntPtr][uint32][char]$character,[IntPtr]::Zero,2,2000,[ref]$result) -eq [IntPtr]::Zero) { throw 'Character input timed out' }
}
foreach($message in @(0x100,0x101)) {
    if ([RbProbeInput]::SendMessageTimeoutW($gui.focus,$message,[UIntPtr][uint32]13,[IntPtr]::Zero,2,2000,[ref]$result) -eq [IntPtr]::Zero) { throw 'Enter key timed out' }
}
