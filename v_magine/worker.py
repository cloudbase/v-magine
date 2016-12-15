# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
# Licensed under the AGPLv3, see LICENCE file for details.

import logging
import os
import socket
import threading
import time
import sys

import netaddr
import validators

from v_magine import actions
from v_magine import centos
from v_magine import constants
from v_magine import exceptions
from v_magine import rdo
from v_magine import security
from v_magine import utils

LOG = logging

OPENSTACK_DEFAULT_BASE_DIR_WIN32 = "\\OpenStack"
OPENSTACK_CONTROLLER_VM_NAME = "openstack-controller"
VMAGINE_DOWNLOAD_URL = "https://www.cloudbase.it/v-magine"
VMAGINE_GITHUB_URL = "https://github.com/cloudbase/v-magine"
VMAGINE_ISSUES_URL = "https://github.com/cloudbase/v-magine/issues"
VMAGINE_QUESTIONS_URL = "http://ask.cloudbase.it"
CORIOLIS_URL = "https://cloudbase.it/coriolis"


class _VMConsoleThread(threading.Thread):
    def __init__(self, console_named_pipe, stdout_callback):
        super(_VMConsoleThread, self).__init__()
        self.setDaemon(True)
        self._console_named_pipe = console_named_pipe
        self._stdout_callback = stdout_callback
        self._exception = None

    def get_exception(self):
        return self._exception

    def run(self):
        try:
            self._read_console()
            self._exception = None
        except Exception as ex:
            self._exception = ex

    def _read_console(self):
        base_dir = utils.get_base_dir()
        console_log_file = os.path.join(
            base_dir, "%s-console.log" % constants.PRODUCT_NAME)

        buf = ""
        menu_done = False

        with open(console_log_file, 'ab') as console_log_file:
            with open(self._console_named_pipe, 'rb') as vm_console_pipe:
                while True:
                    data = vm_console_pipe.readline()

                    # Exit loop when the VM reboots
                    if not data:
                        LOG.debug("Console: no more data")
                        break

                    # NOTE: Workaround due to formatting issues with menu.c32
                    # TODO: Needs to be fixed in term.js
                    if not menu_done:
                        buf += data
                        if b'\x1b' not in buf:
                            self._stdout_callback(data)
                        idx = buf.find(b"\x1b[0m")
                        if idx >= 0:
                            self._stdout_callback(buf[idx + len(b"\x1b[0m"):])
                            menu_done = True
                            buf = b""
                            LOG.debug("Console: pxelinux menu done")
                    else:
                        self._stdout_callback(data)

                    console_log_file.write(data)
                    # TODO(alexpilotti): Fix why the heck CentOS gets stuck
                    # instead of rebooting and remove this awful workaround :)
                    if data.find("Reached target Shutdown.") != -1:
                        LOG.debug("Console: reached target Shutdown")
                        break

                    if data.find("Warning: Could not boot.") != -1:
                        raise exceptions.CouldNotBootException()


