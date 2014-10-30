pyinstaller --noconfirm --log-level=WARN --onedir --noconsole --hidden-import=pybootd --hidden-import=socket --icon=resources\app.ico stackinabox.spec 

xcopy /S /E /Y www dist\stackinabox\www\
xcopy /S /E /Y pxe dist\stackinabox\pxe\
xcopy /S /E /Y resources dist\stackinabox\resources\
copy c:\python27\python.exe dist\stackinabox\
