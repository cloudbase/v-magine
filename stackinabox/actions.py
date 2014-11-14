# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
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

import gzip
import logging
import os
import psutil

from oslo.utils import units

from stackinabox import glance
from stackinabox import kickstart
from stackinabox import pybootdmgr
from stackinabox import utils
from stackinabox import windows
from stackinabox.virt import base as base_virt_driver
from stackinabox.virt import factory as virt_factory

LOG = logging

VSWITCH_INTERNAL_NAME = "stackinabox-internal"
VSWITCH_DATA_NAME = "stackinabox-data"

FIREWALL_PXE_RULE_NAME = "stackinabox PXE"

DHCP_PORT = 67
TFTP_PORT = 69

MIN_OS_FREE_MEMORY_MB = 500
OPENSTACK_VM_RECOMMENDED_MEM_MB = 8 * 1024
OPENSTACK_VM_MIN_MEM_MB = 1 * 1024

OPENSTACK_VM_VHD_MAX_SIZE = 60 * units.Gi

DATA_VLAN_RANGE = range(500, 2000)

HYPERV_MSI_VENDOR = "Cloudbase Solutions Srl"
HYPERV_MSI_CAPTION_PREFIX = 'OpenStack Hyper-V Nova Compute'
HYPERV_MSI_URL = ("https://www.cloudbase.it/downloads/"
                  "HyperVNovaCompute_Juno_2014_2.msi")
CIRROS_VHDX_URL = ("https://raw.githubusercontent.com/cloudbase/"
                   "ci-overcloud-init-scripts/master/scripts/devstack_vm/"
                   "cirros-0.3.3-x86_64.vhdx.gz")

OPENSTACK_INSTANCES_PATH = "C:\\OpenStack\\Instances"
OPENSTACK_LOGDIR = "C:\\OpenStack\\Log"


