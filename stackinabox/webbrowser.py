import ctypes
import os

from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWebKit
from PyQt5 import QtWidgets
from PyQt5 import QtWebKitWidgets

from stackinabox import utils


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, url):
        super(MainWindow, self).__init__()

        app_icon_path = os.path.join(utils.get_resources_dir(), "app.ico")
        self.setWindowIcon(QtGui.QIcon(app_icon_path))
        self.setWindowTitle('v-magine')

        self.resize(1024, 768)

        self._web = QtWebKitWidgets.QWebView()

        self._status_bar_label = QtWidgets.QLabel('Loading...   ')

        self._progressbar = QtWidgets.QProgressBar()
        self._progressbar.setMinimum(0)
        self._progressbar.setMaximum(100)

        self.setCentralWidget(self._web)

        self.statusBar().addPermanentWidget(self._status_bar_label)
        self.statusBar().addPermanentWidget(self._progressbar, 1)

        self._web.loadStarted.connect(self.load_started)
        self._web.loadProgress.connect(self.load_progress)
        self._web.loadFinished.connect(self.load_finished)
        self._web.urlChanged.connect(self.url_changed)

        page = self._web.page()
        page.settings().setAttribute(
            QtWebKit.QWebSettings.DeveloperExtrasEnabled, True)

        frame = page.mainFrame()
        page.setViewportSize(frame.contentsSize())

        if os.name == 'nt':
            appid = 'StackInABox.1.0.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                appid)

        self._web.load(QtCore.QUrl(url))
        self._web.show()

    def url_changed(self, url):
        self.setWindowTitle('v-magine - %s' % url.toString())

    def load_started(self):
        self._progressbar.setValue(0)
        self._progressbar.show()
        self._status_bar_label.show()

    def load_progress(self, progress):
        self._progressbar.setValue(progress)

    def load_finished(self, ok):
        self._progressbar.setValue(0)
        self._progressbar.hide()
        self._status_bar_label.hide()

    def closeEvent(self, event):
        reply = QtWidgets.QMessageBox.question(
            self, 'Message',
            "Are you sure you want to close this window?",
            QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()
