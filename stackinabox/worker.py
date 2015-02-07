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

import json
import logging
import os
import platform
import pythoncom
import socket
import threading
import time
import sys

from PyQt5 import QtCore

from stackinabox import actions
from stackinabox import rdo
from stackinabox import security
from stackinabox import utils

LOG = logging

DEFAULT_CENTOS_MIRROR = "http://mirror.centos.org/centos/7/os/x86_64"
OPENSTACK_DEFAULT_BASE_DIR_WIN32 = "\\OpenStack"
OPENSTACK_CONTROLLER_VM_NAME = "openstack-controller"

OPENDNS_NAME_SERVERS = ['208.67.222.222', '208.67.220.220']


class CancelDeploymentException(Exception):
    def __init__(self):
        msg = "Deployment cancelled by the user"
        super(CancelDeploymentException, self).__init__(msg)


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
    finished = QtCore.pyqtSignal()
    stdout_data_ready = QtCore.pyqtSignal(str)
    stderr_data_ready = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(Exception)
    install_done = QtCore.pyqtSignal(bool)
    get_ext_vswitches_completed = QtCore.pyqtSignal(list)
    get_available_host_nics_completed = QtCore.pyqtSignal(list)
    add_ext_vswitch_completed = QtCore.pyqtSignal(bool)
    get_deployment_details_completed = QtCore.pyqtSignal(str, str)
    platform_requirements_checked = QtCore.pyqtSignal()
    progress_status_update = QtCore.pyqtSignal(bool, int, int, str)

    def __init__(self, thread):
        super(Worker, self).__init__()

        self._tread = thread
        self.moveToThread(self._tread)
        self.finished.connect(self._tread.quit)
        self._tread.started.connect(self.started)

        self._term_type = None
        self._term_cols = None
        self._term_rows = None

        self._curr_step = 0
        self._max_steps = 0

        self._is_install_done = True

        self._dep_actions = actions.DeploymentActions()

        def stdout_callback(data):
            self.stdout_data_ready.emit(data)
        self._stdout_callback = stdout_callback

        def stderr_callback(data):
            self.stderr_data_ready.emit(data)
        self._stderr_callback = stderr_callback

    def is_eula_accepted(self):
        return self._dep_actions.is_eula_accepted()

    def set_eula_accepted(self):
        self._dep_actions.set_eula_accepted()

    def show_welcome(self):
        return self._dep_actions.show_welcome()

    def set_show_welcome(self, show):
        return self._dep_actions.set_show_welcome(show)

    def is_openstack_deployed(self):
        return self._dep_actions.is_openstack_deployed()

    def set_term_info(self, term_type, cols, rows):
        self._term_type = term_type
        self._term_cols = cols
        self._term_rows = rows
        LOG.debug("Term info set: %s" %
                  str((self._term_type, self._term_cols, self._term_rows)))

    @QtCore.pyqtSlot()
    def started(self):
        LOG.info("Started")
        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)

    def can_close(self):
        return self._is_install_done

    def _get_mac_address(self, vm_network_config, vnic_name):
        return [vnic_cfg[2] for vnic_cfg in vm_network_config
                if vnic_cfg[1] == vnic_name][0]

    def _update_status(self, msg):
        if self._cancel_deployment:
            raise CancelDeploymentException()

        self._curr_step += 1
        self.progress_status_update.emit(
            True, self._curr_step, self._max_steps, msg)

    def _start_progress_status(self, msg=''):
        self.progress_status_update.emit(True, 0, 0, msg)

    def _stop_progress_status(self, msg=''):
        self.progress_status_update.emit(False, 0, 0, msg)

    def _deploy_openstack_vm(self, ext_vswitch_name,
                             openstack_vm_mem_mb, openstack_base_dir,
                             admin_password):
        vm_name = OPENSTACK_CONTROLLER_VM_NAME
        vm_admin_user = "root"
        vm_dir = os.path.join(openstack_base_dir, vm_name)

        # TODO(alexpilotti): Add support for more OSs
        pxe_os_id = "centos7"
        console_named_pipe = r"\\.\pipe\%s" % vm_name

        # inst_repo = "http://10.14.0.142/centos/7.0/os/x86_64"
        inst_repo = DEFAULT_CENTOS_MIRROR

        vfd_path = os.path.join(vm_dir, "floppy.vfd")

        self._update_status('Generating SSH key...')
        (ssh_key_path,
         ssh_pub_key_path) = self._dep_actions.generate_controller_ssh_key()

        self._update_status('Generating MD5 password...')
        encrypted_password = security.get_password_md5(admin_password)

        if not os.path.isdir(vm_dir):
            os.makedirs(vm_dir)

        self._update_status('Check if OpenStack controller VM exists...')
        self._dep_actions.check_remove_vm(vm_name)

        self._update_status('Creating virtual switches...')
        internal_net_config = self._dep_actions.get_internal_network_config()
        self._dep_actions.create_vswitches(ext_vswitch_name,
                                           internal_net_config)

        vm_network_config = self._dep_actions.get_openstack_vm_network_config(
            vm_name, ext_vswitch_name)
        LOG.info("VNIC Network config: %s " % vm_network_config)

        mgmt_ext_mac_address = self._get_mac_address(vm_network_config,
                                                     "%s-mgmt-ext" % vm_name)
        mgmt_int_mac_address = self._get_mac_address(vm_network_config,
                                                     "%s-mgmt-int" % vm_name)
        data_mac_address = self._get_mac_address(vm_network_config,
                                                 "%s-data" % vm_name)
        ext_mac_address = self._get_mac_address(vm_network_config,
                                                "%s-ext" % vm_name)
        pxe_mac_address = self._get_mac_address(vm_network_config,
                                                "%s-pxe" % vm_name)

        self._dep_actions.create_kickstart_vfd(
            vfd_path, encrypted_password, mgmt_ext_mac_address,
            mgmt_int_mac_address, data_mac_address, ext_mac_address,
            inst_repo, ssh_pub_key_path)

        self._update_status('Creating the OpenStack controller VM...')
        self._dep_actions.create_openstack_vm(
            vm_name, vm_dir, openstack_vm_mem_mb, vfd_path, vm_network_config,
            console_named_pipe)

        vnic_ip_info = self._dep_actions.get_openstack_vm_ip_info(
            vm_network_config, internal_net_config["subnet"])

        LOG.debug("VNIC PXE IP info: %s " % vnic_ip_info)

        self._update_status('Starting PXE daemons...')
        self._dep_actions.start_pxe_service(
            internal_net_config["host_ip"],
            [vnic_ip[1:] for vnic_ip in vnic_ip_info], pxe_os_id)

        self._dep_actions.generate_mac_pxelinux_cfg(
            pxe_mac_address,
            mgmt_ext_mac_address.replace('-', ':'),
            inst_repo)

        self._update_status('PXE booting OpenStack controller VM...')
        self._dep_actions.start_openstack_vm()

        LOG.debug("Reading from console")
        console_thread = _VMConsoleThread(console_named_pipe,
                                          self._stdout_callback)
        console_thread.start()
        console_thread.join()

        self._update_status('Rebooting OpenStack controller VM...')
        self._dep_actions.reboot_openstack_vm()

        LOG.info("PXE booting done")

        vm_int_mgmt_ip = [vnic_ip[2] for vnic_ip in vnic_ip_info
                          if vnic_ip[0] == "%s-mgmt-int" % vm_name][0]

        return (vm_int_mgmt_ip, vm_admin_user, ssh_key_path)

    def _install_rdo(self, rdo_installer, host, ssh_key_path, username,
                     password, rdo_admin_password, fip_range, fip_range_start,
                     fip_range_end, fip_gateway, fip_name_servers):
        max_connect_attempts = 10
        reboot_sleep_s = 30

        try:
            self._update_status(
                'Waiting for the RDO VM to reboot...')
            time.sleep(reboot_sleep_s)

            self._update_status(
                'Enstablishing SSH connection with RDO VM...')
            rdo_installer.connect(host, ssh_key_path, username, password,
                                  self._term_type, self._term_cols,
                                  self._term_rows, max_connect_attempts)

            self._update_status('Updating RDO VM...')
            rdo_installer.update_os()

            self._update_status('Installing RDO...')
            rdo_installer.install_rdo(rdo_admin_password, fip_range,
                                      fip_range_start, fip_range_end,
                                      fip_gateway, fip_name_servers)

            self._update_status(
                'Checking if rebooting the RDO VM is required...')
            if rdo_installer.check_new_kernel():
                self._update_status('Rebooting RDO VM...')
                rdo_installer.reboot()

                time.sleep(reboot_sleep_s)

                self._update_status(
                    'Enstablishing SSH connection with RDO VM...')
                rdo_installer.connect(host, ssh_key_path, username, password,
                                      self._term_type, self._term_cols,
                                      self._term_rows, max_connect_attempts)

            self._update_status("Retrieving OpenStack configuration...")
            nova_config = rdo_installer.get_nova_config()

            self._update_status('RDO successfully deployed!')

            return nova_config
        finally:
            rdo_installer.disconnect()

    def _install_local_hyperv_compute(self, nova_config,
                                      openstack_base_dir, hyperv_host_username,
                                      hyperv_host_password):
        self._update_status('Checking if the OpenStack components for '
                            'Hyper-V are already installed...')
        for msi_info in self._dep_actions.check_installed_components():
            self._update_status('Uninstalling %s' % msi_info[1])
            self._dep_actions.uninstall_product(msi_info[0])

        nova_msi_path = "hyperv_nova_compute.msi"
        freerdp_webconnect_msi_path = "freerdp_webconnect.msi"
        try:
            self._update_status('Downloading Hyper-V OpenStack components...')
            self._dep_actions.download_hyperv_compute_msi(nova_msi_path)

            self._update_status('Installing Hyper-V OpenStack components...')
            self._dep_actions.install_hyperv_compute(
                nova_msi_path, nova_config, openstack_base_dir,
                hyperv_host_username, hyperv_host_password)

            self._update_status('Downloading FreeRDP-WebConnect...')
            self._dep_actions.download_freerdp_webconnect_msi(
                freerdp_webconnect_msi_path)

            self._update_status('Installing FreeRDP-WebConnect...')
            self._dep_actions.install_freerdp_webconnect(
                freerdp_webconnect_msi_path, nova_config,
                hyperv_host_username, hyperv_host_password)
        finally:
            if os.path.exists(nova_msi_path):
                os.remove(nova_msi_path)
            if os.path.exists(freerdp_webconnect_msi_path):
                os.remove(freerdp_webconnect_msi_path)

        self._update_status('Hyper-V OpenStack installed successfully')

    def _validate_deployment(self, rdo_installer):
        self._update_status('Validating OpenStack deployment...')
        # Skip for now
        # rdo_installer.check_hyperv_compute_services(platform.node())

    def _create_cirros_image(self, openstack_cred):
        image_path = "cirros.vhdx.gz"
        self._update_status('Downloading Cirros VHDX image...')
        self._dep_actions.download_cirros_image(image_path)
        self._update_status('Removing existing images...')
        self._dep_actions.delete_existing_images(openstack_cred)
        self._update_status('Uploading Cirros VHDX image in Glance...')
        self._dep_actions.create_cirros_image(openstack_cred, image_path)
        os.remove(image_path)

    def _get_default_openstack_base_dir(self):
        if sys.platform == 'win32':
            drive = os.environ['SYSTEMDRIVE']
            return os.path.join(drive, OPENSTACK_DEFAULT_BASE_DIR_WIN32)
        else:
            raise NotImplementedError()

    def _get_fip_range_data(self):
        fip_subnet = utils.get_random_ipv4_subnet()
        fip_range = "%s/24" % fip_subnet
        fip_gateway = fip_subnet[:-1] + "1"
        fip_range_start = fip_subnet[:-1] + "2"
        fip_range_end = fip_subnet[:-1] + "254"
        fip_gateway = fip_subnet[:-1] + "1"
        return (fip_range, fip_range_start, fip_range_end, fip_gateway)

    def get_config(self):
        try:
            (min_mem_mb, suggested_mem_mb,
             max_mem_mb) = self._dep_actions.get_openstack_vm_memory_mb(
                OPENSTACK_CONTROLLER_VM_NAME)

            (fip_range,
             fip_range_start,
             fip_range_end,
             fip_gateway) = self._get_fip_range_data()

            return {
                "default_openstack_base_dir":
                self._get_default_openstack_base_dir(),
                "default_centos_mirror": DEFAULT_CENTOS_MIRROR,
                "min_openstack_vm_mem_mb": min_mem_mb,
                "suggested_openstack_vm_mem_mb": suggested_mem_mb,
                "max_openstack_vm_mem_mb": max_mem_mb,
                "default_hyperv_host_username": "Administrator",
                "default_fip_range": fip_range,
                "default_fip_range_start": fip_range_start,
                "default_fip_range_end": fip_range_end,
                "default_fip_range_gateway": fip_gateway,
                "default_fip_range_name_servers": OPENDNS_NAME_SERVERS,
                "localhost": socket.gethostname()
            }
        except Exception as ex:
            LOG.exception(ex)
            self.error.emit(ex)
            raise

    @QtCore.pyqtSlot()
    def check_platform_requirements(self):
        try:
            LOG.debug("check_platform_requirements called")
            self._dep_actions.check_platform_requirements()
            self.platform_requirements_checked.emit()
        except Exception as ex:
            LOG.exception(ex)
            self.error.emit(ex)

    @QtCore.pyqtSlot()
    def get_ext_vswitches(self):
        try:
            LOG.debug("get_ext_vswitches called")

            self._start_progress_status('Loading virtual switches...')

            ext_vswitches = self._dep_actions.get_ext_vswitches()
            LOG.debug("External vswitches: %s" % str(ext_vswitches))
            self.get_ext_vswitches_completed.emit(ext_vswitches)
        except Exception as ex:
            LOG.exception(ex)
            self.error.emit(ex)
            raise
        finally:
            self._stop_progress_status()

    @QtCore.pyqtSlot()
    def get_available_host_nics(self):
        try:
            LOG.debug("get_available_host_nics called")
            self._start_progress_status('Loading host nics...')

            self.get_available_host_nics_completed.emit([])

            host_nics = self._dep_actions.get_available_host_nics()
            LOG.debug("Available host nics: %s" % str(host_nics))
            self.get_available_host_nics_completed.emit(host_nics)
        except Exception as ex:
            LOG.exception(ex)
            self.error.emit(ex)
            raise
        finally:
            self._stop_progress_status()

    @QtCore.pyqtSlot(str, str)
    def add_ext_vswitch(self, vswitch_name, nic_name):
        try:
            LOG.debug("add_ext_vswitch called, vswitch_name: "
                      "%(vswitch_name)s, nic_name: %(nic_name)s" %
                      {"vswitch_name": vswitch_name, "nic_name": nic_name})

            self._start_progress_status('Creating virtual switch...')

            ext_vswitches = self._dep_actions.get_ext_vswitches()
            if vswitch_name in ext_vswitches:
                raise Exception('A virtual switch with name "%s" already '
                                'exists' % vswitch_name)

            self._dep_actions.add_ext_vswitch(str(vswitch_name), str(nic_name))
            # Refresh VSwitch list
            self.get_ext_vswitches()
            self.add_ext_vswitch_completed.emit(True)
        except Exception as ex:
            LOG.exception(ex)
            self.error.emit(ex)
            self.add_ext_vswitch_completed.emit(False)
            raise
        finally:
            self._stop_progress_status()

    def _get_controller_ip(self):
        return self._dep_actions.get_vm_ip_address(
            OPENSTACK_CONTROLLER_VM_NAME) or ""

    @QtCore.pyqtSlot()
    def get_deployment_details(self):
        LOG.debug("get_deployment_details called")
        controller_ip = self._get_controller_ip()
        self.get_deployment_details_completed.emit(
            controller_ip,
            self._get_horizon_url(controller_ip))

    def _get_horizon_url(self, controller_ip):
        # TODO(alexpilotti): This changes between Ubuntu and RDO
        return "http://%s" % controller_ip

    @QtCore.pyqtSlot()
    def open_horizon_url(self):
        controller_ip = self._get_controller_ip()
        horizon_url = self._get_horizon_url(controller_ip)
        self._dep_actions.open_url(horizon_url)

    @QtCore.pyqtSlot()
    def open_controller_ssh(self):
        controller_ip = self._get_controller_ip()
        self._dep_actions.open_controller_ssh(controller_ip)

    @QtCore.pyqtSlot()
    def cancel_openstack_deployment(self):
        try:
            LOG.debug("cancel_openstack_deployment called")
            # TODO: evaluate synchronizing access to _cancel_deployment
            if not self._cancel_deployment:
                self._cancel_deployment = True
                self._dep_actions.check_remove_vm(OPENSTACK_CONTROLLER_VM_NAME)
        except Exception as ex:
            LOG.exception(ex)
            self.error.emit(ex)

    @QtCore.pyqtSlot(str)
    def deploy_openstack(self, json_args):
        try:
            self._start_progress_status('Deployment started')

            self._is_install_done = False
            self._cancel_deployment = False

            self._dep_actions.set_openstack_deployment_status(False)

            args = json.loads(str(json_args))

            ext_vswitch_name = args.get("ext_vswitch_name")
            openstack_vm_mem_mb = int(args.get("openstack_vm_mem_mb"))
            openstack_base_dir = args.get("openstack_base_dir")
            admin_password = args.get("admin_password")
            hyperv_host_username = args.get("hyperv_host_username")
            hyperv_host_password = args.get("hyperv_host_password")
            fip_range = args.get("fip_range")
            fip_range_start = args.get("fip_range_start")
            fip_range_end = args.get("fip_range_end")
            fip_gateway = args.get("fip_gateway")
            fip_name_servers = args.get("fip_name_servers")

            self._curr_step = 0
            self._max_steps = 27

            self._dep_actions.check_platform_requirements()
            rdo_installer = rdo.RDOInstaller(self._stdout_callback,
                                             self._stderr_callback)

            (mgmt_ip, ssh_user, ssh_key_path) = self._deploy_openstack_vm(
                ext_vswitch_name, openstack_vm_mem_mb,
                openstack_base_dir, admin_password)

            # Authenticate with the SSH key
            ssh_password = None
            # ssh_password = admin_password

            nova_config = self._install_rdo(rdo_installer, mgmt_ip,
                                            ssh_key_path, ssh_user,
                                            ssh_password, admin_password,
                                            fip_range, fip_range_start,
                                            fip_range_end, fip_gateway,
                                            fip_name_servers)
            LOG.debug("OpenStack config: %s" % nova_config)

            self._install_local_hyperv_compute(nova_config,
                                               openstack_base_dir,
                                               hyperv_host_username,
                                               hyperv_host_password)
            self._validate_deployment(rdo_installer)

            openstack_cred = self._dep_actions.get_openstack_credentials(
                mgmt_ip, admin_password)
            self._create_cirros_image(openstack_cred)

            self._update_status('Your OpenStack deployment is ready!')

            self._dep_actions.set_openstack_deployment_status(True)
            self.install_done.emit(True)
            self._stop_progress_status()
        except Exception as ex:
            LOG.exception(ex)
            LOG.error(ex)

            if self._cancel_deployment:
                msg = 'OpenStack deployment cancelled'
            else:
                msg = 'OpenStack deployment failed'

            self._stop_progress_status(msg)
            self.error.emit(ex)
            self.install_done.emit(False)
        finally:
            self._dep_actions.stop_pxe_service()
            self._is_install_done = True
