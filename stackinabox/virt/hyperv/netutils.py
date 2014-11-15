# Copyright 2013 Cloudbase Solutions SRL
# Copyright 2013 Pedro Navarro Perez
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
import sys
import time
import wmi

from stackinabox.i18n import _
from stackinabox.virt.hyperv import vmutils

LOG = logging.getLogger(__name__)

WMI_JOB_STATE_STARTED = 4096
WMI_JOB_STATE_RUNNING = 4
WMI_JOB_STATE_COMPLETED = 7


class NetworkUtils(object):

    _ETHERNET_SWITCH_PORT = 'Msvm_SwitchPort'

    _wmi_namespace = '//./root/virtualization'
    _wmi_cimv2_namespace = '//./root/cimv2'

    def __init__(self):
        self._wmi_conn = None
        self._wmi_conn_cimv2 = None

    @property
    def _conn(self):
        if self._wmi_conn is None:
            self._wmi_conn = wmi.WMI(moniker=self._wmi_namespace)
        return self._wmi_conn

    @property
    def _conn_cimv2(self):
        if self._wmi_conn_cimv2 is None:
            self._wmi_conn_cimv2 = wmi.WMI(moniker=self._wmi_cimv2_namespace)
        return self._wmi_conn_cimv2

    def set_host_nic_ip_address(self, nic_name, dhcp=False, ip_list=None,
                                netmask_list=None, gateway_list=None,
                                gateway_metrics_list=None):
        net_adapter_list = self._conn_cimv2.Win32_NetworkAdapter(
            NetConnectionID=nic_name)
        if not net_adapter_list:
            raise vmutils.HyperVException(_('Nic not found: %s') %
                                          nic_name)
        net_adapter = net_adapter_list[0]
        net_adapter_config = net_adapter.associators(
            wmi_result_class='Win32_NetworkAdapterConfiguration')[0]

        if dhcp:
            (ret_val,) = net_adapter_config.EnableDHCP()
            if ret_val not in [0, 1]:
                raise vmutils.HyperVException(
                    _('Enabling DHCP failed with error: %s') % ret_val)
        else:
            (ret_val,) = net_adapter_config.EnableStatic(
                IPAddress=ip_list,
                SubnetMask=netmask_list)
            if ret_val not in [0, 1]:
                raise vmutils.HyperVException(
                    _('Setting static IP addresses %(ip_list)s with netmasks '
                      '%(netmask_list)s on interface %(nic_name)s failed with '
                      'error: %(ret_val)s') %
                    {'ip_list': ip_list, 'nic_name': nic_name,
                     'netmask_list': netmask_list, 'ret_val': ret_val})

            if gateway_list:
                (ret_val,) = net_adapter_config.EnableGateways(
                    DefaultIPGateway=gateway_list,
                    GatewayCostMetric=netmask_list)
                if ret_val not in [0, 1]:
                    raise vmutils.HyperVException(
                        _('Setting a gateway failed with error: %s') %
                        ret_val)

    def get_switch_ports(self, vswitch_name):
        vswitch = self._get_vswitch(vswitch_name)
        vswitch_ports = vswitch.associators(
            wmi_result_class=self._ETHERNET_SWITCH_PORT)
        return set(p.Name for p in vswitch_ports)

    def vnic_port_exists(self, port_id):
        try:
            self._get_vnic_settings(port_id)
        except Exception:
            return False
        return True

    def get_vnic_ids(self):
        return set(
            p.ElementName
            for p in self._conn.Msvm_SyntheticEthernetPortSettingData() +
            self._conn.Msvm_EmulatedEthernetPortSettingData()
            if p.ElementName is not None)

    def _get_vnic_settings(self, vnic_name):
        vnic_settings = self._conn.Msvm_SyntheticEthernetPortSettingData(
            ElementName=vnic_name)
        vnic_settings += self._conn.Msvm_EmulatedEthernetPortSettingData(
            ElementName=vnic_name)

        if not vnic_settings:
            raise vmutils.HyperVException(_('Vnic not found: %s') %
                                          vnic_name)
        if len(vnic_settings) > 1:
            raise vmutils.HyperVException(_('Multiple vnics found with name: '
                                            '%s') % vnic_name)
        return vnic_settings[0]

    def connect_vnic_to_vswitch(self, vswitch_name, switch_port_name):
        vnic_settings = self._get_vnic_settings(switch_port_name)
        if not vnic_settings.Connection or not vnic_settings.Connection[0]:
            port = self.get_port_by_id(switch_port_name, vswitch_name)
            if port:
                port_path = port.Path_()
            else:
                port_path = self._create_switch_port(
                    vswitch_name, switch_port_name)
            vnic_settings.Connection = [port_path]
            self._modify_virt_resource(vnic_settings)

    def _get_vm_from_res_setting_data(self, res_setting_data):
        sd = res_setting_data.associators(
            wmi_result_class='Msvm_VirtualSystemSettingData')
        vm = sd[0].associators(
            wmi_result_class='Msvm_ComputerSystem')
        return vm[0]

    def _modify_virt_resource(self, res_setting_data):
        vm = self._get_vm_from_res_setting_data(res_setting_data)

        vs_man_svc = self._conn.Msvm_VirtualSystemManagementService()[0]
        (job_path, ret_val) = vs_man_svc.ModifyVirtualSystemResources(
            vm.Path_(), [res_setting_data.GetText_(1)])
        self._check_job_status(ret_val, job_path)

    def _check_job_status(self, ret_val, jobpath):
        """Poll WMI job state for completion."""
        if not ret_val:
            return
        elif ret_val not in [WMI_JOB_STATE_STARTED, WMI_JOB_STATE_RUNNING]:
            raise vmutils.HyperVException(_('Job failed with error %d') %
                                          ret_val)

        job_wmi_path = jobpath.replace('\\', '/')
        job = wmi.WMI(moniker=job_wmi_path)

        while job.JobState == WMI_JOB_STATE_RUNNING:
            time.sleep(0.1)
            job = wmi.WMI(moniker=job_wmi_path)
        if job.JobState != WMI_JOB_STATE_COMPLETED:
            job_state = job.JobState
            if job.path().Class == "Msvm_ConcreteJob":
                err_sum_desc = job.ErrorSummaryDescription
                err_desc = job.ErrorDescription
                err_code = job.ErrorCode
                data = {'job_state': job_state,
                        'err_sum_desc': err_sum_desc,
                        'err_desc': err_desc,
                        'err_code': err_code}
                raise vmutils.HyperVException(
                    _("WMI job failed with status %(job_state)d. "
                      "Error details: %(err_sum_desc)s - %(err_desc)s - "
                      "Error code: %(err_code)d") % data)
            else:
                (error, ret_val) = job.GetError()
                if not ret_val and error:
                    data = {'job_state': job_state,
                            'error': error}
                    raise vmutils.HyperVException(
                        _("WMI job failed with status %(job_state)d. "
                          "Error details: %(error)s") % data)
                else:
                    raise vmutils.HyperVException(
                        _("WMI job failed with status %d. "
                          "No error description available") % job_state)

        desc = job.Description
        elap = job.ElapsedTime
        LOG.debug(_("WMI job succeeded: %(desc)s, Elapsed=%(elap)s"),
                  {'desc': desc, 'elap': elap})

    def _create_switch_port(self, vswitch_name, switch_port_name):
        """Creates a switch port."""
        switch_svc = self._conn.Msvm_VirtualSwitchManagementService()[0]
        vswitch_path = self._get_vswitch(vswitch_name).path_()
        (new_port, ret_val) = switch_svc.CreateSwitchPort(
            Name=switch_port_name,
            FriendlyName=switch_port_name,
            ScopeOfResidence="",
            VirtualSwitch=vswitch_path)
        if ret_val != 0:
            raise vmutils.HyperVException(
                _('Failed creating port for %s') % vswitch_name)
        return new_port

    def remove_all_security_rules(self, switch_port_name):
        pass

    def disconnect_switch_port(
            self, vswitch_name, switch_port_name, delete_port):
        """Disconnects the switch port."""
        switch_svc = self._conn.Msvm_VirtualSwitchManagementService()[0]
        switch_port_path = self._get_switch_port_path_by_name(
            switch_port_name)
        if not switch_port_path:
            # Port not found. It happens when the VM was already deleted.
            return

        (ret_val, ) = switch_svc.DisconnectSwitchPort(
            SwitchPort=switch_port_path)
        if ret_val != 0:
            data = {'switch_port_name': switch_port_name,
                    'vswitch_name': vswitch_name,
                    'ret_val': ret_val}
            raise vmutils.HyperVException(
                _('Failed to disconnect port %(switch_port_name)s '
                  'from switch %(vswitch_name)s '
                  'with error %(ret_val)s') % data)
        if delete_port:
            (ret_val, ) = switch_svc.DeleteSwitchPort(
                SwitchPort=switch_port_path)
            if ret_val != 0:
                data = {'switch_port_name': switch_port_name,
                        'vswitch_name': vswitch_name,
                        'ret_val': ret_val}
                raise vmutils.HyperVException(
                    _('Failed to delete port %(switch_port_name)s '
                      'from switch %(vswitch_name)s '
                      'with error %(ret_val)s') % data)

    def get_vswitches(self):
        raise NotImplementedError()

    def _get_vswitch(self, vswitch_name):
        vswitch = self._conn.Msvm_VirtualSwitch(ElementName=vswitch_name)
        if not vswitch:
            raise vmutils.HyperVException(_('VSwitch not found: %s') %
                                          vswitch_name)
        return vswitch[0]

    def vswitch_exists(self, vswitch_name):
        try:
            self._get_vswitch(vswitch_name)
            return True
        except vmutils.HyperVException as e:
            return False

    def create_vswitch(self, vswitch_name, external_port_name=None,
                       create_internal_port=False):
        raise NotImplementedError()

    def remove_vswitch(self, vswitch_name):
        raise NotImplementedError()

    def _get_vswitch_external_port(self, vswitch):
        vswitch_ports = vswitch.associators(
            wmi_result_class=self._ETHERNET_SWITCH_PORT)
        for vswitch_port in vswitch_ports:
            lan_endpoints = vswitch_port.associators(
                wmi_result_class='Msvm_SwitchLanEndpoint')
            if lan_endpoints:
                ext_port = lan_endpoints[0].associators(
                    wmi_result_class='Msvm_ExternalEthernetPort')
                if ext_port:
                    return vswitch_port

    def set_vnic_port_security(self, switch_port_name,
                               allow_mac_spoofing=False,
                               enable_dhcp_guard=False,
                               enable_router_guard=False,
                               allow_ieee_priority_tag=False,
                               allow_teaming=False,
                               monitor_mode=0):
        raise NotImplementedError()

    def set_vswitch_port_vlan_id(self, vlan_id, switch_port_name,
                                 trunk_vlan_ids=None, native_vlan_id=0):
        vlan_endpoint_settings = self._conn.Msvm_VLANEndpointSettingData(
            ElementName=switch_port_name)[0]

        if trunk_vlan_ids:
            raise NotImplementedError()

        if vlan_endpoint_settings.AccessVLAN != vlan_id:
            vlan_endpoint_settings.AccessVLAN = vlan_id
            vlan_endpoint_settings.put()

    def _get_switch_port_path_by_name(self, switch_port_name):
        vswitch = self._conn.Msvm_SwitchPort(ElementName=switch_port_name)
        if vswitch:
            return vswitch[0].path_()

    def get_vswitch_id(self, vswitch_name):
        vswitch = self._get_vswitch(vswitch_name)
        return vswitch.Name

    def get_port_by_id(self, port_id, vswitch_name):
        vswitch = self._get_vswitch(vswitch_name)
        switch_ports = vswitch.associators(
            wmi_result_class=self._ETHERNET_SWITCH_PORT)
        for switch_port in switch_ports:
            if (switch_port.ElementName == port_id):
                return switch_port

    def enable_port_metrics_collection(self, switch_port_name):
        raise NotImplementedError(_("Metrics collection is not supported on "
                                    "this version of Hyper-V"))

    def enable_control_metrics(self, switch_port_name):
        raise NotImplementedError(_("Metrics collection is not supported on "
                                    "this version of Hyper-V"))

    def can_enable_control_metrics(self, switch_port_name):
        return False
