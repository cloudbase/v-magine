# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
# Licensed under the AGPLv3, see LICENCE file for details.

import ctypes
import json
import logging
import os
import pythoncom
import sys
import threading
import trollius

from pybootd import daemons as pybootd_daemons
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWebKit
from PyQt5 import QtWidgets
from PyQt5 import QtWebKitWidgets

import v_magine  # noqa
from v_magine import constants
from v_magine import utils
from v_magine import webbrowser
from v_magine import worker as deployment_worker

LOG = logging


class Controller(QtCore.QObject):
    on_stdout_data_event = QtCore.pyqtSignal(str)
    on_stderr_data_event = QtCore.pyqtSignal(str)
    on_error_event = QtCore.pyqtSignal(str)
    on_install_done_event = QtCore.pyqtSignal(bool)
    on_get_ext_vswitches_completed_event = QtCore.pyqtSignal(str)
    on_get_available_host_nics_completed_event = QtCore.pyqtSignal(str)
    on_add_ext_vswitch_completed_event = QtCore.pyqtSignal(str)
    on_install_started_event = QtCore.pyqtSignal()
    on_show_review_config_event = QtCore.pyqtSignal()
    on_host_config_validated_event = QtCore.pyqtSignal()
    on_show_controller_config_event = QtCore.pyqtSignal()
    on_controller_config_validated_event = QtCore.pyqtSignal()
    on_openstack_networking_config_validated_event = QtCore.pyqtSignal()
    on_show_openstack_networking_config_event = QtCore.pyqtSignal()
    on_show_host_config_event = QtCore.pyqtSignal()
    on_show_welcome_event = QtCore.pyqtSignal()
    on_show_eula_event = QtCore.pyqtSignal()
    on_show_deployment_details_event = QtCore.pyqtSignal(str, str)
    on_show_progress_status_event = QtCore.pyqtSignal(bool, int, int, str)
    on_enable_retry_deployment_event = QtCore.pyqtSignal(bool)
    on_get_config_completed_event = QtCore.pyqtSignal(str)
    on_deployment_disabled_event = QtCore.pyqtSignal()
    on_product_update_available_event = QtCore.pyqtSignal(str, str, bool, str)
    on_get_compute_nodes_completed_event = QtCore.pyqtSignal(str)
    on_get_repo_urls_completed_event = QtCore.pyqtSignal(str)

    def __init__(self, worker):
        super(Controller, self).__init__()
        self._worker = worker
        self._main_window = None
        self._splash_window = None
        self._progress_counter = 0

        self._worker.set_stdout_callback(self._send_stdout_data)
        self._worker.set_stderr_callback(self._send_stderr_data)
        self._worker.set_error_callback(self._error)
        self._worker.set_progress_status_update_callback(
            self._progress_status_update)

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
        self.on_error_event.emit(str(ex))

    def _disable_deployment(self):
        self.on_deployment_disabled_event.emit()

    def _product_update_available(self, future):
        new_version_info = future.result()
        if new_version_info:
            (current_version,
             new_version,
             update_required,
             update_url) = new_version_info
            self.on_product_update_available_event.emit(
                current_version, new_version, update_required, update_url)

    def _check_for_updates(self):
        _run_async_task(
            self._worker.check_for_updates,
            self._product_update_available)

    def _platform_requirements_checked(self, future):
        LOG.debug("_platform_requirements_checked called")
        success = future.result()
        self.show_controller_config()
        if not success:
            self._disable_deployment()

        # Must be called in MainThread
        QtCore.QMetaObject.invokeMethod(self, 'hide_splash',
                                        QtCore.Qt.QueuedConnection)
        self._check_for_updates()

    def _check_platform_requirements(self):
        LOG.debug("Checking platform requirements")
        _run_async_task(
            self._worker.check_platform_requirements,
            self._platform_requirements_checked)

    def _enable_retry_deployment(self, enable):
        self.on_enable_retry_deployment_event.emit(enable)

    def show_splash(self):
        self._splash_window.show()

    @QtCore.pyqtSlot()
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

    def _get_deployment_details_completed(self, future):
        controller_ip, horizon_url = future.result()
        self.on_show_deployment_details_event.emit(controller_ip, horizon_url)

        # Must be called in MainThread
        QtCore.QMetaObject.invokeMethod(self, 'hide_splash',
                                        QtCore.Qt.QueuedConnection)

        self._check_for_updates()

    @QtCore.pyqtSlot()
    def show_deployment_details(self):
        LOG.debug("show_deployment_details called")
        _run_async_task(
            self._worker.get_deployment_details,
            self._get_deployment_details_completed)
        self.get_compute_nodes()

    @QtCore.pyqtSlot()
    def show_controller_config(self):
        self.on_show_controller_config_event.emit()

    @QtCore.pyqtSlot()
    def show_openstack_networking_config(self):
        self.on_show_openstack_networking_config_event.emit()

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

        # TODO: replace with HTML UI
        reply = QtWidgets.QMessageBox.question(
            self._main_window, constants.PRODUCT_NAME,
            "Cancel the OpenStack deployment?",
            QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            # Cannot use the worker's queue, consider a separate worker
            # to avoid blocking the UI
            self._worker.cancel_openstack_deployment()

    @QtCore.pyqtSlot()
    def reconfig_deployment(self):
        LOG.debug("reconfig_deployment called")
        self.on_show_review_config_event.emit()

    @QtCore.pyqtSlot()
    def show_review_config(self):
        LOG.debug("review_config called")
        self.on_show_review_config_event.emit()

    @QtCore.pyqtSlot(str)
    def validate_host_config(self, json_args):
        LOG.debug("validate_host_config called")

        def _host_config_validated(future):
            user_ok = future.result()
            if user_ok:
                self.on_host_config_validated_event.emit()

        args = json.loads(str(json_args))
        _run_async_task(
            lambda: self._worker.validate_host_config(
                args.get("hyperv_host_username"),
                args.get("hyperv_host_password")),
            _host_config_validated)

    @QtCore.pyqtSlot(str)
    def validate_controller_config(self, json_args):
        LOG.debug("validate_controller_config called")
        args = json.loads(str(json_args))

        def _host_controller_config_validated(future):
            user_ok = future.result()
            if user_ok:
                self.on_controller_config_validated_event.emit()

        _run_async_task(
            lambda: self._worker.validate_controller_config(
                args.get("mgmt_ext_dhcp"),
                args.get("mgmt_ext_ip"),
                args.get("mgmt_ext_gateway"),
                args.get("mgmt_ext_name_servers"),
                args.get("use_proxy"),
                args.get("proxy_url"),
                args.get("proxy_username"),
                args.get("proxy_password")
                ),
            _host_controller_config_validated)

    @QtCore.pyqtSlot(str)
    def validate_openstack_networking_config(self, json_args):
        LOG.debug("validate_openstack_networking_config called")
        args = json.loads(str(json_args))

        def _openstack_networking_config_validated(future):
            user_ok = future.result()
            if user_ok:
                self.on_openstack_networking_config_validated_event.emit()

        _run_async_task(
            lambda: self._worker.validate_openstack_networking_config(
                args.get("fip_range"),
                args.get("fip_range_start"),
                args.get("fip_range_end"),
                args.get("fip_gateway"),
                args.get("fip_name_servers")
                ),
            _openstack_networking_config_validated)

    def _get_repo_urls_completed(self, future):
        repo_url, repo_urls = future.result()
        self.on_get_repo_urls_completed_event.emit(
            json.dumps({"repo_url": repo_url, "repo_urls": repo_urls}))

    def _get_config_completed(self, future):
        config_dict = future.result()
        if config_dict:
            self.on_get_config_completed_event.emit(json.dumps(config_dict))

    @QtCore.pyqtSlot()
    def get_config(self):
        LOG.debug("get_config called")

        _run_async_tasks(
            [(self._worker.get_config, self._get_config_completed),
             (self._worker.get_repo_urls, self._get_repo_urls_completed)])

    def _get_compute_nodes_completed(self, future):
        compute_nodes = future.result()
        self.on_get_compute_nodes_completed_event.emit(
            json.dumps(compute_nodes))

    @QtCore.pyqtSlot()
    def get_compute_nodes(self):
        LOG.debug("get_compute_nodes called")
        _run_async_task(
            self._worker.get_compute_nodes,
            self._get_compute_nodes_completed)

    @QtCore.pyqtSlot(str, int, int)
    def set_term_info(self, term_type, cols, rows):
        self._worker.set_term_info(str(term_type), cols, rows)

    def _install_done(self, future):
        success = future.result()
        self.on_install_done_event.emit(success)
        if success:
            self.show_deployment_details()
        else:
            self._enable_retry_deployment(True)

    @QtCore.pyqtSlot(str)
    def install(self, json_args):
        LOG.debug("Install called: %s" % json_args)

        self.on_install_started_event.emit()
        self._enable_retry_deployment(False)
        _run_async_task(
            lambda: self._worker.deploy_openstack(json.loads(str(json_args))),
            self._install_done)

    @QtCore.pyqtSlot()
    def redeploy_openstack(self):
        self._check_platform_requirements()

    def _openstack_deployment_removed(self, future):
        removed = future.result()
        if removed:
            self.show_controller_config()

    @QtCore.pyqtSlot()
    def remove_openstack(self):
        LOG.debug("remove_openstack called")
        # TODO: replace with HTML UI
        reply = QtWidgets.QMessageBox.question(
            self._main_window, constants.PRODUCT_NAME,
            "Remove the current OpenStack deployment? All OpenStack "
            "controller data will be deleted.",
            QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            _run_async_task(
                self._worker.remove_openstack_deployment,
                self._openstack_deployment_removed)

    def _get_ext_vswitches_completed(self, future):
        ext_vswitches = future.result()
        self.on_get_ext_vswitches_completed_event.emit(
            json.dumps(ext_vswitches))

    @QtCore.pyqtSlot()
    def get_ext_vswitches(self):
        LOG.debug("get_ext_vswitches called")
        _run_async_task(
            self._worker.get_ext_vswitches,
            self._get_ext_vswitches_completed)

    def _get_available_host_nics_completed(self, future):
        host_nics = future.result()
        if host_nics:
            self.on_get_available_host_nics_completed_event.emit(
                json.dumps(host_nics))

    @QtCore.pyqtSlot()
    def get_available_host_nics(self):
        LOG.debug("get_available_host_nics called")
        self.on_get_available_host_nics_completed_event.emit(
            json.dumps([]))

        _run_async_task(
            self._worker.get_available_host_nics,
            self._get_available_host_nics_completed)

    def _add_ext_vswitch_completed(self, future):
        def _get_ext_vswitches_completed_callback(future):
            self._get_ext_vswitches_completed(future)
            self.on_add_ext_vswitch_completed_event.emit(vswitch_name)

        vswitch_name = future.result()
        if vswitch_name:
            # Refresh VSwitch list
            _run_async_task(
                self._worker.get_ext_vswitches,
                _get_ext_vswitches_completed_callback)

    @QtCore.pyqtSlot(str, str)
    def add_ext_vswitch(self, vswitch_name, nic_name):
        LOG.debug("add_ext_vswitch called")
        _run_async_task(
            lambda: self._worker.add_ext_vswitch(
                str(vswitch_name), str(nic_name)),
            self._add_ext_vswitch_completed)

    @QtCore.pyqtSlot()
    def open_horizon_url(self):
        LOG.debug("open_horizon_url called")
        _run_async_task(self._worker.open_horizon_url)

    @QtCore.pyqtSlot()
    def open_download_url(self):
        LOG.debug("open_download_url called")
        _run_async_task(self._worker.open_download_url)

    @QtCore.pyqtSlot()
    def open_controller_ssh(self):
        LOG.debug("open_controller_ssh called")
        _run_async_task(self._worker.open_controller_ssh)

    @QtCore.pyqtSlot()
    def open_issues_url(self):
        LOG.debug("open_issues_url called")
        _run_async_task(self._worker.open_issues_url)

    @QtCore.pyqtSlot()
    def open_github_url(self):
        LOG.debug("open_github_url called")
        _run_async_task(self._worker.open_github_url)

    @QtCore.pyqtSlot()
    def open_questions_url(self):
        LOG.debug("open_questions_url called")
        _run_async_task(self._worker.open_questions_url)

    @QtCore.pyqtSlot()
    def open_coriolis_url(self):
        LOG.debug("open_coriolis_url called")
        _run_async_task(self._worker.open_coriolis_url)


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
            appid = 'v_magine.1.0.0'
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
            # TODO: replace with HTML UI
            reply = QtWidgets.QMessageBox.question(
                self, constants.PRODUCT_NAME,
                "Interrupt the OpenStack deployment?",
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
    log_file = os.path.join(log_dir, '%s.log' % constants.PRODUCT_NAME)
    logging.basicConfig(filename=log_file, level=logging.DEBUG,
                        format=log_format)
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    logging.info("{0} - {1}".format(constants.PRODUCT_NAME, constants.VERSION))


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

        controller = Controller(deployment_worker.Worker())

        main_window = MainWindow(controller)
        splash = _create_splash_window(main_window)
        controller.set_splash_window(splash)
        controller.show_splash()

    loop = trollius.get_event_loop()
    loop.set_exception_handler(_async_exception_handler)
    # Need to run trollius event loop in a separate thread due to Qt event loop
    thread = threading.Thread(target=_run_async_loop, args=(loop,))
    thread.start()

    exit_code = app.exec_()
    loop.call_soon_threadsafe(loop.stop)
    thread.join()
    loop.close()

    sys.exit(exit_code)


def _run_async_task(coroutine, callback=None):
    return _run_async_tasks([(coroutine, callback)])[0]


def _run_async_tasks(tasks_info):
    tasks = []
    loop = trollius.get_event_loop()
    for (func, callback) in tasks_info:
        task = loop.run_in_executor(None, func)
        if callback:
            task.add_done_callback(callback)
        tasks.append(task)
    return tasks


def _async_exception_handler(loop, context):
    LOG.error(context.get("message"))
    ex = context.get("exception")
    if ex:
        LOG.exception(ex)


def _run_async_loop(loop):
    LOG.debug("run_async_loop")

    threading.current_thread().name = "AsyncLoopThread"
    pythoncom.CoInitialize()

    trollius.set_event_loop(loop)
    try:
        loop.run_forever()
    except Exception as ex:
        LOG.exception(ex)
    finally:
        loop.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'pybootd':
        del sys.argv[1]
        pybootd_daemons.main()
    else:
        if len(sys.argv) == 3 and sys.argv[1] == 'openurl':
            main(sys.argv[2])
        else:
            main()
