param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('Install','Default','0.1','1','Status','Stop')]
    [string]$Step
)
$ErrorActionPreference = 'Stop'
$targets = @(Get-Process -Name rekordbox -ErrorAction SilentlyContinue)
if ($targets.Count -ne 1) { throw 'Please start exactly one instance of Rekordbox.' }
if ($Step -in @('Install','0.1','1')) {
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
    $processCondition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$targets[0].Id)
    $windows = [System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,$processCondition)
    $condition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,'PERFORMANCE')
    if (-not ($windows | Where-Object { $_.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$condition) })) {
        throw 'PERFORMANCE mode was not detected. Close Preferences and any open BPM input fields, or use the embedded settings panel directly.'
    }
}
$action = @{Install='install';Default='default';'0.1'='tenth';'1'='integer';Status='status';Stop='stop'}[$Step]
$result = & python (Join-Path $PSScriptRoot 'tools\tempo_control.py') --pid $targets[0].Id $action
if ($LASTEXITCODE -ne 0) { throw "Tempo control failed (exit $LASTEXITCODE)." }
$result
if ($Step -in @('Default','0.1','1','Stop')) {
    $state = $result -join "`n" | ConvertFrom-Json
    if ($state.permanent) {
        Write-Host 'Selection saved. Previously detected decks were asked to recalculate their tempo.'
    } else {
        Write-Host 'The selection takes effect on the next tempo input. The current tempo is retained until then.'
    }
}
