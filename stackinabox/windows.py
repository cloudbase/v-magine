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

from win32com import client

PROTOCOL_TCP = "TCP"
PROTOCOL_UDP = "UDP"


class WindowsUtils(object):
    _FW_IP_PROTOCOL_TCP = 6
    _FW_IP_PROTOCOL_UDP = 17
    _FW_SCOPE_ALL = 0
    _FW_SCOPE_LOCAL_SUBNET = 1

    _NET_FW_ACTION_BLOCK = 0
    _NET_FW_ACTION_ALLOW = 1

    def firewall_create_rule(self, rule_name, local_ports, protocol,
                             interface_names, allow=True, description="",
                             grouping=""):

        protocol_map = {PROTOCOL_TCP: self._FW_IP_PROTOCOL_TCP,
                        PROTOCOL_UDP: self._FW_IP_PROTOCOL_UDP}
        action_map = {True: self._NET_FW_ACTION_ALLOW,
                      False: self._NET_FW_ACTION_BLOCK}

        fw_policy2 = client.Dispatch("HNetCfg.FwPolicy2")
        fw_rule = client.Dispatch("HNetCfg.FwRule")

        fw_rule.Name = rule_name
        fw_rule.Description = description
        fw_rule.Protocol = protocol_map[protocol]
        fw_rule.LocalPorts = local_ports
        fw_rule.Interfaces = interface_names
        fw_rule.Grouping = grouping
        fw_rule.Action = action_map[allow]
        #fw_rule.Profiles = fw_policy2.CurrentProfileTypes
        fw_rule.Enabled = True

        fw_policy2.Rules.Add(fw_rule)

    def firewall_rule_exists(self, rule_name):
        fw_policy2 = client.Dispatch("HNetCfg.FwPolicy2")
        for fw_rule in fw_policy2.Rules:
            if fw_rule.Name == rule_name:
                return True
        return False

    def firewall_remove_rule(self, rule_name):
        fw_policy2 = client.Dispatch("HNetCfg.FwPolicy2")
        fw_policy2.Rules.Remove(rule_name)
