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

import logging
import os
import platform
import pythoncom
import threading
import time

from oslo.utils import units
from PySide import QtCore

from stackinabox import actions
from stackinabox import rdo
from stackinabox import security

LOG = logging

class _VMConsoleThread(threading.Thread):
    def __init__(self, console_named_pipe, stdout_callback):
        super(_VMConsoleThread, self).__init__()
        self.setDaemon(True)
        self._console_named_pipe = console_named_pipe
        self._stdout_callback = stdout_callback

    def run(self):
        with open(self._console_named_pipe, 'rb') as vm_console_pipe:
            while True:
                data = vm_console_pipe.readline()
                # Exit loop when the VM reboots
                if not data:
                    break
                self._stdout_callback(data)
                # TODO(alexpilotti): Fix why the heck CentOS gets stuck here
                # instead of rebooting and remove this awful workaround :)
                if data.find("Reached target Shutdown.") != -1:
                    break


class Worker(QtCore.QObject):
    finished = QtCore.Signal()
    stdout_data_ready = QtCore.Signal(str)
    stderr_data_ready = QtCore.Signal(str)
    status_changed = QtCore.Signal(str)
    error = QtCore.Signal(Exception)

    def __init__(self):
        super(Worker, self).__init__()

        self._term_type = None
        self._term_cols = None
        self._term_rows = None

        def stdout_callback(data):
            self.stdout_data_ready.emit(data)
        self._stdout_callback = stdout_callback

        def stderr_callback(data):
            self.stderr_data_ready.emit(data)
        self._stderr_callback = stderr_callback

    def set_term_info(self, term_type, cols, rows):
        self._term_type = term_type
        self._term_cols = cols
        self._term_rows = rows

    @QtCore.Slot()
    def started(self):
        LOG.info("Started")

    def _deploy_openstack_vm(self, dep_actions):
        vm_dir = "C:\\VM"
        external_vswitch_name = "external"
        vm_name = "openstack-controller"
        vm_admin_user = "root"
        max_vm_mem_mb = None
        # TODO(alexpilotti): Add support for more OSs
        pxe_os_id = "centos7"
        console_named_pipe = r"\\.\pipe\%s" % vm_name

        self.status_changed.emit('Generating random password...')
        password = security.get_random_password()
        # TODO Remove
        password = "Passw0rd"

        LOG.debug("Password: %s" % password)

        self.status_changed.emit('Generating MD5 password...')
        encrypted_password = security.get_password_md5(password)

        if not os.path.isdir(vm_dir):
            os.makedirs(vm_dir)

        self.status_changed.emit('Check if OpenStack controller VM exists...')
        dep_actions.check_remove_vm(vm_name)

        vfd_path = os.path.join(vm_dir, "floppy.vfd")
        dep_actions.create_kickstart_vfd(vfd_path, encrypted_password)

        self.status_changed.emit('Creating virtual switches...')
        internal_network_config = dep_actions.get_internal_network_config()
        dep_actions.create_vswitches(external_vswitch_name,
                                     internal_network_config)

        self.status_changed.emit('Creating the OpenStack controller VM...')
        vm_network_config = dep_actions.create_openstack_vm(
            vm_name, vm_dir, max_vm_mem_mb, vfd_path, external_vswitch_name,
            console_named_pipe)

        vnic_ip_info = dep_actions.get_openstack_vm_ip_info(
            vm_network_config, internal_network_config["subnet"])

        LOG.debug("VNIC IP info: %s " % vnic_ip_info)

        self.status_changed.emit('Starting PXE daemons...')
        dep_actions.start_pxe_service(
            internal_network_config["host_ip"],
            [vnic_ip[1:] for vnic_ip in vnic_ip_info], pxe_os_id)

        self.status_changed.emit('PXE booting OpenStack controller VM...')
        dep_actions.start_openstack_vm()

        LOG.debug("Reading from console")
        console_thread = _VMConsoleThread(console_named_pipe,
                                          self._stdout_callback)
        console_thread.start()
        console_thread.join()

        self.status_changed.emit('Rebooting OpenStack controller VM...')
        dep_actions.reboot_openstack_vm()

        LOG.info("PXE booting done")

        vm_int_mgmt_ip = [vnic_ip[2] for vnic_ip in vnic_ip_info
                          if vnic_ip[0] == "%s-mgmt-int" % vm_name][0]
        LOG.debug("Connection info: %s " %
                  str((vm_int_mgmt_ip, vm_admin_user, password)))

        return (vm_int_mgmt_ip, vm_admin_user, password)

    def _install_rdo(self, rdo_installer, host, username, password):
        LOG.info("install_rdo")
        max_connect_attempts = 10
        reboot_sleep_s = 5

        try:
            self.status_changed.emit(
                'Enstablishing SSH connection with RDO VM...')
            rdo_installer.connect(host, username, password,
                                  self._term_type, self._term_cols,
                                  self._term_rows, max_connect_attempts)

            self.status_changed.emit('Updating RDO VM...')
            rdo_installer.update_os()

            self.status_changed.emit('Installing RDO...')
            rdo_installer.install_rdo(password)

            self.status_changed.emit('Checking if rebooting the RDO VM is '
                                     'required...')
            if rdo_installer.check_new_kernel():
                self.status_changed.emit('Rebooting RDO VM...')
                rdo_installer.reboot()

                time.sleep(reboot_sleep_s)

                self.status_changed.emit(
                    'Enstablishing SSH connection with RDO VM...')
                rdo_installer.connect(host, username, password,
                                      self._term_type, self._term_cols,
                                      self._term_rows, max_connect_attempts)

            self.status_changed.emit("Retrieving OpenStack configuration...")
            nova_config = rdo_installer.get_nova_config()

            self.status_changed.emit('RDO successfully deployed!')

            return nova_config
        finally:
            rdo_installer.disconnect()

    def _install_local_hyperv_compute(self, dep_actions, nova_config):
        self.status_changed.emit('Checking if the OpenStack components for '
                                 'Hyper-V are already installed...')
        msi_info = dep_actions.check_hyperv_compute_installed()
        if msi_info:
            self.status_changed.emit('Uninstalling older version of the '
                                     'Hyper-V OpenStack components...')
            dep_actions.uninstall_product(msi_info[0])

        msi_path = "hyperv_nova_compute.msi"
        try:
            self.status_changed.emit('Downloading Hyper-V OpenStack '
                                     'components...')
            dep_actions.download_hyperv_compute_msi(msi_path)
            self.status_changed.emit('Installing Hyper-V OpenStack '
                                     'components...')
            dep_actions.install_hyperv_compute(msi_path, nova_config)
        finally:
            os.remove(msi_path)

        self.status_changed.emit('Hyper-V OpenStack installed successfully')

    def _validate_deployment(self, rdo_installer):
        self.status_changed.emit('Validating OpenStack deployment...')
        r.check_hyperv_compute_services(platform.node())
        self.status_changed.emit('Your OpenStack deployment is ready!')

    @QtCore.Slot()
    def deploy_openstack(self):
        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        dep_actions = actions.DeploymentActions()

        try:
            dep_actions.check_platform_requirements()
            rdo_installer = rdo.RDOInstaller(self._stdout_callback,
                                             self._stderr_callback)

            (ssh_ip, ssh_user, ssh_password) = self._deploy_openstack_vm(
                dep_actions)
            nova_config = self._install_rdo(rdo_installer, ssh_ip, ssh_user,
                                            ssh_password)
            self._install_local_hyperv_compute(dep_actions, nova_config)
            self._validate_deployment(rdo_installer)

        except Exception as ex:
            LOG.exception(ex)
            LOG.error(ex)
            self.error.emit(ex);
        finally:
            dep_actions.stop_pxe_service()
