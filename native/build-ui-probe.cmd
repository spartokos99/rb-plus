@echo off
setlocal
call "%~dp0setup-msvc.cmd"
if errorlevel 1 exit /b 1
cd /d "%~dp0.."
if not exist build mkdir build
cl /nologo /std:c++17 /O2 /W4 /WX /EHsc /MT /LD native\ui_input_probe.cpp /Fobuild\ui_input_probe.obj /Febuild\ui_input_probe.dll /link user32.lib
exit /b %errorlevel%
