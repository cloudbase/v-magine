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

import logging
import os

from stackinabox.virt import base
from stackinabox.virt.hyperv import constants
from stackinabox.virt.hyperv import hostutilsv2
from stackinabox.virt.hyperv import netutilsv2
from stackinabox.virt.hyperv import vhdutilsv2
from stackinabox.virt.hyperv import vmutils
from stackinabox.virt.hyperv import vmutilsv2
from stackinabox import windows

LOG = logging.getLogger(__name__)


class HyperVDriver(base.BaseDriver):
    HOST_MEMORY_BUFFER_MB = 100

    def __init__(self):
        LOG.debug("Initializing HyperVDriver")

        self._vmutils = vmutilsv2.VMUtilsV2()
        self._vhdutils = vhdutilsv2.VHDUtilsV2()
        self._netutils = netutilsv2.NetworkUtilsV2()
        self._hostutils = hostutilsv2.HostUtilsV2()
        self._windows_utils = windows.WindowsUtils()

    def vm_exists(self, vm_name):
        return self._vmutils.vm_exists(vm_name)

    def get_host_available_memory(self):
        host_avail_mem_mb = self._hostutils.get_host_available_memory_mb()
        return max(host_avail_mem_mb - self.HOST_MEMORY_BUFFER_MB,
                   0) * 1024 * 1024

    def get_vm_memory_usage(self, vm_name):
        return (self._vmutils.get_vm_summary_info(
            vm_name).get('MemoryUsage') or 0) * 1024 * 1024

    def vm_is_stopped(self, vm_name):
        return (self._vmutils.get_vm_state(vm_name) ==
                constants.HYPERV_VM_STATE_DISABLED)

    def reboot_vm(self, vm_name):
        self._vmutils.set_vm_state(vm_name, constants.HYPERV_VM_STATE_REBOOT)

    def power_off_vm(self, vm_name):
        self._vmutils.set_vm_state(vm_name, constants.HYPERV_VM_STATE_DISABLED)

    def destroy_vm(self, vm_name):
        self.power_off_vm(vm_name)
        self._vmutils.destroy_vm(vm_name)

    def create_vm(self, vm_name, vm_path, max_disk_size, max_memory_mb,
                  min_memory_mb, vcpus_num, vmnic_info, vfd_path, iso_path,
                  console_named_pipe):
        vhd_path = os.path.join(vm_path, "%s.vhdx" % vm_name)

        if os.path.exists(vhd_path):
            os.remove(vhd_path)
        self._vhdutils.create_dynamic_vhd(vhd_path, max_disk_size,
                                          constants.DISK_FORMAT_VHDX)

        # Hyper-V requires memory to be 2MB aligned
        max_memory_mb -= max_memory_mb % 2

        # memory_ratio = max_memory_mb / float(min_memory_mb)
        memory_ratio = 1
        self._vmutils.create_vm(vm_name, max_memory_mb, vcpus_num, False,
                                memory_ratio)

        self._vmutils.attach_ide_drive(vm_name, vhd_path, 0, 0)

        if vfd_path:
            self._vmutils.attach_floppy_drive(vm_name, vfd_path, 0, 0)

        if iso_path:
            self._vmutils.attach_ide_drive(vm_name, iso_path, 0, 1,
                                           constants.IDE_DVD)

        for (vmswitch_name, vmnic_name, mac_address, pxe, allow_mac_spoofing,
             access_vlan_id, trunk_vlan_ids, private_vlan_id) in vmnic_info:
            self._vmutils.create_nic(vm_name, vmnic_name, mac_address, pxe)
            self._netutils.connect_vnic_to_vswitch(vmswitch_name, vmnic_name)
            if allow_mac_spoofing:
                self._netutils.set_vnic_port_security(
                    vmnic_name, allow_mac_spoofing=allow_mac_spoofing)
                if access_vlan_id or trunk_vlan_ids:
                    self._netutils.set_vswitch_port_vlan_id(
                        access_vlan_id, vmnic_name, trunk_vlan_ids,
                        private_vlan_id)

        if console_named_pipe:
            self._vmutils.set_vm_serial_port_connection(vm_name,
                                                        console_named_pipe)

    def start_vm(self, vm_name):
        self._vmutils.set_vm_state(vm_name, constants.HYPERV_VM_STATE_ENABLED)

    def get_vswitches(self):
        return self._netutils.get_vswitches()

    def get_host_nics(self):
        return self._netutils.get_external_ports()

    def vswitch_exists(self, vswitch_name):
        return self._netutils.vswitch_exists(vswitch_name)

    def create_vswitch(self, vswitch_name, external_port_name=None,
                       create_internal_port=False):
        LOG.debug('create_vswitch called. %s' % vswitch_name)
        self._netutils.create_vswitch(vswitch_name, external_port_name,
                                      create_internal_port)

    def set_vswitch_host_ip(self, vswitch_name, host_ip, subnet_mask):
        self._netutils.set_host_nic_ip_address(
            "vEthernet (%s)" % vswitch_name,
            ip_list=[host_ip],
            netmask_list=[subnet_mask])

    def add_vswitch_host_firewall_rule(self, vswitch_name, rule_name,
                                       local_ports, protocol=base.TCP,
                                       allow=True, description=''):
        protocol_map = {base.TCP: windows.PROTOCOL_TCP,
                        base.UDP: windows.PROTOCOL_UDP}
        interface_name = "vEthernet (%s)" % vswitch_name

        if self._windows_utils.firewall_rule_exists(rule_name):
            self._windows_utils.firewall_remove_rule(rule_name)

        self._windows_utils.firewall_create_rule(rule_name, local_ports,
                                                 protocol_map[protocol],
                                                 [interface_name],
                                                 allow, description)

    def check_platform(self):
        VLAN_HOTFIX_ID = '2982439'
        OCT14_RLP_HOTFIX_ID = '2995388'

        if not self._windows_utils.check_os_version(
                6, 2, comparison=windows.VER_GREATER_EQUAL):
            raise Exception("Windows 8 or Windows Server / Hyper Server 2012 "
                            "or above are required for this product")

        try:
            # TODO: check if the feature is installed
            self._vmutils.list_instances()
        except Exception as ex:
            LOG.exception(ex)
            raise Exception("Please enable Hyper-V on this host before "
                            "installing OpenStack")

        if (self._windows_utils.check_os_version(6, 3) and
                not (self._windows_utils.check_hotfix(VLAN_HOTFIX_ID) or
                     self._windows_utils.check_hotfix(OCT14_RLP_HOTFIX_ID))):
            raise Exception(
                "Windows update KB%(hotfix_id)s needs to be installed for "
                "OpenStack to work properly on this host. Please see: "
                "http://support.microsoft.com/?kbid=%(hotfix_id)s" %
                {"hotfix_id": VLAN_HOTFIX_ID})

    def get_guest_ip_addresses(self, vm_name):
        guest_info = self._vmutils.get_guest_info(vm_name)
        ipv4_addresses = None
        ipv6_addresses = None
        if guest_info:
            ipv4_addresses = guest_info.get("NetworkAddressIPv4").split(";")
            ipv6_addresses = guest_info.get("NetworkAddressIPv6").split(";")
        return (ipv4_addresses, ipv6_addresses)
