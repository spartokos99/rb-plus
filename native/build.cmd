@echo off
setlocal
call "%~dp0setup-msvc.cmd"
if errorlevel 1 exit /b 1
cd /d "%~dp0.."
if not exist build mkdir build
cl /nologo /std:c++17 /O2 /W4 /WX /EHsc /MT native\quantizer_test.cpp /Fobuild\quantizer_test.obj /Febuild\quantizer_test.exe
if errorlevel 1 exit /b 1
build\quantizer_test.exe
if errorlevel 1 exit /b 1
cl /nologo /std:c++17 /O2 /W4 /WX /EHsc /MT native\layout_order_test.cpp /Fobuild\layout_order_test.obj /Febuild\layout_order_test.exe
if errorlevel 1 exit /b 1
build\layout_order_test.exe
if errorlevel 1 exit /b 1
cl /nologo /std:c++17 /O2 /W4 /WX /EHsc /MT /LD native\tempo_hook.cpp /Fobuild\tempo_hook.obj /Febuild\rb_bpm.dll /link /DYNAMICBASE /NXCOMPAT
exit /b %errorlevel%
