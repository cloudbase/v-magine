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

from stackinabox.virt import base
from stackinabox.virt.hyperv import constants
from stackinabox.virt.hyperv import netutilsv2
from stackinabox.virt.hyperv import vhdutilsv2
from stackinabox.virt.hyperv import vmutilsv2
from stackinabox import windows


class HyperVDriver(base.BaseDriver):
    def __init__(self):
        self._vmutils = vmutilsv2.VMUtilsV2()
        self._vhdutils = vhdutilsv2.VHDUtilsV2()
        self._netutils = netutilsv2.NetworkUtilsV2()

    def create_vm(self, vm_name, vm_path, max_disk_size, max_memory_mb,
                  min_memory_mb, vcpus_num, vmnic_info, vfd_path):
        vhd_path = os.path.join(vm_path, "%s.vhdx" % vm_name)

        if self._vmutils.vm_exists(vm_name):
            self._vmutils.destroy_vm(vm_name)

        if os.path.exists(vhd_path):
            os.remove(vhd_path)
        self._vhdutils.create_dynamic_vhd(vhd_path, max_disk_size,
                                          constants.DISK_FORMAT_VHDX)

        memory_ratio = max_memory_mb / float(min_memory_mb)
        self._vmutils.create_vm(vm_name, max_memory_mb, vcpus_num, False,
                                memory_ratio)

        self._vmutils.attach_ide_drive(vm_name, vhd_path, 0, 0)

        if vfd_path:
            self._vmutils.attach_floppy_drive(vm_name, vfd_path, 0, 0)

        for (vmswitch_name, vmnic_name, pxe, allow_mac_spoofing,
             access_vlan_id, trunk_vlan_ids, private_vlan_id) in vmnic_info:
            self._vmutils.create_nic(vm_name, vmnic_name, None, pxe)
            self._netutils.connect_vnic_to_vswitch(vmswitch_name, vmnic_name)
            if allow_mac_spoofing:
                self._netutils.set_vnic_port_security(
                    vmnic_name, allow_mac_spoofing=allow_mac_spoofing)
                if access_vlan_id or trunk_vlan_ids:
                    self._netutils.set_vswitch_port_vlan_id(
                        access_vlan_id, vmnic_name, trunk_vlan_ids,
                        private_vlan_id)

    def vswitch_exists(self, vswitch_name):
        raise NotImplementedError()

    def create_vswitch(self, vswitch_name, vswitch_type=base.VSWITCH_PRIVATE):
        raise NotImplementedError()

    def add_vswitch_host_firewall_rule(self, vswitch_name, rule_name,
                                       local_ports, protocol=base.TCP,
                                       allow=True, description=''):
        protocol_map = {base.TCP: windows.PROTOCOL_TCP,
                        base.UDP: windows.PROTOCOL_UDP}
        interface_name = "vEthernet (%s)" % vswitch_name

        windows_utils = windows.WindowsUtils()
        if windows_utils.firewall_rule_exists(rule_name):
            windows_utils.firewall_remove_rule(rule_name)

        windows_utils.firewall_create_rule(rule_name, local_ports,
                                           protocol_map[protocol],
                                           [interface_name],
                                           allow, description)
