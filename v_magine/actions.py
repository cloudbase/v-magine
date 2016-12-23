# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
# Licensed under the AGPLv3, see LICENCE file for details.

import json
import logging
import os
import socket
import sys

from oslo_utils import units
from six.moves.urllib import request

from v_magine import config
from v_magine import constants
from v_magine import kickstart
from v_magine import pybootdmgr
from v_magine import security
from v_magine import utils
from v_magine import windows
from v_magine.virt import base as base_virt_driver
from v_magine.virt import factory as virt_factory

LOG = logging

UPDATE_CHECK_URL = "https://www.cloudbase.it/checkupdates.php?p={0}&v={1}"

VSWITCH_INTERNAL_NAME = "%s-internal" % constants.PRODUCT_NAME
VSWITCH_DATA_NAME = "%s-data" % constants.PRODUCT_NAME

FIREWALL_PXE_RULE_NAME = "%s PXE" % constants.PRODUCT_NAME

DHCP_PORT = 67
TFTP_PORT = 69

FREERDP_WEBCONNECT_SERVICE_USER = "FreeRDP-WebConnect"

FREERDP_WEBCONNECT_HTTP_PORT = 8000
FREERDP_WEBCONNECT_HTTPS_PORT = 4430

OPENSTACK_MAX_VM_MEM_MB = 16 * 1024
OPENSTACK_MAX_VM_RECOMMENDED_MEM_MB = 6 * 1024
OPENSTACK_VM_MIN_MEM_MB = int(2.5 * 1024)
OPENSTACK_VM_RECOMMENDED_VCPU_COUNT = 4

OPENSTACK_MIN_INSTANCES_MEM_MB = 256

OPENSTACK_VM_VHD_MAX_SIZE = 60 * units.Gi

DATA_VLAN_RANGE = range(500, 2000)

HYPERV_MSI_VENDOR = "Cloudbase Solutions Srl"
HYPERV_MSI_CAPTION_PREFIX = 'OpenStack Hyper-V'
FREERDP_WEBCONNECT_CAPTION_PREFIX = "FreeRDP-WebConnect"
HYPERV_MSI_URL = ("https://www.cloudbase.it/downloads/"
                  "HyperVNovaCompute_Newton_14_0_1.msi")
FREERDP_WEBCONNECT_MSI_URL = ("https://www.cloudbase.it/downloads/"
                              "FreeRDPWebConnect.msi")

OPENSTACK_INSTANCES_DIR = "Instances"
OPENSTACK_LOG_DIR = "Log"

CONTROLLER_SSH_KEY_NAME = "%s_controller_rsa" % constants.PRODUCT_NAME

HYPERVISOR_TYPE_HYPERV = "Hyper-V"


