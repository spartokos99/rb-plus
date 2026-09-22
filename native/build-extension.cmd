@echo off
setlocal
call "%~dp0setup-msvc.cmd"
if errorlevel 1 exit /b 1
cd /d "%~dp0.."
if not exist build mkdir build
set RBQ_OUTPUT=rb_bpm_startup
if not "%~1"=="" set RBQ_OUTPUT=%~1
cl /nologo /std:c++17 /O2 /W4 /WX /EHsc /MT /LD native\tempo_extension.cpp /Fobuild\tempo_extension.obj /Febuild\%RBQ_OUTPUT%.dll /link /DYNAMICBASE /NXCOMPAT
exit /b %errorlevel%
