@echo off

pyinstaller --noconfirm --log-level=WARN --onedir v-magine.spec
if %errorlevel% neq 0 exit /b %errorlevel%

xcopy /S /E /Y www dist\v-magine\www\
if %errorlevel% neq 0 exit /b %errorlevel%

xcopy /S /E /Y pxe dist\v-magine\pxe\
if %errorlevel% neq 0 exit /b %errorlevel%

xcopy /S /E /Y resources dist\v-magine\resources\
if %errorlevel% neq 0 exit /b %errorlevel%

xcopy /S /E /Y bin dist\v-magine\bin\
if %errorlevel% neq 0 exit /b %errorlevel%

del dist\v-magine\*d.dll
if %errorlevel% neq 0 exit /b %errorlevel%
rmdir /s /q dist\v-magine\qml
if %errorlevel% neq 0 exit /b %errorlevel%
