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
import os
import pywintypes
import win32api
import win32con
import win32process
import win32security
import wmi

from ctypes import windll
from ctypes import wintypes
from win32com import client

from stackinabox import utils
from stackinabox.virt.hyperv import vmutils

kernel32 = windll.kernel32
advapi32 = windll.Advapi32

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


class Win32_STARTUPINFO_W(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('lpReserved', wintypes.LPWSTR),
        ('lpDesktop', wintypes.LPWSTR),
        ('lpTitle', wintypes.LPWSTR),
        ('dwX', wintypes.DWORD),
        ('dwY', wintypes.DWORD),
        ('dwXSize', wintypes.DWORD),
        ('dwYSize', wintypes.DWORD),
        ('dwXCountChars', wintypes.DWORD),
        ('dwYCountChars', wintypes.DWORD),
        ('dwFillAttribute', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('wShowWindow', wintypes.WORD),
        ('cbReserved2', wintypes.WORD),
        ('lpReserved2', ctypes.POINTER(wintypes.BYTE)),
        ('hStdInput', wintypes.HANDLE),
        ('hStdOutput', wintypes.HANDLE),
        ('hStdError', wintypes.HANDLE),
    ]


class Win32_PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('hProcess', wintypes.HANDLE),
        ('hThread', wintypes.HANDLE),
        ('dwProcessId', wintypes.DWORD),
        ('dwThreadId', wintypes.DWORD),
    ]


kernel32.VerifyVersionInfoW.argtypes = [
    ctypes.POINTER(Win32_OSVERSIONINFOEX_W),
    wintypes.DWORD, wintypes.ULARGE_INTEGER]
kernel32.VerifyVersionInfoW.restype = wintypes.BOOL

kernel32.VerSetConditionMask.argtypes = [wintypes.ULARGE_INTEGER,
                                         wintypes.DWORD,
                                         wintypes.BYTE]
kernel32.VerSetConditionMask.restype = wintypes.ULARGE_INTEGER

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD

advapi32.SaferCreateLevel.argtypes = [wintypes.DWORD,
                                      wintypes.DWORD,
                                      wintypes.DWORD,
                                      ctypes.POINTER(wintypes.HANDLE),
                                      ctypes.c_void_p]
advapi32.SaferCreateLevel.restype = wintypes.BOOL

advapi32.SaferCloseLevel.argtypes = [wintypes.HANDLE]
advapi32.SaferCloseLevel.restype = wintypes.BOOL

advapi32.SaferComputeTokenFromLevel.argtypes = [wintypes.HANDLE,
                                                wintypes.HANDLE,
                                                ctypes.POINTER(
                                                    wintypes.HANDLE),
                                                wintypes.DWORD,
                                                ctypes.c_void_p]
advapi32.SaferComputeTokenFromLevel.restype = wintypes.BOOL

advapi32.CreateProcessWithTokenW.argtypes = [wintypes.HANDLE,
                                             wintypes.DWORD,
                                             wintypes.LPCWSTR,
                                             wintypes.LPWSTR,
                                             wintypes.DWORD,
                                             ctypes.c_void_p,
                                             wintypes.LPCWSTR,
                                             ctypes.POINTER(
                                                 Win32_STARTUPINFO_W),
                                             ctypes.POINTER(
                                                 Win32_PROCESS_INFORMATION)]
advapi32.CreateProcessWithTokenW.restype = wintypes.BOOL

advapi32.CreateProcessAsUserW.argtypes = [wintypes.HANDLE,
                                          wintypes.LPCWSTR,
                                          wintypes.LPWSTR,
                                          ctypes.c_void_p,
                                          ctypes.c_void_p,
                                          wintypes.BOOL,
                                          wintypes.DWORD,
                                          ctypes.c_void_p,
                                          wintypes.LPCWSTR,
                                          ctypes.POINTER(
                                              Win32_STARTUPINFO_W),
                                          ctypes.POINTER(
                                              Win32_PROCESS_INFORMATION)]
advapi32.CreateProcessAsUserW.restype = wintypes.BOOL

ERROR_OLD_WIN_VERSION = 1150

PROTOCOL_TCP = "TCP"
PROTOCOL_UDP = "UDP"

SW_SHOWNORMAL = 1

SAFER_SCOPEID_USER = 2
SAFER_LEVELID_NORMALUSER = 0x20000
SAFER_LEVELID_CONSTRAINED = 0x10000
SAFER_LEVELID_UNTRUSTED = 0x1000
SAFER_LEVEL_OPEN = 1

INFINITE = 0xFFFFFFFF

CREATE_NEW_CONSOLE = 0x10


