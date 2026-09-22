param(
    [ValidateSet('Open','Close','Status','Page','Default','0.1','1')][string]$Action,
    [ValidateSet('RB PLUS','STEMS','Video','Lighting','Extensions','Audio','View')][string]$Page='RB PLUS'
)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class RbPrefsProbe {
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern IntPtr GetPropW(IntPtr h,string name);
 [DllImport("user32.dll")] public static extern IntPtr GetDlgItem(IntPtr h,int id);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern IntPtr SendMessageTimeoutW(IntPtr h,uint m,UIntPtr w,IntPtr l,uint flags,uint ms,out UIntPtr result);
 [DllImport("user32.dll")] public static extern bool PostMessageW(IntPtr h,uint m,UIntPtr w,IntPtr l);
}
'@
$rb=Get-Process -Name rekordbox
function Get-RbWindows {
    $condition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$rb.Id)
    return [System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,$condition)
}
$windows=Get-RbWindows
$prefs=$windows | Where-Object {$_.Current.Name -in @('Preferences','Einstellungen')} | Select-Object -First 1
if(-not $prefs -and $Action -ne 'Close') {
    $main=$windows | Where-Object {$_.Current.Name -eq 'rekordbox'} | Select-Object -First 1
    $items=$main.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
    $button=$items | Where-Object {$_.Current.HelpText -like 'Preferences:*'} | Select-Object -First 1
    if(-not $button) { throw 'Preferences button not found' }
    $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    for($attempt=0;$attempt -lt 30 -and -not $prefs;$attempt++) {
        Start-Sleep -Milliseconds 100
        $prefs=Get-RbWindows | Where-Object {$_.Current.Name -in @('Preferences','Einstellungen')} | Select-Object -First 1
    }
}
if(-not $prefs) { if($Action -eq 'Close') { exit }; throw 'Preferences did not open' }
$handle=[IntPtr]$prefs.Current.NativeWindowHandle
if($Action -eq 'Open') { exit }
if($Action -eq 'Close') { [void][RbPrefsProbe]::PostMessageW($handle,0x10,[UIntPtr]::Zero,[IntPtr]::Zero); exit }
$tabs=[RbPrefsProbe]::GetPropW($handle,'RBQ.ExtensionsTabs')
if($Action -eq 'Page') {
    [void][RbPrefsProbe]::SetForegroundWindow($handle)
    $category=if($Page -in @('Audio','View')){$Page}else{'Extensions'}
    $items=$prefs.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
    $button=$items | Where-Object {$_.Current.Name -eq $category -and $_.Current.ControlType -eq [System.Windows.Automation.ControlType]::Button} | Select-Object -First 1
    if(-not $button){throw 'Preferences category not found'}
    $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    if($Page -in @('RB PLUS','STEMS','Video','Lighting')) {
        for($attempt=0;$attempt -lt 30 -and -not [RbPrefsProbe]::IsWindowVisible($tabs);$attempt++){Start-Sleep -Milliseconds 100}
        if(-not [RbPrefsProbe]::IsWindowVisible($tabs)){throw 'Extensions tab strip not visible'}
        $tabRoot=[System.Windows.Automation.AutomationElement]::FromHandle($tabs)
        $nameCondition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,$Page)
        $tab=$tabRoot.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$nameCondition)
        if(-not $tab){throw 'Requested Extensions tab not found'}
        $tab.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
    }
    Start-Sleep -Milliseconds 350
}
$panel=[RbPrefsProbe]::GetPropW($handle,'RBQ.TempoPanel')
if($panel -eq [IntPtr]::Zero) { throw 'Embedded Tempo Step panel not found' }
$combo=[RbPrefsProbe]::GetDlgItem($panel,1001)
$result=[UIntPtr]::Zero
if($Action -in @('Status','Page')) {
    if([RbPrefsProbe]::SendMessageTimeoutW($combo,0x147,[UIntPtr]::Zero,[IntPtr]::Zero,2,3000,[ref]$result) -eq [IntPtr]::Zero) { throw 'Reading selection timed out' }
    $selected=[int]$result.ToUInt64()
    if($selected -lt 0 -or $selected -gt 2) { throw 'Invalid embedded selection' }
    $tabIndex=-1
    if($tabs -ne [IntPtr]::Zero){
        if([RbPrefsProbe]::SendMessageTimeoutW($tabs,0x130b,[UIntPtr]::Zero,[IntPtr]::Zero,2,3000,[ref]$result) -eq [IntPtr]::Zero){throw 'Reading tab timed out'}
        $tabIndex=[int]$result.ToUInt64()
    }
    [pscustomobject]@{pid=$rb.Id; preferences=$handle.ToInt64(); panel=$panel.ToInt64(); mode=$selected; step=@('Default','0.1','1')[$selected]; panel_visible=[RbPrefsProbe]::IsWindowVisible($panel); tabs_visible=[RbPrefsProbe]::IsWindowVisible($tabs); tab_index=$tabIndex} | ConvertTo-Json
    exit
}
$selected=@{Default=0;'0.1'=1;'1'=2}[$Action]
if([RbPrefsProbe]::SendMessageTimeoutW($combo,0x14e,[UIntPtr][uint32]$selected,[IntPtr]::Zero,2,3000,[ref]$result) -eq [IntPtr]::Zero) { throw 'Selection timed out' }
if([RbPrefsProbe]::SendMessageTimeoutW($panel,0x111,[UIntPtr][uint32]66537,$combo,2,3000,[ref]$result) -eq [IntPtr]::Zero) { throw 'Setting update timed out' }
