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
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWebKit
from PyQt5 import QtWidgets
from PyQt5 import QtWebKitWidgets

import stackinabox
from stackinabox import utils
from stackinabox import webbrowser
from stackinabox import worker as deployment_worker

LOG = logging


class Controller(QtCore.QObject):
    on_stdout_data_event = QtCore.pyqtSignal(str)
    on_stderr_data_event = QtCore.pyqtSignal(str)
    on_error_event = QtCore.pyqtSignal(str)
    on_install_done_event = QtCore.pyqtSignal(bool)
    on_get_ext_vswitches_completed_event = QtCore.pyqtSignal(str)
    on_get_available_host_nics_completed_event = QtCore.pyqtSignal(str)
    on_add_ext_vswitch_completed_event = QtCore.pyqtSignal(bool)
    on_install_started_event = QtCore.pyqtSignal()
    on_review_config_event = QtCore.pyqtSignal()
    on_show_controller_config_event = QtCore.pyqtSignal()
    on_show_host_config_event = QtCore.pyqtSignal()
    on_show_welcome_event = QtCore.pyqtSignal()
    on_show_eula_event = QtCore.pyqtSignal()
    on_show_deployment_details_event = QtCore.pyqtSignal(str, str)
    on_show_progress_status_event = QtCore.pyqtSignal(bool, int, int, str)
    on_enable_retry_deployment_event = QtCore.pyqtSignal(bool)

    def __init__(self, worker):
        super(Controller, self).__init__()
        self._worker = worker
        self._main_window = None
        self._splash_window = None
        self._progress_counter = 0

        self._worker.stdout_data_ready.connect(self._send_stdout_data)
        self._worker.stderr_data_ready.connect(self._send_stderr_data)
        self._worker.error.connect(self._error)
        self._worker.install_done.connect(self._install_done)
        self._worker.get_ext_vswitches_completed.connect(
            self._get_ext_vswitches_completed)
        self._worker.get_available_host_nics_completed.connect(
            self._get_available_host_nics_completed)
        self._worker.add_ext_vswitch_completed.connect(
            self._add_ext_vswitch_completed)
        self._worker.get_deployment_details_completed.connect(
            self._get_deployment_details_completed)
        self._worker.platform_requirements_checked.connect(
            self._platform_requirements_checked)
        self._worker.progress_status_update.connect(
            self._progress_status_update)
        self._worker.host_user_validated.connect(
            self._host_user_validated)

    def set_main_window(self, main_window):
        self._main_window = main_window

    def set_splash_window(self, splash_window):
        self._splash_window = splash_window

    def _progress_status_update(self, enable, step, total_steps, msg):
        # TODO: synchronize this method
        send_update_event = False

        if enable and not step:
            self._progress_counter += 1
            send_update_event = True
        else:
            if self._progress_counter:
                self._progress_counter -= 1
            if not self._progress_counter:
                send_update_event = True

        if send_update_event:
            self.on_show_progress_status_event.emit(
                enable, step, total_steps, msg)

    def _send_stdout_data(self, data):
        self.on_stdout_data_event.emit(data)

    def _send_stderr_data(self, data):
        self.on_stderr_data_event.emit(data)

    def _error(self, ex):
        self.on_error_event.emit(ex.message)

    def _install_done(self, success):
        self.on_install_done_event.emit(success)
        if success:
            self.show_deployment_details()
        else:
            self._enable_retry_deployment(True)

    def _get_ext_vswitches_completed(self, ext_vswitches):
        self.on_get_ext_vswitches_completed_event.emit(
            json.dumps(ext_vswitches))

    def _get_available_host_nics_completed(self, host_nics):
        self.on_get_available_host_nics_completed_event.emit(
            json.dumps(host_nics))

    def _add_ext_vswitch_completed(self, success):
        self.on_add_ext_vswitch_completed_event.emit(success)

    def _get_deployment_details_completed(self, controller_ip, horizon_url):
        self.on_show_deployment_details_event.emit(controller_ip, horizon_url)
        self.hide_splash()

    def _platform_requirements_checked(self):
        self.show_controller_config()
        self.hide_splash()

    def _check_platform_requirements(self):
        QtCore.QMetaObject.invokeMethod(self._worker,
                                        'check_platform_requirements',
                                        QtCore.Qt.QueuedConnection)

    def _enable_retry_deployment(self, enable):
        self.on_enable_retry_deployment_event.emit(enable)

    def _host_user_validated(self):
        self.on_review_config_event.emit()

    def show_splash(self):
        self._splash_window.show()

    def hide_splash(self):
        LOG.debug("hide_splash called")
        self._splash_window.hide()
        self._main_window.show()

    def can_close(self):
        return self._worker.can_close()

    def start(self):
        try:
            if self._worker.show_welcome():
                self.show_welcome()
            elif not self._worker.is_eula_accepted():
                self.show_eula()
            elif self._worker.is_openstack_deployed():
                self.show_deployment_details()
            else:
                self._check_platform_requirements()
        except Exception as ex:
            LOG.exception(ex)
            raise

    @QtCore.pyqtSlot()
    def show_deployment_details(self):
        LOG.debug("show_deployment_details called")
        QtCore.QMetaObject.invokeMethod(self._worker, 'get_deployment_details',
                                        QtCore.Qt.QueuedConnection)

    @QtCore.pyqtSlot()
    def show_controller_config(self):
        self.on_show_controller_config_event.emit()

    @QtCore.pyqtSlot()
    def show_host_config(self):
        LOG.debug("show_host_config")
        self.get_ext_vswitches()
        self.on_show_host_config_event.emit()

    @QtCore.pyqtSlot()
    def show_welcome(self):
        self.on_show_welcome_event.emit()
        self.hide_splash()

    @QtCore.pyqtSlot()
    def show_eula(self):
        self._worker.set_show_welcome(False)
        self.on_show_eula_event.emit()
        self.hide_splash()

    @QtCore.pyqtSlot()
    def accept_eula(self):
        self._worker.set_eula_accepted()
        self._check_platform_requirements()

    @QtCore.pyqtSlot()
    def refuse_eula(self):
        self._main_window.close()

    @QtCore.pyqtSlot()
    def cancel_deployment(self):
        LOG.debug("cancel_deployment called")
        # Cannot use the worker's queue, consider a separate worker
        # to avoid blocking the UI
        self._worker.cancel_openstack_deployment()

    @QtCore.pyqtSlot()
    def reconfig_deployment(self):
        LOG.debug("reconfig_deployment called")
        self.on_review_config_event.emit()

    @QtCore.pyqtSlot(str)
    def review_config(self, json_args):
        LOG.debug("review_config called")

        args = json.loads(str(json_args))
        QtCore.QMetaObject.invokeMethod(
            self._worker, 'validate_host_user',
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(str, args.get("hyperv_host_username")),
            QtCore.Q_ARG(str, args.get("hyperv_host_password")))

    @QtCore.pyqtSlot(result=str)
    def get_config(self):
        return json.dumps(self._worker.get_config())

    @QtCore.pyqtSlot(str, int, int)
    def set_term_info(self, term_type, cols, rows):
        self._worker.set_term_info(str(term_type), cols, rows)

    @QtCore.pyqtSlot(str)
    def install(self, json_args):
        LOG.debug("Install called: %s" % json_args)

        self.on_install_started_event.emit()
        self._enable_retry_deployment(False)

        try:
            QtCore.QMetaObject.invokeMethod(
                self._worker, 'deploy_openstack',
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(str, json_args))
        except Exception as ex:
            LOG.exception(ex)
            raise

    @QtCore.pyqtSlot()
    def redeploy_openstack(self):
        self.show_controller_config()

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

    @QtCore.pyqtSlot()
    def open_horizon_url(self):
        LOG.debug("open_horizon_url called")
        QtCore.QMetaObject.invokeMethod(self._worker,
                                        'open_horizon_url',
                                        QtCore.Qt.QueuedConnection)

    @QtCore.pyqtSlot()
    def open_controller_ssh(self):
        LOG.debug("open_controller_ssh called")
        QtCore.QMetaObject.invokeMethod(self._worker,
                                        'open_controller_ssh',
                                        QtCore.Qt.QueuedConnection)


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, controller):
        super(MainWindow, self).__init__()

        self._controller = controller
        self._controller.set_main_window(self)

        app_icon_path = os.path.join(utils.get_resources_dir(), "app.ico")
        self.setWindowIcon(QtGui.QIcon(app_icon_path))
        self.setWindowTitle('V-Magine - OpenStack Installer')

        self._web = QtWebKitWidgets.QWebView()

        self._web.setPage(QWebPageWithoutJsWarning(self._web))

        width = 1020
        heigth = 768

        self.resize(width, heigth)
        self.setCentralWidget(self._web)

        self._web.loadFinished.connect(self.onLoad)

        page = self._web.page()
        page.settings().setAttribute(
            QtWebKit.QWebSettings.DeveloperExtrasEnabled, True)
        page.settings().setAttribute(
            QtWebKit.QWebSettings.LocalContentCanAccessRemoteUrls, True)

        frame = page.mainFrame()
        page.setViewportSize(frame.contentsSize())

        if os.name == 'nt':
            appid = 'StackInABox.1.0.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                appid)

        web_dir = utils.get_web_dir()
        self._web.setUrl(QtCore.QUrl.fromLocalFile(
            os.path.join(web_dir, "index.html")))

        self.setFixedSize(width, heigth)

        self._web.show()

    def closeEvent(self, event):
        if self._controller.can_close():
            event.accept()
        else:
            reply = QtWidgets.QMessageBox.question(
                self, 'Message',
                "Are you sure to quit and interrupt the OpenStack "
                "installation?",
                QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
            if reply == QtWidgets.QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()

    def onLoad(self):
        LOG.debug("onLoad")

        page = self._web.page()
        frame = page.mainFrame()

        frame.addToJavaScriptWindowObject("controller", self._controller)
        frame.evaluateJavaScript("ApplicationIsReady()")

        self._controller.start()


class QWebPageWithoutJsWarning(QtWebKitWidgets.QWebPage):
    def __init__(self, parent=None):
        super(QWebPageWithoutJsWarning, self).__init__(parent)

    @QtCore.pyqtSlot()
    def shouldInterruptJavaScript(self):
        LOG.debug("shouldInterruptJavaScript")
        return False


def _config_logging(log_dir):
    log_format = ("%(asctime)-15s %(levelname)s %(module)s %(funcName)s "
                  "%(lineno)d %(thread)d %(threadName)s %(message)s")
    log_file = os.path.join(log_dir, 'v-magine.log')
    logging.basicConfig(filename=log_file, level=logging.DEBUG,
                        format=log_format)
    logging.getLogger("paramiko").setLevel(logging.WARNING)


def _init_worker():
    thread = QtCore.QThread()
    worker = deployment_worker.Worker(thread)
    thread.start()
    return worker


def _create_splash_window(main_window):
    res_dir = utils.get_resources_dir()
    splash_img_path = os.path.join(res_dir, "v-magine-splash.png")

    image = QtGui.QPixmap(splash_img_path)
    splash = QtWidgets.QSplashScreen(main_window, image)
    splash.setAttribute(QtCore.Qt.WA_DeleteOnClose)
    splash.setMask(image.mask())
    return splash


def main(url=None):
    app = QtWidgets.QApplication(sys.argv)

    if url:
        main_window = webbrowser.MainWindow(url)
        main_window.show()
    else:
        base_dir = utils.get_base_dir()
        os.chdir(base_dir)
        _config_logging(base_dir)

        worker = _init_worker()
        controller = Controller(worker)

        main_window = MainWindow(controller)
        splash = _create_splash_window(main_window)
        controller.set_splash_window(splash)
        controller.show_splash()

    sys.exit(app.exec_())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'pybootd':
        pybootd_daemons.main()
    else:
        if len(sys.argv) == 3 and sys.argv[1] == 'openurl':
            main(sys.argv[2])
        else:
            main()
