# -*- mode: python -*-
a = Analysis(['.\\stackinabox\\main.py'],
             pathex=['.'],
             hiddenimports=["sip", "PyQt5.Qt", "PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets", "PyQt5.QtWebKitWidgets", "PyQt5.QtPrintSupport",  "pybootd", "socket"],
             hookspath=None,
             runtime_hooks=None)
pyz = PYZ(a.pure)
plugins = [("qt5_plugins/platforms/qwindows.dll",
			r"c:\Qt\Qt5.4.0\5.4\msvc2013\plugins\platforms\qwindows.dll", "BINARY")]
data = [
  ("qt.conf", "qt.conf", "DATA")
]
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='stackinabox.exe',
          debug=False,
          strip=None,
          upx=True,
          console=True,
		  uac_admin=True,
		  icon="resources\\app.ico")
coll = COLLECT(exe,
               a.binaries + plugins,
               a.zipfiles,
               a.datas + data,
               strip=None,
               upx=True,
               name='stackinabox')

# uac_admin is not supported upstream yet, use the following pull request:
#git clone https://github.com/pyinstaller/pyinstaller.git
#git fetch origin pull/149/head
#git checkout -b pull1 FETCH_HEAD
#cd pyinstaller
#python setup.py install
