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

import os
import psutil
import sys

from oslo.utils import units

from stackinabox import kickstart
from stackinabox import pybootd
from stackinabox import utils
from stackinabox.virt import base as base_virt_driver
from stackinabox.virt import factory as virt_factory

VSWITCH_INTERNAL_NAME = "stackinabox-internal"
VSWITCH_DATA_NAME = "stackinabox-data"

FIREWALL_PXE_RULE_NAME = "stackinabox PXE"

DHCP_PORT = 67
TFTP_PORT = 69

MIN_OS_FREE_MEMORY_MB = 1.5 * 1024
OPENSTACK_VM_RECOMMENDED_MEM_MB = 8 * 1024
OPENSTACK_VM_MIN_MEM_MB = 1 * 1024

OPENSTACK_VM_VHD_MAX_SIZE = 60 * units.Gi

DATA_VLAN_RANGE = range(500, 2000)


class DeploymentActions(object):

    def __init__(self):
        self._pybootd_manager = pybootd.PyBootdManager()
        self._virt_driver = virt_factory.get_virt_driver()

    def _get_openstack_vm_memory_mb(self):
        mem_info = psutil.virtual_memory()
        # Get the best option considering host limits
        max_mem_mb = min(mem_info.total / units.Mi - MIN_OS_FREE_MEMORY_MB,
                         OPENSTACK_VM_RECOMMENDED_MEM_MB)
        return max_mem_mb

    def start_pxe_service(self, listen_address, reservations, pxe_os_id):
        pxe_base_dir = utils.get_pxe_files_dir()
        tftp_root_dir = os.path.join(pxe_base_dir, pxe_os_id)

        tftp_root_url = "file://"
        if sys.platform == "win32":
            # Note: pybootd fails if the drive is in the url
            tftp_root_url += tftp_root_dir.replace("\\", "/")[2:]
        else:
            tftp_root_url += tftp_root_dir

        self._pybootd_manager.start(listen_address, tftp_root_url,
                                    reservations[0][1], reservations)

    def stop_pxe_service(self, pybootd_manager):
        self._pybootd_manager.stop()

    def check_remove_openstack_vm(self, vm_name):
        if self._virt_driver.vm_exists(vm_name):
            if not self._virt_driver.vm_is_stopped(vm_name):
                self._virt_driver.power_off_vm(vm_name)
            self._virt_driver.destroy_vm(vm_name)

    def create_openstack_vm(self, vm_name, vm_dir, max_mem_mb, vfd_path,
                            external_vswitch_name):
        min_mem_mb = OPENSTACK_VM_MIN_MEM_MB
        if not max_mem_mb:
            max_mem_mb = self._get_openstack_vm_memory_mb()
        if max_mem_mb < min_mem_mb:
            raise Exception("Not enough RAM available for OpenStack")

        vhd_max_size = OPENSTACK_VM_VHD_MAX_SIZE
        # Set vCPU count equal to the hosts's core count
        vcpu_count = len(psutil.cpu_percent(interval=0, percpu=True))

        # vmswitch_name, vmnic_name, mac_address, pxe, allow_mac_spoofing,
        # access_vlan_id, trunk_vlan_ids, private_vlan_id
        vm_network_config = [
            (external_vswitch_name, "%s-mgmt-ext" % vm_name, None,
             False, False, None, None, None),
            (VSWITCH_INTERNAL_NAME, "%s-mgmt-int" % vm_name,
             utils.get_random_mac_address(),
             False, False, None, None, None),
            (VSWITCH_DATA_NAME, "%s-data" % vm_name, None,
             False, True, None, DATA_VLAN_RANGE, 0),
            (external_vswitch_name, "%s-ext" % vm_name, None,
             False, True, None, None, None),
            (VSWITCH_INTERNAL_NAME, "%s-pxe" % vm_name,
             utils.get_random_mac_address(),
             True, False, None, None, None),
        ]

        self._virt_driver.create_vm(vm_name, vm_dir, vhd_max_size,
                                    max_mem_mb, min_mem_mb, vcpu_count,
                                    vm_network_config, vfd_path)

        return vm_network_config

    def start_openstack_vm(self, vm_name):
        self._virt_driver.start_vm(vm_name)

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
        Returns a list o f tuples (vnic_name, mac_address, ipv4)
        """
        vnic_ip_info = []
        base_addr = subnet[:-1]
        last_octet = 2
        for vnic_name, mac_address in [(vif_config[1], vif_config[2])
                                       for vif_config in vm_network_config
                                       if vif_config[2]]:
            vnic_ip_info.append((vnic_name, mac_address, base_addr +
                                 str(last_octet)))
            last_octet += 1
        return vnic_ip_info

    def create_kickstart_vfd(self, vfd_path, encrypted_password):
        kickstart.generate_kickstart_vfd(vfd_path,
                                         {"encrypted_password":
                                          encrypted_password})

    def create_vswitches(self, external_vswitch_name, internal_network_config):
        virt_driver = virt_factory.get_virt_driver()

        if not virt_driver.vswitch_exists(external_vswitch_name):
            raise Exception("External switch not found: %s" %
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