class Worker(object):
    def __init__(self):
        super(Worker, self).__init__()

        self._term_type = None
        self._term_cols = None
        self._term_rows = None

        self._curr_step = 0
        self._max_steps = 0

        self._is_install_done = True

        self._dep_actions = actions.DeploymentActions()

        self._stdout_callback = None
        self._stderr_callback = None
        self._error_callback = None
        self._progress_status_update_callback = None

    def set_error_callback(self, callback):
        self._error_callback = callback

    def set_progress_status_update_callback(self, callback):
        self._progress_status_update_callback = callback

    def set_stdout_callback(self, callback):
        self._stdout_callback = callback

    def set_stderr_callback(self, callback):
        self._stderr_callback = callback

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

    def can_close(self):
        return self._is_install_done

    def _get_mac_address(self, vm_network_config, vnic_name):
        return [vnic_cfg[2] for vnic_cfg in vm_network_config
                if vnic_cfg[1] == vnic_name][0]

    def _update_status(self, msg):
        if self._cancel_deployment:
            raise exceptions.CancelDeploymentException()

        self._curr_step += 1
        self._progress_status_update_callback(
            True, self._curr_step, self._max_steps, msg)

    def _start_progress_status(self, msg=''):
        if msg:
            LOG.debug(msg)
        self._progress_status_update_callback(True, 0, 0, msg)

    def _stop_progress_status(self, msg=''):
        self._progress_status_update_callback(False, 0, 0, msg)

    def _deploy_openstack_vm(self, ext_vswitch_name, openstack_vm_vcpu_count,
                             openstack_vm_mem_mb, openstack_base_dir,
                             admin_password, repo_url,
                             mgmt_ext_ip, mgmt_ext_netmask,
                             mgmt_ext_gateway, mgmt_ext_name_servers,
                             proxy_url, proxy_username, proxy_password):
        vm_name = OPENSTACK_CONTROLLER_VM_NAME
        vm_admin_user = "root"
        vm_dir = os.path.join(openstack_base_dir, vm_name)

        # TODO(alexpilotti): Add support for more OSs
        pxe_os_id = "centos7"
        console_named_pipe = r"\\.\pipe\%s" % vm_name

        iso_path = os.path.join(vm_dir, "ks.iso")

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

        self._dep_actions.create_kickstart_image(
            iso_path, encrypted_password, mgmt_ext_mac_address,
            mgmt_int_mac_address, data_mac_address, ext_mac_address,
            repo_url, ssh_pub_key_path, mgmt_ext_ip, mgmt_ext_netmask,
            mgmt_ext_gateway, mgmt_ext_name_servers, proxy_url,
            proxy_username, proxy_password)

        self._update_status('Creating the OpenStack controller VM...')
        self._dep_actions.create_openstack_vm(
            vm_name, vm_dir, openstack_vm_vcpu_count,
            openstack_vm_mem_mb, None, iso_path,
            vm_network_config, console_named_pipe)

        vnic_ip_info = self._dep_actions.get_openstack_vm_ip_info(
            vm_network_config, internal_net_config["subnet"])

        LOG.debug("VNIC PXE IP info: %s " % vnic_ip_info)

        self._update_status('Starting PXE daemons...')
        self._dep_actions.start_pxe_service(
            internal_net_config["host_ip"],
            [vnic_ip[1:] for vnic_ip in vnic_ip_info], pxe_os_id)

        self._dep_actions.generate_mac_pxelinux_cfg(
            pxe_mac_address, mgmt_ext_mac_address.replace('-', ':'),
            repo_url, mgmt_ext_ip, mgmt_ext_netmask, mgmt_ext_gateway,
            mgmt_ext_name_servers, proxy_url, proxy_username,
            proxy_password)

        self._update_status('PXE booting OpenStack controller VM...')
        self._dep_actions.start_openstack_vm()

        LOG.debug("Reading from console")
        console_thread = _VMConsoleThread(console_named_pipe,
                                          self._stdout_callback)
        console_thread.start()
        console_thread.join()

        ex = console_thread.get_exception()
        if ex:
            if isinstance(ex, exceptions.CouldNotBootException):
                raise exceptions.CouldNotBootException(
                    'Unable to deploy the controller VM. Make sure that DHCP '
                    'is enabled on the "{0}" network and that the repository '
                    '"{1}" is accessible'.format(ext_vswitch_name, repo_url))
            else:
                raise ex

        self._update_status('Rebooting OpenStack controller VM...')
        self._dep_actions.reboot_openstack_vm()

        LOG.info("PXE booting done")

        vm_int_mgmt_ip = [vnic_ip[2] for vnic_ip in vnic_ip_info
                          if vnic_ip[0] == "%s-mgmt-int" % vm_name][0]

        return (vm_int_mgmt_ip, vm_admin_user, ssh_key_path)

    def _install_rdo(self, rdo_installer, host, ssh_key_path, username,
                     password, rdo_admin_password, fip_range, fip_range_start,
                     fip_range_end, fip_gateway, fip_name_servers):
        reboot_sleep_s = 30

        def reboot_and_reconnect():
            self._update_status('Rebooting RDO VM...')
            rdo_installer.reboot()

            time.sleep(reboot_sleep_s)

            self._update_status(
                'Enstablishing SSH connection with RDO VM...')
            rdo_installer.connect(host, ssh_key_path, username, password,
                                  self._term_type, self._term_cols,
                                  self._term_rows)

        try:
            self._update_status(
                'Waiting for the RDO VM to reboot...')
            time.sleep(reboot_sleep_s)

            self._update_status(
                'Enstablishing SSH connection with RDO VM...')
            rdo_installer.connect(host, ssh_key_path, username, password,
                                  self._term_type, self._term_cols,
                                  self._term_rows)

            self._update_status('Updating RDO VM...')
            rdo_installer.update_os()

            self._update_status('Installing RDO...')
            rdo_installer.install_rdo(rdo_admin_password, fip_range,
                                      fip_range_start, fip_range_end,
                                      fip_gateway, fip_name_servers)

            self._update_status(
                'Checking if rebooting the RDO VM is required...')
            if rdo_installer.check_new_kernel():
                reboot_and_reconnect()

            self._update_status('Installing Hyper-V LIS components...')
            rdo_installer.install_lis()
            reboot_and_reconnect()

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
            self._dep_actions.uninstall_product(
                msi_info[0], "uninstall_%s.log" % msi_info[1])

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

    def _get_default_openstack_base_dir(self):
        if sys.platform == 'win32':
            drive = os.environ['SYSTEMDRIVE']
            return os.path.join(drive, OPENSTACK_DEFAULT_BASE_DIR_WIN32)
        else:
            raise NotImplementedError()

    def get_compute_nodes(self):
        try:
            self._start_progress_status('Retrieving compute nodes info...')
            compute_nodes = self._dep_actions.get_compute_nodes()
            return compute_nodes
        except Exception as ex:
            LOG.exception(ex)
            self._error_callback(ex)
        finally:
            self._stop_progress_status()

    def get_config(self):
        try:
            LOG.debug("get_config called")

            self._start_progress_status('Loading default values...')

            min_mem_mb = 0
            suggested_mem_mb = 0
            max_mem_mb = 0

            try:
                # TODO: This data should not be retrieved if there is no
                # hypervisor
                (min_mem_mb, suggested_mem_mb,
                 max_mem_mb) = self._dep_actions.get_openstack_vm_memory_mb(
                    OPENSTACK_CONTROLLER_VM_NAME)
            except Exception as ex:
                LOG.exception(ex)

            cpu_count = utils.get_cpu_count()

            suggested_openstack_vm_vcpu_count = min(
                cpu_count,
                self._dep_actions.get_openstack_vm_recommended_vcpu_count())

            fip_range = None
            fip_range_start = None
            fip_range_end = None
            fip_gateway = None

            curr_user = self._dep_actions.get_current_user()

            proxy_url = utils.get_proxy()
            name_servers = utils.get_dns()

            config_dict = {
                "default_openstack_base_dir":
                self._get_default_openstack_base_dir(),
                "min_openstack_vm_mem_mb": min_mem_mb,
                "suggested_openstack_vm_mem_mb": suggested_mem_mb,
                "max_openstack_vm_mem_mb": max_mem_mb,
                "min_openstack_vm_vcpu_count": 1,
                "suggested_openstack_vm_vcpu_count":
                    suggested_openstack_vm_vcpu_count,
                "max_openstack_vm_vcpu_count": cpu_count,
                "default_hyperv_host_username": curr_user,
                "default_fip_range": fip_range,
                "default_fip_range_start": fip_range_start,
                "default_fip_range_end": fip_range_end,
                "default_fip_range_gateway": fip_gateway,
                "default_fip_range_name_servers": name_servers,
                "default_use_proxy": proxy_url is not None,
                "default_proxy_url": proxy_url,
                "default_mgmt_ext_dhcp": False,
                "default_mgmt_ext_name_servers": name_servers,
                "localhost": socket.gethostname(),
            }

            return config_dict
        except Exception as ex:
            LOG.exception(ex)
            self._error_callback(ex)
        finally:
            self._stop_progress_status()

    def get_repo_urls(self):
        try:
            LOG.debug("get_repo_urls called")
            self._start_progress_status('Loading repository mirrors list...')

            repo_urls = centos.get_repo_mirrors()
            return (repo_urls[0], repo_urls)
        except Exception as ex:
            LOG.exception(ex)
            self._error_callback(ex)
        finally:
            self._stop_progress_status()

    def check_platform_requirements(self):
        try:
            LOG.debug("check_platform_requirements called")
            self._start_progress_status('Checking requirements...')

            self._dep_actions.check_platform_requirements()
            self._check_openstack_vm_memory_requirements(
                OPENSTACK_CONTROLLER_VM_NAME)
            return True
        except Exception as ex:
            LOG.exception(ex)
            self._error_callback(ex)
            return False
        finally:
            self._stop_progress_status()

    def _check_openstack_vm_memory_requirements(self, vm_name):
        (min_mem_mb, suggested_mem_mb,
         max_mem_mb) = self._dep_actions.get_openstack_vm_memory_mb(vm_name)

        if max_mem_mb < min_mem_mb:
            raise Exception(
                "Not enough RAM available for OpenStack. "
                "Available: {:,} MB, "
                "required {:,} MB".format(max_mem_mb, min_mem_mb))

    def get_ext_vswitches(self):
        try:
            LOG.debug("get_ext_vswitches called")

            self._start_progress_status('Loading virtual switches...')

            ext_vswitches = self._dep_actions.get_ext_vswitches()
            LOG.debug("External vswitches: %s" % str(ext_vswitches))
            return ext_vswitches
        except Exception as ex:
            LOG.exception(ex)
            self._error_callback(ex)
            raise
        finally:
            self._stop_progress_status()

    def get_available_host_nics(self):
        try:
            LOG.debug("get_available_host_nics called")
            self._start_progress_status('Loading host NICs...')

            host_nics = self._dep_actions.get_available_host_nics()
            LOG.debug("Available host nics: %s" % str(host_nics))
            return host_nics
        except Exception as ex:
            LOG.exception(ex)
            self._error_callback(ex)
            raise
        finally:
            self._stop_progress_status()

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

            self._dep_actions.add_ext_vswitch(vswitch_name, nic_name)
            return vswitch_name
        except Exception as ex:
            LOG.exception(ex)
            self._error_callback(ex)
            raise
        finally:
            self._stop_progress_status()

    def _get_controller_ip(self):
        return self._dep_actions.get_vm_ip_address(
            OPENSTACK_CONTROLLER_VM_NAME)

    def get_deployment_details(self):
        try:
            LOG.debug("get_deployment_details called")
            self._start_progress_status(
                'Loading OpenStack deployment details...')

            controller_ip = self._get_controller_ip()
            if not controller_ip:
                raise Exception('The OpenStack controller is not available. '
                                'Please ensure that the "%s" virtual machine '
                                'is running' % OPENSTACK_CONTROLLER_VM_NAME)

            return (controller_ip, self._get_horizon_url(controller_ip))
        except Exception as ex:
            LOG.exception(ex)
            LOG.error(ex)
            self._error_callback(ex)
            missing_ip = "The OpenStack controller is not available"
            return (missing_ip, missing_ip)
        finally:
            self._stop_progress_status()

    def _get_horizon_url(self, controller_ip):
        # TODO(alexpilotti): This changes between Ubuntu and RDO
        return "http://%s" % controller_ip

    def open_horizon_url(self):
        try:
            self._start_progress_status('Opening OpenStack web console...')
            controller_ip = self._get_controller_ip()
            horizon_url = self._get_horizon_url(controller_ip)
            self._dep_actions.open_url(horizon_url)
        except Exception as ex:
            LOG.exception(ex)
            LOG.error(ex)
            self._error_callback(ex)
        finally:
            self._stop_progress_status()

    def _open_url(self, url):
        try:
            self._dep_actions.open_url(url)
        except Exception as ex:
            LOG.exception(ex)
            LOG.error(ex)
            self._error_callback(ex)

    def open_download_url(self):
        self._open_url(VMAGINE_DOWNLOAD_URL)

    def open_issues_url(self):
        self._open_url(VMAGINE_ISSUES_URL)

    def open_github_url(self):
        self._open_url(VMAGINE_GITHUB_URL)

    def open_questions_url(self):
        self._open_url(VMAGINE_QUESTIONS_URL)

    def open_coriolis_url(self):
        self._open_url(CORIOLIS_URL)

    def open_controller_ssh(self):
        try:
            self._start_progress_status('Opening OpenStack SSH console...')
            controller_ip = self._get_controller_ip()
            self._dep_actions.open_controller_ssh(controller_ip)
        except Exception as ex:
            LOG.exception(ex)
            LOG.error(ex)
            self._error_callback(ex)
        finally:
            self._stop_progress_status()

    def remove_openstack_deployment(self):
        try:
            LOG.debug("remove_openstack_deployment called")
            self._dep_actions.check_remove_vm(OPENSTACK_CONTROLLER_VM_NAME)
            self._dep_actions.set_openstack_deployment_status(False)
            return True
        except Exception as ex:
            LOG.exception(ex)
            self._error_callback(ex)

    def cancel_openstack_deployment(self):
        try:
            LOG.debug("cancel_openstack_deployment called")
            # TODO: evaluate synchronizing access to _cancel_deployment
            if not self._cancel_deployment:
                self._cancel_deployment = True
                self._dep_actions.check_remove_vm(OPENSTACK_CONTROLLER_VM_NAME)
        except Exception as ex:
            LOG.exception(ex)
            self._error_callback(ex)

    def deploy_openstack(self, args):
        try:
            self._start_progress_status('Deployment started')

            self._is_install_done = False
            self._cancel_deployment = False

            self._dep_actions.set_openstack_deployment_status(False)

            ext_vswitch_name = args.get("ext_vswitch_name")
            repo_url = args.get("centos_mirror")
            openstack_vm_mem_mb = int(args.get("openstack_vm_mem_mb"))
            openstack_vm_vcpu_count = int(args.get("openstack_vm_vcpu_count"))
            openstack_base_dir = args.get("openstack_base_dir")
            admin_password = args.get("admin_password")

            if not args.get("mgmt_ext_dhcp"):
                mgmt_ext_cidr = args.get("mgmt_ext_ip")
                mgmt_ext_gateway = str(netaddr.IPAddress(
                    args.get("mgmt_ext_gateway")))

                ip = netaddr.IPNetwork(mgmt_ext_cidr)
                mgmt_ext_ip = str(ip.ip)
                mgmt_ext_netmask = str(ip.netmask)
                mgmt_ext_name_servers = args.get("mgmt_ext_name_servers")
            else:
                mgmt_ext_ip = None
                mgmt_ext_netmask = None
                mgmt_ext_gateway = None
                mgmt_ext_name_servers = None

            if args.get("use_proxy"):
                proxy_url = args.get("proxy_url")
                proxy_username = args.get("proxy_username")
                proxy_password = args.get("proxy_password")
            else:
                proxy_url = None
                proxy_username = None
                proxy_password = None

            hyperv_host_username = args.get("hyperv_host_username")
            hyperv_host_password = args.get("hyperv_host_password")

            fip_range = str(netaddr.IPNetwork(args.get("fip_range")).cidr)
            fip_range_start = str(netaddr.IPAddress(
                args.get("fip_range_start")))
            fip_range_end = str(netaddr.IPAddress(
                args.get("fip_range_end")))
            fip_gateway = str(netaddr.IPAddress(
                args.get("fip_gateway")))
            fip_name_servers = args.get("fip_name_servers")

            self._curr_step = 0
            self._max_steps = 27

            self._dep_actions.check_platform_requirements()
            rdo_installer = rdo.RDOInstaller(self._stdout_callback,
                                             self._stderr_callback)

            (mgmt_ip, ssh_user, ssh_key_path) = self._deploy_openstack_vm(
                ext_vswitch_name, openstack_vm_vcpu_count,
                openstack_vm_mem_mb, openstack_base_dir,
                admin_password, repo_url,
                mgmt_ext_ip, mgmt_ext_netmask,
                mgmt_ext_gateway, mgmt_ext_name_servers, proxy_url,
                proxy_username, proxy_password)

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

            self._update_status('Your OpenStack deployment is ready!')

            self._dep_actions.set_openstack_deployment_status(True)
            return True
            self._stop_progress_status()
        except Exception as ex:
            LOG.exception(ex)
            LOG.error(ex)

            if self._cancel_deployment:
                msg = 'OpenStack deployment cancelled'
            else:
                msg = 'OpenStack deployment failed'

            self._stop_progress_status(msg)
            self._error_callback(ex)
            return False
        finally:
            self._dep_actions.stop_pxe_service()
            self._is_install_done = True

    def validate_host_config(self, username, password):
        try:
            LOG.debug("validate_host_config called")
            self._start_progress_status("Validating Hyper-V host user...")
            self._dep_actions.validate_host_user(username, password)
            return True
        except Exception as ex:
            LOG.exception(ex)
            self._error_callback(ex)
        finally:
            self._stop_progress_status()

    @staticmethod
    def _validate_single_ip_address(ip_address, error_msg):
        try:
            ip = netaddr.IPAddress(ip_address)
            if ip.is_netmask() or str(ip) != ip_address:
                raise exceptions.InvalidIPAddressException()
            return ip
        except Exception:
            raise exceptions.InvalidIPAddressException(
                error_msg % ip_address)

    @staticmethod
    def _validate_name_servers(name_servers, max_name_servers=None):
        if not name_servers:
            raise exceptions.BaseVMagineException(
                "At least one name server is required")

        if max_name_servers and len(name_servers) > max_name_servers:
            raise exceptions.BaseVMagineException(
                "At most two name servers can be specified")

        for name_server in name_servers:
            if not utils.is_valid_hostname(name_server):
                Worker._validate_single_ip_address(
                    name_server, "Invalid name server: %s")

    def validate_openstack_networking_config(self, fip_range, fip_range_start,
                                             fip_range_end, fip_gateway,
                                             fip_name_servers):
        LOG.debug("validate_openstack_networking_config called")
        try:
            LOG.debug("fip_range: %s", fip_range)
            try:
                ip_range = netaddr.IPNetwork(fip_range)
                if (ip_range.ip != ip_range.network or
                        ip_range.size == 1 or
                        ip_range.ip == ip_range.netmask or
                        str(ip_range.cidr) != fip_range):
                    raise exceptions.InvalidIPAddressException()
            except Exception:
                raise exceptions.InvalidIPAddressException(
                    "Invalid IP range: %s. The network needs to be "
                    "in CIDR notation, e.g. 192.168.0.0/24" % fip_range)

            LOG.debug("fip_range_start: %s", fip_range_start)
            ip_start = self._validate_single_ip_address(
                fip_range_start, "Invalid range start IP address: %s")

            if ip_start not in ip_range:
                raise exceptions.InvalidIPAddressException(
                    "The range start IP does not belong to the range "
                    "network: %s" % fip_range_start)

            LOG.debug("fip_range_end: %s", fip_range_end)
            ip_end = self._validate_single_ip_address(
                fip_range_end, "Invalid range end IP address: %s")

            if ip_end not in ip_range:
                raise exceptions.InvalidIPAddressException(
                    "The range end IP does not belong to the range "
                    "network: %s" % fip_range_start)

            if ip_end <= ip_start:
                raise exceptions.InvalidIPAddressException(
                    "The range end IP must be higher than the start IP")

            LOG.debug("fip_gateway: %s", fip_gateway)
            ip_gateway = self._validate_single_ip_address(
                fip_gateway, "Invalid gateway IP address: %s")

            if ip_start <= ip_gateway <= ip_end:
                raise exceptions.InvalidIPAddressException(
                    "The gateway IP can not be in the "
                    "%(fip_range_start)s-%(fip_range_end)s range" %
                    {"fip_range_start": fip_range_start,
                     "fip_range_end": fip_range_end})

            LOG.debug("fip_name_servers: %s", fip_name_servers)
            self._validate_name_servers(fip_name_servers)

            return True
        except Exception as ex:
            LOG.exception(ex)
            self._error_callback(ex)

    def validate_controller_config(self, mgmt_ext_dhcp, mgmt_ext_ip,
                                   mgmt_ext_gateway, mgmt_ext_name_servers,
                                   use_proxy, proxy_url, proxy_username,
                                   proxy_password):
        LOG.debug("validate_controller_config called")
        try:
            if not mgmt_ext_dhcp:
                LOG.debug("mgmt_ext_ip: %s", mgmt_ext_ip)
                try:
                    ip_address = mgmt_ext_ip.split("/")[0]
                    ip = self._validate_single_ip_address(ip_address, "")
                    ip_net = netaddr.IPNetwork(mgmt_ext_ip)
                    net_bits = ip_net.netmask.netmask_bits()
                    if (ip == ip_net.network or
                            "%s/%d" % (ip, net_bits) != mgmt_ext_ip):
                        raise exceptions.InvalidIPAddressException()
                except Exception:
                    raise exceptions.InvalidIPAddressException(
                        "Invalid IP address: %s. The address needs to be "
                        "in CIDR notation, e.g. 192.168.0.1/24" % mgmt_ext_ip)

                LOG.debug("mgmt_ext_gateway: %s", mgmt_ext_gateway)
                self._validate_single_ip_address(
                    mgmt_ext_gateway, "Invalid gateway IP address: %s")

                LOG.debug("mgmt_ext_name_servers: %s", mgmt_ext_name_servers)
                self._validate_name_servers(mgmt_ext_name_servers, 2)

            if use_proxy:
                LOG.debug("proxy_url: %s", proxy_url)
                if not validators.url(proxy_url):
                    raise exceptions.InvalidUrlException(
                        "Invalid proxy URL: %s" % proxy_url)

                if proxy_password and not proxy_username:
                    raise exceptions.BaseVMagineException(
                        "A proxy username must be specified if a password "
                        "is provided")

            return True
        except Exception as ex:
            LOG.exception(ex)
            self._error_callback(ex)

    def check_for_updates(self):
        try:
            self._start_progress_status("Checking for product updates...")
            update_info = self._dep_actions.check_for_updates()
            new_version = update_info.get("new_version")
            if new_version:
                return (
                    constants.VERSION,
                    new_version,
                    update_info.get("update_required"),
                    update_info.get("update_url"))
        except Exception as ex:
            LOG.exception(ex)
            self._error_callback(ex)
        finally:
            self._stop_progress_status()
