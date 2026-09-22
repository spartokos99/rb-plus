@echo off
rem Keep the environment in the calling build script's setlocal scope.
if /i "%VSCMD_ARG_TGT_ARCH%"=="x64" (
    where cl.exe >nul 2>nul
    if not errorlevel 1 exit /b 0
)
if defined RBQ_VCVARS (
    call "%RBQ_VCVARS%" >nul
    if errorlevel 1 exit /b 1
    exit /b 0
)
set "RBQ_VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%RBQ_VSWHERE%" (
    echo MSVC x64 not found. Use an x64 Developer Command Prompt or set RBQ_VCVARS. >&2
    exit /b 1
)
set "RBQ_VSINSTALL="
for /f "usebackq tokens=*" %%I in (`"%RBQ_VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "RBQ_VSINSTALL=%%I"
if not defined RBQ_VSINSTALL (
    echo Install Visual Studio C++ build tools with the Windows SDK. >&2
    exit /b 1
)
call "%RBQ_VSINSTALL%\VC\Auxiliary\Build\vcvars64.bat" >nul
exit /b %errorlevel%
