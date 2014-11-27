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
import json
import logging
import os
import sys

# For PyInstaller
import pkg_resources
import xmlrpclib

from pybootd import daemons as pybootd_daemons
from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4 import QtWebKit

import stackinabox
from stackinabox import utils
from stackinabox import worker as deployment_worker

LOG = logging


class Controller(QtCore.QObject):
    on_status_changed_event = QtCore.pyqtSignal(str, int, int)
    on_stdout_data_event = QtCore.pyqtSignal(str)
    on_stderr_data_event = QtCore.pyqtSignal(str)
    on_error_event = QtCore.pyqtSignal(str)
    on_install_done_event = QtCore.pyqtSignal(bool)
    on_get_ext_vswitches_completed_event = QtCore.pyqtSignal(str)
    on_get_available_host_nics_completed_event = QtCore.pyqtSignal(str)
    on_add_ext_vswitch_completed_event = QtCore.pyqtSignal(bool)

    def __init__(self, worker):
        super(Controller, self).__init__()
        self._worker = worker
        self._worker.stdout_data_ready.connect(self._send_stdout_data)
        self._worker.stderr_data_ready.connect(self._send_stderr_data)
        self._worker.status_changed.connect(self._status_changed)
        self._worker.error.connect(self._error)
        self._worker.install_done.connect(self._install_done)
        self._worker.get_ext_vswitches_completed.connect(
            self._get_ext_vswitches_completed)
        self._worker.get_available_host_nics_completed.connect(
            self._get_available_host_nics_completed)
        self._worker.add_ext_vswitch_completed.connect(
            self._add_ext_vswitch_completed)

    def _send_stdout_data(self, data):
        self.on_stdout_data_event.emit(data)

    def _send_stderr_data(self, data):
        self.on_stderr_data_event.emit(data)

    def _status_changed(self, msg, step, max_steps):
        self.on_status_changed_event.emit(msg, step, max_steps)

    def _error(self, ex):
        self.on_error_event.emit(ex.message)

    def _install_done(self, success):
        self.on_install_done_event.emit(success)

    def _get_ext_vswitches_completed(self, ext_vswitches):
        self.on_get_ext_vswitches_completed_event.emit(
            json.dumps(ext_vswitches))

    def _get_available_host_nics_completed(self, host_nics):
        self.on_get_available_host_nics_completed_event.emit(
            json.dumps(host_nics))

    def _add_ext_vswitch_completed(self, success):
        self.on_add_ext_vswitch_completed_event.emit(success)

    @QtCore.pyqtSlot(result=str)
    def get_config(self):
        return json.dumps(self._worker.get_config())

    @QtCore.pyqtSlot(str, int, int)
    def set_term_info(self, term_type, cols, rows):
        self._worker.set_term_info(str(term_type), cols, rows)

    @QtCore.pyqtSlot(str, int, str, str, str, str, str, str)
    def install(self, ext_vswitch_name, openstack_vm_mem_mb,
                openstack_base_dir, admin_password,
                hyperv_host_username, hyperv_host_password,
                fip_range_start, fip_range_end):
        LOG.debug("Install called")
        QtCore.QMetaObject.invokeMethod(
            self._worker, 'deploy_openstack',
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(str, ext_vswitch_name),
            QtCore.Q_ARG(int, openstack_vm_mem_mb),
            QtCore.Q_ARG(str, openstack_base_dir),
            QtCore.Q_ARG(str, admin_password),
            QtCore.Q_ARG(str, hyperv_host_username),
            QtCore.Q_ARG(str, hyperv_host_password),
            QtCore.Q_ARG(str, fip_range_start),
            QtCore.Q_ARG(str, fip_range_end))

    @QtCore.pyqtSlot()
    def get_ext_vswitches(self):
        LOG.debug("get_ext_vswitches called")
        QtCore.QMetaObject.invokeMethod(self._worker, 'get_ext_vswitches',
                                        QtCore.Qt.QueuedConnection)

    @QtCore.pyqtSlot()
    def get_available_host_nics(self):
        LOG.debug("get_available_host_nics called")
        QtCore.QMetaObject.invokeMethod(self._worker,
                                        'get_available_host_nics',
                                        QtCore.Qt.QueuedConnection)

    @QtCore.pyqtSlot(str, str)
    def add_ext_vswitch(self, vswitch_name, nic_name):
        LOG.debug("add_ext_vswitch called")
        QtCore.QMetaObject.invokeMethod(self._worker, 'add_ext_vswitch',
                                        QtCore.Qt.QueuedConnection,
                                        QtCore.Q_ARG(str, vswitch_name),
                                        QtCore.Q_ARG(str, nic_name))


class MainWindow(QtGui.QMainWindow):

    def __init__(self):
        super(MainWindow, self).__init__()

        app_icon_path = os.path.join(utils.get_resources_dir(), "app.ico")
        self.setWindowIcon(QtGui.QIcon(app_icon_path))
        self.setWindowTitle('Stack in a Box - OpenStack Installer')

        self._web = QtWebKit.QWebView()

        self._web.setPage(QWebPageWithoutJsWarning(self._web))

        self.resize(1024, 768)
        self.setCentralWidget(self._web)

        self._web.loadFinished.connect(self.onLoad)

        self._init_worker()
        self._controller = Controller(self._worker)

        self._web.load(QtCore.QUrl("www/index.html"))

        self._web.show()

    def closeEvent(self, event):
        if self._worker.can_close():
            event.accept()
        else:
            reply = QtGui.QMessageBox.question(
                self, 'Message',
                "Are you sure to quit and interrupt the OpenStack "
                "installation?",
                QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
            if reply == QtGui.QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()

    def _init_worker(self):
        self._thread = QtCore.QThread()
        self._worker = deployment_worker.Worker()
        self._worker.moveToThread(self._thread)

        self._worker.finished.connect(self._thread.quit)
        self._thread.started.connect(self._worker.started)
        self._thread.start()

    def onLoad(self):
        page = self._web.page()
        page.settings().setAttribute(
            QtWebKit.QWebSettings.DeveloperExtrasEnabled, False)

        frame = page.mainFrame()
        page.setViewportSize(frame.contentsSize())

        if os.name == 'nt':
            appid = 'StackInABox.1.0.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                appid)

        frame.addToJavaScriptWindowObject("controller", self._controller)
        frame.evaluateJavaScript("ApplicationIsReady()")


class QWebPageWithoutJsWarning(QtWebKit.QWebPage):
    def __init__(self, parent=None):
        super(QWebPageWithoutJsWarning, self).__init__(parent)

    @QtCore.pyqtSlot()
    def shouldInterruptJavaScript(self):
        LOG.debug("shouldInterruptJavaScript")
        return False


def _config_logging(log_dir):
    log_format = ("%(asctime)-15s %(levelname)s %(module)s %(funcName)s "
                  "%(lineno)d %(thread)d %(threadName)s %(message)s")
    log_file = os.path.join(log_dir, 'stackinabox.log')
    logging.basicConfig(filename=log_file, level=logging.DEBUG,
                        format=log_format)
    logging.getLogger("paramiko").setLevel(logging.WARNING)


def main():
    base_dir = os.path.dirname(sys.executable)
    os.chdir(base_dir)

    _config_logging(base_dir)

    app = QtGui.QApplication(sys.argv)

    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'pybootd':
        pybootd_daemons.main()
    else:
        main()
