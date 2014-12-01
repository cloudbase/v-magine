# -*- mode: python -*-
a = Analysis(['.\\stackinabox\\main.py'],
             pathex=['.'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='stackinabox.exe',
          debug=False,
          strip=None,
          upx=True,
          console=False,
		  uac_admin=True,
		  icon="resources\\app.ico")
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=None,
               upx=True,
               name='stackinabox')

# uac_admin is not supported upstream yet, use the following pull request:
#git clone https://github.com/pyinstaller/pyinstaller.git
#git fetch origin pull/149/head
#git checkout -b pull1 FETCH_HEAD
#cd pyinstaller
#python setup.py install
