@echo off

pyinstaller --noconfirm --log-level=WARN --onedir stackinabox.spec
if %errorlevel% neq 0 exit /b %errorlevel%

xcopy /S /E /Y www dist\stackinabox\www\
if %errorlevel% neq 0 exit /b %errorlevel%

xcopy /S /E /Y pxe dist\stackinabox\pxe\
if %errorlevel% neq 0 exit /b %errorlevel%

xcopy /S /E /Y resources dist\stackinabox\resources\
if %errorlevel% neq 0 exit /b %errorlevel%

xcopy /S /E /Y bin dist\stackinabox\bin\
if %errorlevel% neq 0 exit /b %errorlevel%
