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

import ctypes
import logging
import win32api
import win32con
import wmi

from ctypes import windll
from ctypes import wintypes
from win32com import client

from stackinabox import utils
from stackinabox.virt.hyperv import vmutils

kernel32 = windll.kernel32

LOG = logging

class Win32_OSVERSIONINFOEX_W(ctypes.Structure):
    _fields_ = [
        ('dwOSVersionInfoSize', wintypes.DWORD),
        ('dwMajorVersion', wintypes.DWORD),
        ('dwMinorVersion', wintypes.DWORD),
        ('dwBuildNumber', wintypes.DWORD),
        ('dwPlatformId', wintypes.DWORD),
        ('szCSDVersion', wintypes.WCHAR * 128),
        ('wServicePackMajor', wintypes.WORD),
        ('wServicePackMinor', wintypes.WORD),
        ('wSuiteMask', wintypes.WORD),
        ('wProductType', wintypes.BYTE),
        ('wReserved', wintypes.BYTE)
    ]

kernel32.VerifyVersionInfoW.argtypes = [
    ctypes.POINTER(Win32_OSVERSIONINFOEX_W),
    wintypes.DWORD, wintypes.ULARGE_INTEGER]
kernel32.VerifyVersionInfoW.restype = wintypes.BOOL

kernel32.VerSetConditionMask.argtypes = [wintypes.ULARGE_INTEGER,
                                         wintypes.DWORD,
                                         wintypes.BYTE]
kernel32.VerSetConditionMask.restype = wintypes.ULARGE_INTEGER

VER_MAJORVERSION = 1
VER_MINORVERSION = 2
VER_BUILDNUMBER = 4
VER_PLATFORMID = 0x8
VER_SERVICEPACKMINOR = 0x10
VER_SERVICEPACKMAJOR = 0x20
VER_SUITENAME = 0x40
VER_PRODUCT_TYPE = 0x80

VER_EQUAL = 1
VER_GREATER = 2
VER_GREATER_EQUAL = 3
VER_LESS = 4
VER_LESS_EQUAL = 5
VER_AND = 6
VER_OR = 7

VER_NT_DOMAIN_CONTROLLER = 2
VER_NT_SERVER = 3
VER_NT_WORKSTATION = 1

ERROR_OLD_WIN_VERSION = 1150

PROTOCOL_TCP = "TCP"
PROTOCOL_UDP = "UDP"


class WindowsUtils(object):
    _FW_IP_PROTOCOL_TCP = 6
    _FW_IP_PROTOCOL_UDP = 17
    _FW_SCOPE_ALL = 0
    _FW_SCOPE_LOCAL_SUBNET = 1

    _NET_FW_ACTION_BLOCK = 0
    _NET_FW_ACTION_ALLOW = 1

    def __init__(self):
        self._wmi_conn_cimv2 = None

    @property
    def _conn_cimv2(self):
        if self._wmi_conn_cimv2 is None:
            self._wmi_conn_cimv2 = wmi.WMI(moniker='//./root/cimv2')
        return self._wmi_conn_cimv2

    def check_hotfix(self, hotfix_id):
        hotfix_id_list = self._conn_cimv2.Win32_QuickFixEngineering(
            HotFixID='KB%s' % hotfix_id)
        if hotfix_id_list:
            return hotfix_id_list[0].InstalledOn

    def get_installed_products(self, vendor):
        products=[]
        for p in self._conn_cimv2.Win32_Product(vendor=vendor):
            products.append((p.IdentifyingNumber, p.Caption))
        return products

    def uninstall_product(self, product_id, log_path, hidden=False):
        if hidden:
            ui = "/qn"
        else:
            ui = "/qb"
        utils.execute_process(["msiexec.exe", "/uninstall", product_id, ui,
                               "/l*v", log_path])

    def install_msi(self, msi_path, features, properties, log_path,
                    hidden=False):
        if hidden:
            ui = "/qn"
        else:
            ui = "/qb"

        args = ["msiexec.exe", "/i", msi_path, ui, "/l*v", log_path]

        if features:
            args.append("ADDLOCAL=%s" % ",".join(features))

        if properties:
            for (k, v) in properties.items():
                args.append("%(k)s=%(v)s" % {"k": k, "v": v})

        LOG.debug("Installing MSI: %s" % args)
        utils.execute_process(args)

    def check_os_version(self, major=None, minor=None, product_type=None,
                         comparison=VER_EQUAL):
        vi = Win32_OSVERSIONINFOEX_W()
        vi.dwOSVersionInfoSize = ctypes.sizeof(Win32_OSVERSIONINFOEX_W)

        type_masks = []
        if major is not None:
            vi.dwMajorVersion = major
            type_masks.append(VER_MAJORVERSION)

        if major is not None:
            vi.dwMinorVersion = minor
            type_masks.append(VER_MINORVERSION)

        if product_type is not None:
            vi.wProductType = product_type
            type_masks.append(VER_PRODUCT_TYPE)

        mask = 0
        type_mask_or = 0
        for type_mask in type_masks:
            mask = kernel32.VerSetConditionMask(mask, type_mask,
                                                comparison)
            type_mask_or |= type_mask

        ret_val = kernel32.VerifyVersionInfoW(ctypes.byref(vi), type_mask_or,
                                              mask)
        if ret_val:
            return True
        else:
            err = kernel32.GetLastError()
            if err == ERROR_OLD_WIN_VERSION:
                return False
            else:
                raise vmutils.HyperVException(
                    "VerifyVersionInfo failed with error: %s" % err)

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
        # fw_rule.Profiles = fw_policy2.CurrentProfileTypes
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


def kill_process(pid):
    hProc = None
    try:
        hProc = win32api.OpenProcess(win32con.PROCESS_TERMINATE, 0, pid)
        if hProc:
            win32api.TerminateProcess(hProc, 0)
    finally:
        if hProc:
            hProc.Close()
