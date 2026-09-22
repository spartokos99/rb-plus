@echo off
setlocal
call "%~dp0setup-msvc.cmd"
if errorlevel 1 exit /b 1
cd /d "%~dp0.."
if not exist build\loader-test mkdir build\loader-test
cl /nologo /O2 /W4 /WX /MT native\loader_test.cpp /Fobuild\loader-test\host.obj /Febuild\loader-test\host.exe
if errorlevel 1 exit /b 1
cl /nologo /O2 /W4 /WX /MT /LD /DRBQ_TEST_DLL native\loader_test.cpp /Fobuild\loader-test\dll.obj /Febuild\loader-test\rb_bpm_patch.dll
exit /b %errorlevel%
