param(
    [Parameter(Mandatory=$true)][string]$Path
)
# Read-only. Exit 0: known static match; exit 2: unknown/inconsistent/unreadable.
# A static match never substitutes for the runtime matrix in compatibility/README.md.
$ErrorActionPreference='Stop'
& python (Join-Path $PSScriptRoot 'tools\check_compatibility.py') --path $Path
exit $LASTEXITCODE