class DeploymentActions(object):

    def __init__(self):
        self._pybootd_manager = pybootdmgr.PyBootdManager()
        self._virt_driver = virt_factory.get_virt_driver()
        self._windows_utils = windows.WindowsUtils()
        self._config = config.AppConfig()
        self._vm_name = None

    def check_installed_components(self):
        installed_products = []
        products = self._windows_utils.get_installed_products(
            HYPERV_MSI_VENDOR)
        for (product_id, caption) in products:
            if (caption.startswith(HYPERV_MSI_CAPTION_PREFIX) or
                    caption.startswith(FREERDP_WEBCONNECT_CAPTION_PREFIX)):
                installed_products.append((product_id, caption))
        return installed_products

    def is_openstack_deployed(self):
        return bool(self._config.get_config_value("deployment_status"))

    def set_openstack_deployment_status(self, deployed):
        self._config.set_config_value("deployment_status", deployed)

    def is_eula_accepted(self):
        return bool(self._config.get_config_value("eula"))

    def set_eula_accepted(self):
        self._config.set_config_value("eula", True)

    def show_welcome(self):
        return bool(self._config.get_config_value("show_welcome",
                                                  default=True))

    def set_show_welcome(self, show):
        self._config.set_config_value("show_welcome", show)

    def _get_controller_ssh_key_path(self):
        ssh_dir = security.get_user_ssh_dir()
        return os.path.join(ssh_dir, CONTROLLER_SSH_KEY_NAME)

    def get_vm_ip_address(self, vm_name):
        if self._virt_driver.vm_exists(vm_name):
            (ipv4_addresses,
             ipv6_addresses) = self._virt_driver.get_guest_ip_addresses(
                vm_name)

            if ipv4_addresses:
                return ipv4_addresses[0]
            elif ipv6_addresses:
                return ipv6_addresses[0]

    @staticmethod
    def _get_powershell_encoded_cmd(cmd):
        return cmd.encode('utf-16le').encode('base64')

    @staticmethod
    def _get_powershell_path():
        return (r"%s\System32\WindowsPowerShell\v1.0\powershell.exe" %
                os.environ["SystemRoot"])

    def open_controller_ssh(self, host_address):
        key_path = self._get_controller_ssh_key_path()

        ssh_user = "root"
        bin_dir = utils.get_bin_dir()
        ssh_path = os.path.join(bin_dir, "ssh.exe")
        title = "V-Magine - OpenStack SSH Console"

        encoded_cmd = self._get_powershell_encoded_cmd(
            '$host.ui.RawUI.WindowTitle = "%(title)s"; '
            '& "%(ssh_path)s" -o StrictHostKeyChecking=no -i "%(key_path)s" '
            '%(user)s@%(host)s -t bash --rcfile keystonerc_admin -i' %
            {"title": title, "ssh_path": ssh_path, "key_path": key_path,
             "user": ssh_user, "host": host_address})

        self._windows_utils.run_safe_process(
            self._get_powershell_path(), "-EncodedCommand %s" % encoded_cmd,
            new_console=True)

    def generate_controller_ssh_key(self):
        key_path = self._get_controller_ssh_key_path()
        return security.generate_ssh_key(key_path)

    def uninstall_product(self, product_id, log_file):
        self._windows_utils.uninstall_product(product_id, log_file)

    @utils.retry_on_error()
    def download_hyperv_compute_msi(self, target_path):
        utils.download_file(HYPERV_MSI_URL, target_path)

    @utils.retry_on_error()
    def download_freerdp_webconnect_msi(self, target_path):
        utils.download_file(FREERDP_WEBCONNECT_MSI_URL, target_path)

    @staticmethod
    def _get_keystone_v2_url(auth_url):
        return auth_url[:-2] + "v2.0" if auth_url.endswith("v3") else auth_url

    def install_freerdp_webconnect(self, msi_path, nova_config,
                                   hyperv_host_username,
                                   hyperv_host_password):

        features = ['FreeRDPWebConnect', 'VC120Redist']
        properties = {}

        # properties["REDIRECT_HTTPS"] = "1"

        properties["HTTP_PORT"] = FREERDP_WEBCONNECT_HTTP_PORT
        properties["HTTPS_PORT"] = FREERDP_WEBCONNECT_HTTPS_PORT
        properties["ENABLE_FIREWALL_RULES"] = "1"

        properties["OPENSTACK_AUTH_URL"] = self._get_keystone_v2_url(
            nova_config["neutron"]["auth_url"])
        properties["OPENSTACK_TENANT_NAME"] = nova_config[
            "keystone_authtoken"]["project_name"]
        properties["OPENSTACK_USERNAME"] = nova_config["keystone_authtoken"][
            "username"]
        properties["OPENSTACK_PASSWORD"] = nova_config["keystone_authtoken"][
            "password"]

        properties["HYPERV_HOST_USERNAME"] = hyperv_host_username
        properties["HYPERV_HOST_PASSWORD"] = hyperv_host_password

        LOG.info("Installing FreeRDP-WebConnect")
        self._windows_utils.install_msi(msi_path, features, properties,
                                        "freerdp_webconnect.log")
        LOG.info("FreeRDP-WebConnect installed")

        LOG.info("Adding FreeRDP-WebConnect user to Remote Desktop Users")
        # This is needed on client OS
        group_domain, group_name = self._windows_utils.get_group_by_sid(
            windows.GROUP_SID_REMOTE_DESKTOP_USERS)
        self._windows_utils.add_user_to_local_group(
            FREERDP_WEBCONNECT_SERVICE_USER, group_name)

    def _check_username(self, username):
        username = username.strip()
        if "\\" not in username:
            username = "%(host)s\\%(username)s" % {
                "host": socket.gethostname(),
                "username": username}
        return username

    def open_url(self, url):
        LOG.debug("Opening url: %s", url)
        if not self._windows_utils.open_url(url):
            self._windows_utils.run_safe_process(
                sys.executable, "openurl %s" % url)

    def install_hyperv_compute(self, msi_path, nova_config,
                               openstack_base_dir, hyperv_host_username,
                               hyperv_host_password):
        instances_path = os.path.join(openstack_base_dir,
                                      OPENSTACK_INSTANCES_DIR)
        openstack_log_dir = os.path.join(openstack_base_dir, OPENSTACK_LOG_DIR)

        features = ["HyperVNovaCompute", "NeutronHyperVAgent",
                    "iSCSISWInitiator", "FreeRDP"]

        properties = {}
        properties["RPCBACKEND"] = "RabbitMQ"

        properties["RPCBACKENDHOST"] = nova_config["oslo_messaging_rabbit"][
            "rabbit_host"]
        properties["RPCBACKENDPORT"] = nova_config["oslo_messaging_rabbit"][
            "rabbit_port"]

        glance_hosts = nova_config["glance"]["api_servers"]
        (glance_host, glance_port) = glance_hosts.split(",")[0].split(':')

        properties["GLANCEHOST"] = glance_host
        properties["GLANCEPORT"] = glance_port

        properties["INSTANCESPATH"] = instances_path
        properties["LOGDIR"] = openstack_log_dir

        rdp_console_url = "http://%(host)s:%(port)d" % {
            "host": socket.gethostname(),
            "port": FREERDP_WEBCONNECT_HTTP_PORT}

        properties["RDPCONSOLEURL"] = rdp_console_url

        properties["ADDVSWITCH"] = "0"
        properties["VSWITCHNAME"] = VSWITCH_DATA_NAME

        properties["USECOWIMAGES"] = "1"
        properties["FORCECONFIGDRIVE"] = "1"
        properties["CONFIGDRIVEINJECTPASSWORD"] = "1"
        properties["DYNAMICMEMORYRATIO"] = "1"
        properties["ENABLELOGGING"] = "1"
        properties["VERBOSELOGGING"] = "1"

        properties["NEUTRONURL"] = nova_config["neutron"]["url"]
        properties["NEUTRONADMINTENANTNAME"] = nova_config["neutron"][
            "project_name"]
        properties["NEUTRONADMINUSERNAME"] = nova_config["neutron"][
            "username"]
        properties["NEUTRONADMINPASSWORD"] = nova_config["neutron"][
            "password"]
        properties["NEUTRONADMINAUTHURL"] = nova_config["neutron"][
            "auth_url"]

        if hyperv_host_username:
            properties["NOVACOMPUTESERVICEUSER"] = self._check_username(
                hyperv_host_username)
            properties["NOVACOMPUTESERVICEPASSWORD"] = hyperv_host_password

        if not os.path.exists(openstack_log_dir):
            os.makedirs(openstack_log_dir)

        LOG.info("Installing Nova compute")
        self._windows_utils.install_msi(msi_path, features, properties,
                                        "nova_install.log")
        LOG.info("Nova compute installed")

    @staticmethod
    def get_openstack_vm_recommended_vcpu_count():
        return OPENSTACK_VM_RECOMMENDED_VCPU_COUNT

    def get_openstack_vm_memory_mb(self, vm_name):
        mem_available = self._virt_driver.get_host_available_memory()
        LOG.info("Host available memory: %s" % mem_available)

        if self._virt_driver.vm_exists(vm_name):
            # If the controller VM exists, add its memory as it will be deleted
            mem_available += self._virt_driver.get_vm_memory_usage(vm_name)

        max_mem_mb = min(mem_available / units.Mi, OPENSTACK_MAX_VM_MEM_MB)
        # Get the best option considering host limits
        suggested_mem_mb = min(
            max(max_mem_mb - OPENSTACK_MIN_INSTANCES_MEM_MB, 0),
            OPENSTACK_MAX_VM_RECOMMENDED_MEM_MB)

        return (OPENSTACK_VM_MIN_MEM_MB, suggested_mem_mb, max_mem_mb)

    def check_platform_requirements(self):
        self._virt_driver.check_platform()

    @staticmethod
    def _get_primary_secondary_dns(name_servers):
        if not name_servers:
            return None, None
        dns1 = name_servers[0].strip() if len(name_servers) else None
        dns2 = name_servers[1].strip() if len(name_servers) > 1 else None
        return dns1, dns2

    def generate_mac_pxelinux_cfg(self, pxe_mac_address, mgmt_ext_mac_address,
                                  inst_repo, mgmt_ext_ip, mgmt_ext_netmask,
                                  mgmt_ext_gateway, mgmt_ext_name_servers,
                                  proxy_url, proxy_username, proxy_password):

        proxy_url = utils.add_credentials_to_url(
            proxy_url, proxy_username, proxy_password)

        mgmt_ext_dns1, mgmt_ext_dns2 = self._get_primary_secondary_dns(
            mgmt_ext_name_servers)

        self._pybootd_manager.generate_mac_pxelinux_cfg(
            pxe_mac_address,
            {'mgmt_ext_mac_address': mgmt_ext_mac_address,
             'inst_repo': inst_repo,
             "mgmt_ext_ip": mgmt_ext_ip,
             "mgmt_ext_netmask": mgmt_ext_netmask,
             "mgmt_ext_gateway": mgmt_ext_gateway,
             "mgmt_ext_dns1": mgmt_ext_dns1,
             "mgmt_ext_dns2": mgmt_ext_dns2,
             "proxy_url": proxy_url})

    def start_pxe_service(self, listen_address, reservations, pxe_os_id):
        pxe_base_dir = utils.get_pxe_files_dir()
        tftp_root_dir = os.path.join(pxe_base_dir, pxe_os_id)

        self._pybootd_manager.start(listen_address, tftp_root_dir,
                                    reservations[0][1], reservations)

    def stop_pxe_service(self):
        self._pybootd_manager.stop()

    def check_remove_vm(self, vm_name):
        if self._virt_driver.vm_exists(vm_name):
            if not self._virt_driver.vm_is_stopped(vm_name):
                self._virt_driver.power_off_vm(vm_name)
            self._virt_driver.destroy_vm(vm_name)

    def get_openstack_vm_network_config(self, vm_name, external_vswitch_name):
        # vmswitch_name, vmnic_name, mac_address, pxe, allow_mac_spoofing,
        # access_vlan_id, trunk_vlan_ids, private_vlan_id
        vm_network_config = [
            (external_vswitch_name, "%s-mgmt-ext" % vm_name,
             utils.get_random_mac_address(),
             False, False, None, None, None),
            (VSWITCH_INTERNAL_NAME, "%s-mgmt-int" % vm_name,
             utils.get_random_mac_address(),
             False, False, None, None, None),
            (VSWITCH_DATA_NAME, "%s-data" % vm_name,
             utils.get_random_mac_address(),
             False, True, None, DATA_VLAN_RANGE, 0),
            (external_vswitch_name, "%s-ext" % vm_name,
             utils.get_random_mac_address(),
             False, True, None, None, None),
            (VSWITCH_INTERNAL_NAME, "%s-pxe" % vm_name,
             utils.get_random_mac_address(),
             True, False, None, None, None),
        ]

        return vm_network_config

    def create_openstack_vm(self, vm_name, vm_dir, vcpu_count, max_mem_mb,
                            vfd_path, iso_path, vm_network_config,
                            console_named_pipe):
        (min_mem_mb, max_mem_mb_auto,
         max_mem_mb_limit) = self.get_openstack_vm_memory_mb(vm_name)

        if not max_mem_mb:
            max_mem_mb = max_mem_mb_auto
        if max_mem_mb < min_mem_mb:
            raise Exception("Not enough RAM available for OpenStack")

        vhd_max_size = OPENSTACK_VM_VHD_MAX_SIZE

        self._virt_driver.create_vm(vm_name, vm_dir, vhd_max_size,
                                    max_mem_mb, min_mem_mb, vcpu_count,
                                    vm_network_config, vfd_path, iso_path,
                                    console_named_pipe)
        self._vm_name = vm_name

    def get_available_host_nics(self):
        return [nic for nic in self._virt_driver.get_host_nics()
                if not nic["in_use"]]

    def get_ext_vswitches(self):
        return [vswitch['name'] for vswitch in
                self._virt_driver.get_vswitches() if vswitch['is_external']]

    def add_ext_vswitch(self, vswitch_name, nic_name):
        self._virt_driver.create_vswitch(vswitch_name, nic_name, True)

    def start_openstack_vm(self):
        self._virt_driver.start_vm(self._vm_name)

    def reboot_openstack_vm(self):
        self._virt_driver.reboot_vm(self._vm_name)

    def get_internal_network_config(self):
        subnet = utils.get_random_ipv4_subnet()
        netmask = "255.255.255.0"
        host_ip = subnet[:-1] + "1"

        return {"subnet": subnet,
                "netmask": netmask,
                "host_ip": host_ip}

    def get_openstack_vm_ip_info(self, vm_network_config, subnet):
        """
        Assigns an IPv4 to every vnic with a static mac address.
        Returns a list of tuples (vnic_name, mac_address, ipv4)
        """
        vnic_ip_info = []
        base_addr = subnet[:-1]
        last_octet = 2

        [vnic_ip_info.append((vif_config[1], vif_config[2],
                              base_addr + str(last_octet)))
            for vif_config in vm_network_config
         if vif_config[1] == "%s-pxe" % self._vm_name]

        last_octet += 1

        [vnic_ip_info.append((vif_config[1], vif_config[2],
                              base_addr + str(last_octet)))
            for vif_config in vm_network_config
         if vif_config[1] == "%s-mgmt-int" % self._vm_name]

        return vnic_ip_info

    def create_kickstart_image(self, ks_image_path, encrypted_password,
                               mgmt_ext_mac_address, mgmt_int_mac_address,
                               data_mac_address, ext_mac_address, inst_repo,
                               ssh_pub_key_path, mgmt_ext_ip, mgmt_ext_netmask,
                               mgmt_ext_gateway, mgmt_ext_name_servers,
                               proxy_url, proxy_username, proxy_password):
        def _format_udev_mac(mac):
            return mac.lower().replace('-', ':')

        with open(ssh_pub_key_path, 'rb') as f:
            ssh_pub_key = f.read()

        proxy_url = utils.add_credentials_to_url(
            proxy_url, proxy_username, proxy_password)

        mgmt_ext_dns1, mgmt_ext_dns2 = self._get_primary_secondary_dns(
            mgmt_ext_name_servers)

        kickstart.generate_kickstart_image(
            ks_image_path,
            {"encrypted_password": encrypted_password,
             "mgmt_ext_mac_address": _format_udev_mac(mgmt_ext_mac_address),
             "mgmt_int_mac_address": _format_udev_mac(mgmt_int_mac_address),
             "data_mac_address": _format_udev_mac(data_mac_address),
             "ext_mac_address": _format_udev_mac(ext_mac_address),
             "inst_repo": inst_repo,
             "ssh_pub_key": ssh_pub_key,
             "mgmt_ext_ip": mgmt_ext_ip,
             "mgmt_ext_netmask": mgmt_ext_netmask,
             "mgmt_ext_gateway": mgmt_ext_gateway,
             "mgmt_ext_dns1": mgmt_ext_dns1,
             "mgmt_ext_dns2": mgmt_ext_dns2,
             "proxy_url": proxy_url})

    def create_vswitches(self, external_vswitch_name, internal_network_config):
        virt_driver = virt_factory.get_virt_driver()

        if not virt_driver.vswitch_exists(external_vswitch_name):
            raise Exception("Virtual switch not found: %s" %
                            external_vswitch_name)

        if not virt_driver.vswitch_exists(VSWITCH_INTERNAL_NAME):
            virt_driver.create_vswitch(VSWITCH_INTERNAL_NAME,
                                       create_internal_port=True)

        virt_driver.set_vswitch_host_ip(VSWITCH_INTERNAL_NAME,
                                        internal_network_config["host_ip"],
                                        internal_network_config["netmask"])

        local_ports = str(DHCP_PORT) + "," + str(TFTP_PORT)
        virt_driver.add_vswitch_host_firewall_rule(VSWITCH_INTERNAL_NAME,
                                                   FIREWALL_PXE_RULE_NAME,
                                                   local_ports,
                                                   base_virt_driver.UDP)

        if not virt_driver.vswitch_exists(VSWITCH_DATA_NAME):
            virt_driver.create_vswitch(VSWITCH_DATA_NAME)

    def get_current_user(self):
        domain, username = self._windows_utils.get_current_user()

        if domain.lower() != socket.gethostname().lower():
            username = "%(domain)s\\%(username)s" % {
                'domain': domain, 'username': username}

        return username

    def validate_host_user(self, username, password):
        username_split = username.split("\\")
        if len(username_split) > 1:
            domain = username_split[0]
            domain_username = username_split[1]
        else:
            domain = "."
            domain_username = username

        try:
            token = self._windows_utils.create_user_logon_session(
                domain_username, password, domain)
            self._windows_utils.close_user_logon_session(token)
        except windows.LogonFailedException:
            raise Exception('Login failed for user "%s"' % username)

    def check_for_updates(self):
        try:
            url = UPDATE_CHECK_URL.format(
                constants.PRODUCT_NAME, constants.VERSION)
            req = request.Request(
                url, headers={'User-Agent': constants.PRODUCT_NAME})
            return json.loads(request.urlopen(req).read().decode())
        except Exception as ex:
            LOG.exception(ex)
            raise Exception("Checking for product updates failed")

    def get_compute_nodes(self):
        # TODO: return a list of hosts once multiple hosts will be supported
        localhost_version_info = self._windows_utils.get_windows_version_info()
        # TODO: return the actual host name once the UI allows longer names
        localhost_version_info['hostname'] = "localhost"
        # localhost_version_info['hostname'] = socket.gethostname()
        localhost_version_info['hypervisor_type'] = HYPERVISOR_TYPE_HYPERV
        return [localhost_version_info]
