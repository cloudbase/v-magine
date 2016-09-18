# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
# Licensed under the AGPLv3, see LICENCE file for details.

UDP = "UDP"
TCP = "TCP"


class BaseDriver(object):
    def get_host_available_memory(self):
        raise NotImplementedError()

    def vm_exists(self, vm_name):
        raise NotImplementedError()

    def destroy_vm(self, vm_name):
        raise NotImplementedError()

    def create_vm(self, vm_name, vm_path, max_disk_size, max_memory_mb,
                  min_memory_mb, vcpus_num, vmnic_info, vfd_path,
                  iso_path, console_named_pipe):
        raise NotImplementedError()

    def vswitch_exists(self, vswitch_name):
        raise NotImplementedError()

    def create_vswitch(self, vswitch_name, external_port_name=None,
                       create_internal_port=False):
        raise NotImplementedError()

    def add_vswitch_host_firewall_rule(self, vswitch_name, rule_name,
                                       local_ports, protocol=TCP, allow=True,
                                       description=""):
        raise NotImplementedError()

    def set_vswitch_host_ip(self, vswitch_name, host_ip, subnet_mask):
        raise NotImplementedError()

    def get_guest_ip_addresses(self, vm_name):
        raise NotImplementedError()