class DeploymentActions(object):

    def __init__(self):
        self._pybootd_manager = pybootdmgr.PyBootdManager()
        self._virt_driver = virt_factory.get_virt_driver()
        self._windows_utils = windows.WindowsUtils()
        self._vm_name = None

    def check_hyperv_compute_installed(self):
        products = self._windows_utils.get_installed_products(
            HYPERV_MSI_VENDOR)
        for (product_id, caption) in products:
            if caption.startswith(HYPERV_MSI_CAPTION_PREFIX):
                return (product_id, caption)

    def uninstall_product(self, product_id):
        self._windows_utils.uninstall_product(product_id, "nova_uninstall.log")

    def download_hyperv_compute_msi(self, target_path):
        utils.retry_action(
            lambda: utils.download_file(HYPERV_MSI_URL, target_path))

    def download_cirros_image(self, target_path):
        utils.retry_action(
            lambda: utils.download_file(CIRROS_VHDX_URL, target_path))

    def get_openstack_credentials(self, mgmt_int_ip, password):
        auth_url = 'http://%s:5000/v2.0/' % mgmt_int_ip
        return {'tenant_name': 'admin', 'username': 'admin',
                'password': password, 'auth_url': auth_url}

    def delete_existing_images(self, openstack_cred):
        g = glance.GlanceClient()
        g.login(**openstack_cred)
        for image in g.get_images():
            g.delete_image(image['id'])

    def create_cirros_image(self, openstack_cred, gzipped_image_path):
        g = glance.GlanceClient()
        g.login(**openstack_cred)
        with gzip.open(gzipped_image_path, 'rb') as f:
            g.create_image('cirros', 'vhd', 'bare', f, 'hyperv', 'public')

    def install_hyperv_compute(self, msi_path, nova_config):

        features = ["HyperVNovaCompute", "NeutronHyperVAgent",
                    "iSCSISWInitiator", "FreeRDP"]

        properties = {}
        properties["RPCBACKEND"] = "RabbitMQ"

        properties["INSTANCESPATH"] = OPENSTACK_INSTANCES_PATH

        rabbit_hosts = nova_config["DEFAULT"]["rabbit_hosts"]
        (rabbit_host, rabbit_port) = rabbit_hosts.split(",")[0].split(':')

        properties["RPCBACKENDHOST"] = rabbit_host
        properties["RPCBACKENDPORT"] = rabbit_port

        glance_hosts = nova_config["DEFAULT"]["glance_api_servers"]
        (glance_host, glance_port) = glance_hosts.split(",")[0].split(':')

        properties["GLANCEHOST"] = glance_host
        properties["GLANCEPORT"] = glance_port

        properties["INSTANCESPATH"] = OPENSTACK_INSTANCES_PATH
        properties["OPENSTACK_LOGDIR"] = OPENSTACK_LOGDIR

        properties["RDPCONSOLEURL"] = "http://localhost:8000"

        properties["ADDVSWITCH"] = "0"
        properties["VSWITCHNAME"] = VSWITCH_DATA_NAME

        properties["USECOWIMAGES"] = "1"
        properties["FORCECONFIGDRIVE"] = "1"
        properties["CONFIGDRIVEINJECTPASSWORD"] = "1"
        properties["DYNAMICMEMORYRATIO"] = "1"
        properties["ENABLELOGGING"] = "1"
        properties["VERBOSELOGGING"] = "1"

        properties["NEUTRONURL"] = nova_config["DEFAULT"]["neutron_url"]
        properties["NEUTRONADMINTENANTNAME"] = nova_config["DEFAULT"][
            "neutron_admin_tenant_name"]
        properties["NEUTRONADMINUSERNAME"] = nova_config["DEFAULT"][
            "neutron_admin_username"]
        properties["NEUTRONADMINPASSWORD"] = nova_config["DEFAULT"][
            "neutron_admin_password"]
        properties["NEUTRONADMINAUTHURL"] = nova_config["DEFAULT"][
            "neutron_admin_auth_url"]

        if not os.path.exists(OPENSTACK_LOGDIR):
            os.makedirs(OPENSTACK_LOGDIR)

        LOG.info("Installing Nova compute")
        self._windows_utils.install_msi(msi_path, features, properties,
                                        "nova_install.log")
        LOG.info("Nova compute installed")

    def _get_openstack_vm_memory_mb(self):
        mem_info = psutil.virtual_memory()
        LOG.info("Host memory: %s" % str(mem_info))

        # Get the best option considering host limits
        max_mem_mb = min(mem_info.available / units.Mi - MIN_OS_FREE_MEMORY_MB,
                         OPENSTACK_VM_RECOMMENDED_MEM_MB)
        LOG.info("Memory to be assigned to the OpenStack VM: %sMB" %
                 max_mem_mb)

        return max_mem_mb

    def check_platform_requirements(self):
        self._virt_driver.check_platform()

    def generate_mac_pxelinux_cfg(self, pxe_mac_address, mgmt_ext_mac_address,
                                  inst_repo):
        self._pybootd_manager.generate_mac_pxelinux_cfg(
            pxe_mac_address,
            {'mgmt_ext_mac_address': mgmt_ext_mac_address,
             'inst_repo': inst_repo})

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

    def create_openstack_vm(self, vm_name, vm_dir, max_mem_mb, vfd_path,
                            vm_network_config, console_named_pipe):
        min_mem_mb = OPENSTACK_VM_MIN_MEM_MB
        if not max_mem_mb:
            max_mem_mb = self._get_openstack_vm_memory_mb()
        if max_mem_mb < min_mem_mb:
            raise Exception("Not enough RAM available for OpenStack")

        vhd_max_size = OPENSTACK_VM_VHD_MAX_SIZE
        # Set vCPU count equal to the hosts's core count
        vcpu_count = len(psutil.cpu_percent(interval=0, percpu=True))

        self._virt_driver.create_vm(vm_name, vm_dir, vhd_max_size,
                                    max_mem_mb, min_mem_mb, vcpu_count,
                                    vm_network_config, vfd_path,
                                    console_named_pipe)
        self._vm_name = vm_name

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

    def create_kickstart_vfd(self, vfd_path, encrypted_password,
                             mgmt_ext_mac_address, mgmt_int_mac_address,
                             data_mac_address, ext_mac_address, inst_repo):
        def _format_udev_mac(mac):
            return mac.lower().replace('-', ':')

        kickstart.generate_kickstart_vfd(
            vfd_path,
            {"encrypted_password": encrypted_password,
             "mgmt_ext_mac_address": _format_udev_mac(mgmt_ext_mac_address),
             "mgmt_int_mac_address": _format_udev_mac(mgmt_int_mac_address),
             "data_mac_address": _format_udev_mac(data_mac_address),
             "ext_mac_address": _format_udev_mac(ext_mac_address),
             "inst_repo": inst_repo})

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
