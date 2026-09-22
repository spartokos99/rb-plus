param([string]$PythonPath = 'python')
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
[System.Windows.Forms.Application]::EnableVisualStyles()
# Resolve Store execution aliases before the message loop. The generic alias
# may not be launchable from a later WinForms event callback on this machine.
try {
    $script:pythonExe=(& $PythonPath -c 'import sys; print(sys.executable)' | Select-Object -Last 1)
    if ($LASTEXITCODE -ne 0 -or -not $script:pythonExe) { throw 'Python x64 wurde nicht gefunden.' }
} catch {
    [void][System.Windows.Forms.MessageBox]::Show($_.ToString(),'Python konnte nicht gestartet werden')
    exit 1
}
$script:connected = $false
$script:attachedPid = 0
$script:lastSelection = 0
$script:updatingSelection = $false

function Invoke-TempoControl([string]$Action) {
    $targets=@(Get-Process -Name rekordbox -ErrorAction SilentlyContinue)
    if ($targets.Count -ne 1) { throw 'Bitte genau eine Rekordbox-Instanz starten.' }
    if ($script:connected -and $targets[0].Id -ne $script:attachedPid) {
        throw 'Rekordbox wurde neu gestartet. Dieses Control-Fenster schliessen und neu oeffnen.'
    }
    if ($Action -in @('install','integer','tenth')) {
        $processCondition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$targets[0].Id)
        $windows=[System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,$processCondition)
        $condition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,'PERFORMANCE')
        if (-not ($windows | Where-Object { $_.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$condition) })) {
            throw 'PERFORMANCE-Modus wurde nicht erkannt. Bitte Einstellungen und offene BPM-Eingaben schliessen oder direkt das eingebettete Einstellungsfeld verwenden.'
        }
    }
    $json=& $script:pythonExe (Join-Path $PSScriptRoot 'tools\tempo_control.py') --pid $targets[0].Id $Action 2>&1
    if ($LASTEXITCODE -ne 0) { throw ($json -join "`n") }
    return ($json -join "`n" | ConvertFrom-Json)
}
function Show-Failure($Failure) {
    [void][System.Windows.Forms.MessageBox]::Show($Failure.ToString(),'BPM / Tempo Step',[System.Windows.Forms.MessageBoxButtons]::OK,[System.Windows.Forms.MessageBoxIcon]::Error)
}
$form=New-Object System.Windows.Forms.Form
$form.Text='BPM / Tempo Step - Rekordbox 7.2.18'
$form.ClientSize=New-Object System.Drawing.Size(490,240)
$form.StartPosition='CenterScreen'
$form.FormBorderStyle='FixedDialog'
$form.MaximizeBox=$false

$intro=New-Object System.Windows.Forms.Label
$intro.Text='Live-Tempo im Performance-Deck (experimenteller Prototyp)'
$intro.Location=New-Object System.Drawing.Point(18,18)
$intro.Size=New-Object System.Drawing.Size(455,24)
$form.Controls.Add($intro)

$connect=New-Object System.Windows.Forms.Button
$connect.Text='Verbinden'
$connect.Location=New-Object System.Drawing.Point(18,55)
$connect.Size=New-Object System.Drawing.Size(130,30)
$form.Controls.Add($connect)

$choices=New-Object System.Windows.Forms.ComboBox
$choices.DropDownStyle='DropDownList'
$choices.Items.AddRange(@('Default / unveraendert','0.1 BPM','1 BPM (Ganzzahlen)'))
$choices.SelectedIndex=0
$choices.Enabled=$false
$choices.Location=New-Object System.Drawing.Point(165,58)
$choices.Size=New-Object System.Drawing.Size(300,30)
$form.Controls.Add($choices)

$status=New-Object System.Windows.Forms.Label
$status.Text='Noch nicht verbunden.'
$status.Location=New-Object System.Drawing.Point(18,103)
$status.Size=New-Object System.Drawing.Size(450,36)
$form.Controls.Add($status)

$note=New-Object System.Windows.Forms.Label
$note.Text="Das Fenster kann geschlossen werden: Der gewaehlte Modus bleibt`nbis zum Beenden von Rekordbox aktiv. Zum Abschalten Default waehlen.`nVor einem Wechsel aus PERFORMANCE auf Default stellen.`nEine neue Auswahl gilt ab der naechsten Tempo-Eingabe."
$note.Location=New-Object System.Drawing.Point(18,150)
$note.Size=New-Object System.Drawing.Size(455,80)
$form.Controls.Add($note)

$connect.Add_Click({
    try {
        $state=Invoke-TempoControl 'status'
        if (-not $state.installed) { $state=Invoke-TempoControl 'install' }
        $script:updatingSelection=$true
        $choices.SelectedIndex=[int]$state.mode
        $script:lastSelection=$choices.SelectedIndex
        $script:updatingSelection=$false
        $script:attachedPid=$state.pid
        $script:connected=$true
        $choices.Enabled=$true
        $connect.Enabled=$false
        $status.Text='Verbunden. Aktiv: '+$choices.SelectedItem+'.'
        if ($state.permanent) {
            $note.Text="Dauerhafter Patch aktiv. Die Auswahl wird gespeichert.`nSie steht auch direkt in den Rekordbox-Einstellungen bereit.`nDieses Control-Fenster wird nicht benoetigt.`nVor einem Wechsel aus PERFORMANCE auf Default stellen."
        }
    } catch { Show-Failure $_ }
})
$choices.Add_SelectedIndexChanged({
    if (-not $script:connected -or $script:updatingSelection) { return }
    try {
        $action=@('default','tenth','integer')[$choices.SelectedIndex]
        $state=Invoke-TempoControl $action
        $script:lastSelection=$choices.SelectedIndex
        $status.Text='Auswahl: '+$choices.SelectedItem+'.'
        if ($state.permanent) { $status.Text+=' Gespeichert und angewendet.' }
        else { $status.Text+=' Jetzt den Tempo-Fader bewegen.' }
    } catch {
        $failure=$_
        $script:updatingSelection=$true
        $choices.SelectedIndex=$script:lastSelection
        $script:updatingSelection=$false
        Show-Failure $failure
    }
})
# Closing releases only this UI. The pinned native DLL owns both the hook and
# selected mode; no controller or background process is needed for playback.
[void]$form.ShowDialog()
$form.Dispose()
