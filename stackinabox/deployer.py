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

from oslo.utils import units

from stackinabox import actions
from stackinabox import security


class DeploymentManager(object):

    def deploy(self):
        vm_dir = "C:\\VM"
        external_vswitch_name = "external"
        vm_name = "openstack-controller"
        max_vm_mem_mb = None
        pxe_os_id = "centos7"

        password = security.get_random_password()
        encrypted_password = security.get_password_md5(password)

        if not os.path.isdir(vm_dir):
            os.makedirs(vm_dir)

        dep_actions = actions.DeploymentActions()

        dep_actions.check_remove_openstack_vm(vm_name)

        vfd_path = os.path.join(vm_dir, "floppy.vfd")
        dep_actions.create_kickstart_vfd(vfd_path, encrypted_password)

        internal_network_config = dep_actions.get_internal_network_config()
        dep_actions.create_vswitches(external_vswitch_name,
                                     internal_network_config)

        vm_network_config = dep_actions.create_openstack_vm(
            vm_name, vm_dir, max_vm_mem_mb, vfd_path, external_vswitch_name)

        vnic_ip_info = dep_actions.get_openstack_vm_ip_info(
            vm_network_config, internal_network_config["subnet"])

        dep_actions.start_pxe_service(
            internal_network_config["host_ip"],
            [vnic_ip[1:] for vnic_ip in vnic_ip_info], pxe_os_id)

        dep_actions.start_openstack_vm(vm_name)