class LogonFailedException(Exception):
    pass


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
        # if self._wmi_conn_cimv2 is None:
        self._wmi_conn_cimv2 = wmi.WMI(moniker='//./root/cimv2')
        return self._wmi_conn_cimv2

    def check_hotfix(self, hotfix_id):
        hotfix_id_list = self._conn_cimv2.Win32_QuickFixEngineering(
            HotFixID='KB%s' % hotfix_id)
        if hotfix_id_list:
            return hotfix_id_list[0].InstalledOn

    def get_installed_products(self, vendor):
        products = []
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

    def check_os_version(self, major, minor):
        os_version_str = self._conn_cimv2.Win32_OperatingSystem()[0].Version
        os_version = map(int, os_version_str.split("."))
        return os_version >= [major, minor]

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

    def run_safe_process(self, filename, arguments=None, wait=False,
                         new_console=False):
        safer_level_handle = wintypes.HANDLE()
        ret_val = advapi32.SaferCreateLevel(SAFER_SCOPEID_USER,
                                            SAFER_LEVELID_NORMALUSER,
                                            SAFER_LEVEL_OPEN,
                                            ctypes.byref(safer_level_handle),
                                            None)
        if not ret_val:
            raise Exception("SaferCreateLevel failed")

        token = wintypes.HANDLE()

        try:
            ret_val = advapi32.SaferComputeTokenFromLevel(
                safer_level_handle, None, ctypes.byref(token), 0, None)
            if not ret_val:
                raise Exception("SaferComputeTokenFromLevel failed")

            proc_info = Win32_PROCESS_INFORMATION()
            startup_info = Win32_STARTUPINFO_W()
            startup_info.cb = ctypes.sizeof(Win32_STARTUPINFO_W)
            startup_info.lpDesktop = ""

            flags = 0
            if new_console:
                flags = CREATE_NEW_CONSOLE

            cmdline = ctypes.create_unicode_buffer(
                '"%s" ' % filename + arguments)

            ret_val = advapi32.CreateProcessAsUserW(
                token, None, cmdline, None, None, False, flags, None, None,
                ctypes.byref(startup_info), ctypes.byref(proc_info))
            if not ret_val:
                raise Exception("CreateProcessAsUserW failed")

            if wait and proc_info.hProcess:
                kernel32.WaitForSingleObject(proc_info.hProcess, INFINITE)

            if proc_info.hProcess:
                kernel32.CloseHandle(proc_info.hProcess)
            if proc_info.hThread:
                kernel32.CloseHandle(proc_info.hThread)
        finally:
            if token:
                kernel32.CloseHandle(token)
            advapi32.SaferCloseLevel(safer_level_handle)

    def open_url(self, url):
        try:
            win32api.ShellExecute(None, 'open', url, None, None, SW_SHOWNORMAL)
            return True
        except pywintypes.error as ex:
            if ex.winerror == 2:
                return False
            else:
                raise

    def check_sysnative_dir_exists(self):
        sysnative_dir_exists = os.path.isdir(self.get_sysnative_dir())
        if not sysnative_dir_exists and self.is_wow64():
            LOG.warning('Unable to validate sysnative folder presence. '
                        'If Target OS is Server 2003 x64, please ensure '
                        'you have KB942589 installed')
        return sysnative_dir_exists

    def is_wow64(self):
        return win32process.IsWow64Process()

    def get_system32_dir(self):
        return os.path.expandvars('%windir%\\system32')

    def get_sysnative_dir(self):
        return os.path.expandvars('%windir%\\sysnative')

    def _get_system_dir(self, sysnative=True):
        if sysnative and self.check_sysnative_dir_exists():
            return self.get_sysnative_dir()
        else:
            return self.get_system32_dir()

    def execute_powershell(self, args="", sysnative=True):
        base_dir = self._get_system_dir(sysnative)
        powershell_path = os.path.join(base_dir,
                                       'WindowsPowerShell\\v1.0\\'
                                       'powershell.exe')

        return self.run_safe_process(
            powershell_path,
            '-ExecutionPolicy RemoteSigned -NoExit -Command %s' % args,
            new_console=True)

    def create_user_logon_session(self, username, password, domain='.'):
        token = wintypes.HANDLE()
        ret_val = advapi32.LogonUserW(unicode(username),
                                      unicode(domain),
                                      unicode(password), 2, 0,
                                      ctypes.byref(token))
        if not ret_val:
            raise LogonFailedException()
        return token

    def close_user_logon_session(self, token):
        kernel32.CloseHandle(token)

    def get_current_user(self):
        proc_token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(), win32security.TOKEN_QUERY)

        sid, tmp = win32security.GetTokenInformation(
            proc_token, win32security.TokenUser)

        username, domain, user_type = win32security.LookupAccountSid(None, sid)

        return domain, username

    def get_file_version(self, path):
        info = win32api.GetFileVersionInfo(path, '\\')
        ms = info['FileVersionMS']
        ls = info['FileVersionLS']
        return (win32api.HIWORD(ms), win32api.LOWORD(ms),
                win32api.HIWORD(ls), win32api.LOWORD(ls))

    def get_windows_version_info(self):
        version_info = self._conn_cimv2.Win32_OperatingSystem()[0]
        return {"description": version_info.Caption,
                "version": version_info.Version}


def kill_process(pid):
    hProc = None
    try:
        hProc = win32api.OpenProcess(win32con.PROCESS_TERMINATE, 0, pid)
        if hProc:
            win32api.TerminateProcess(hProc, 0)
    finally:
        if hProc:
            hProc.Close()
