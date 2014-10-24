# Copyright 2014 Cloudbase Solutions Srl
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import ctypes
import os
import sys

from PySide import QtCore
from PySide import QtGui
from PySide import QtWebKit

import stackinabox

from stackinabox.rdo import install


class Controller(QtCore.QObject):
    on_status_changed_event = QtCore.Signal(str)
    on_stdout_data_event = QtCore.Signal(str)
    on_stderr_data_event = QtCore.Signal(str)
    on_error_event = QtCore.Signal(str)

    def __init__(self, worker):
        super(Controller, self).__init__()
        self._worker = worker
        self._worker.stdout_data_ready.connect(self._send_stdout_data)
        self._worker.stderr_data_ready.connect(self._send_stderr_data)
        self._worker.status_changed.connect(self._status_changed)
        self._worker.error.connect(self._error)

    def _send_stdout_data(self, data):
        self.on_stdout_data_event.emit(data)

    def _send_stderr_data(self, data):
        self.on_stderr_data_event.emit(data)

    def _status_changed(self, msg):
        self.on_status_changed_event.emit(msg)

    def _error(self, ex):
        self.on_error_event.emit(ex.message)

    @QtCore.Slot()
    def install(self):
        print "install"

        QtCore.QMetaObject.invokeMethod(self._worker, 'install_rdo',
                                        QtCore.Qt.QueuedConnection)


class Worker(QtCore.QObject):
    finished = QtCore.Signal()
    stdout_data_ready = QtCore.Signal(str)
    stderr_data_ready = QtCore.Signal(str)
    status_changed = QtCore.Signal(str)
    error = QtCore.Signal(Exception)

    @QtCore.Slot()
    def started(self):
        print "Started"

    @QtCore.Slot()
    def install_rdo(self):
        print "install_rdo"

        def stdout_callback(data):
            self.stdout_data_ready.emit(data)

        def stderr_callback(data):
            self.stderr_data_ready.emit(data)

        rdo_installer = install.RDOInstaller(stdout_callback, stderr_callback)
        try:
            self.status_changed.emit(
                'Enstablishing SSH connection with RDO VM...')
            rdo_installer.connect()

            self.status_changed.emit('Updating RDO VM...')
            rdo_installer.update_os()

            self.status_changed.emit('Installing RDO...')
            rdo_installer.install_rdo()

            self.status_changed.emit('Done!')
        except Exception as ex:
            self.error.emit(ex);
        finally:
            rdo_installer.disconnect()


class MainWindow(QtGui.QMainWindow):

    def __init__(self):
        super(MainWindow, self).__init__()

        self.setWindowIcon(QtGui.QIcon('app.ico'))
        self.setWindowTitle('Stack in a Box - OpenStack Installer')

        self._web = QtWebKit.QWebView()

        self.resize(1024, 768)
        self.setCentralWidget(self._web)

        self._web.loadFinished.connect(self.onLoad)

        self._init_worker()
        self._controller = Controller(self._worker)

        self._web.load("www/index.html")

        self._web.show()

    def _init_worker(self):
        self._thread = QtCore.QThread()
        self._worker = Worker()
        self._worker.moveToThread(self._thread)

        self._worker.finished.connect(self._thread.quit)
        self._thread.started.connect(self._worker.started)
        self._thread.start()

    def onLoad(self):
        page = self._web.page()
        page.settings().setAttribute(
            QtWebKit.QWebSettings.DeveloperExtrasEnabled, True)

        frame = page.mainFrame()
        page.setViewportSize(frame.contentsSize())

        if os.name == 'nt':
            appid = 'StackInABox.1.0.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                appid)

        frame.addToJavaScriptWindowObject("controller", self._controller)
        frame.evaluateJavaScript("ApplicationIsReady()")


def main():
    app = QtGui.QApplication(sys.argv)

    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
