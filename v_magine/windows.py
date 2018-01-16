# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
# Licensed under the AGPLv3, see LICENCE file for details.

import ctypes
import logging
import os
import pywintypes
import six
import win32api
import win32con
import win32process
import win32security
import wmi

from ctypes import windll
from ctypes import wintypes
from win32com import client

from v_magine import exceptions
from v_magine import utils

kernel32 = windll.kernel32
advapi32 = windll.Advapi32
netapi32 = windll.netapi32

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


class Win32_LOCALGROUP_MEMBERS_INFO_3(ctypes.Structure):
    _fields_ = [
        ('lgrmi3_domainandname', wintypes.LPWSTR)
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

GROUP_SID_REMOTE_DESKTOP_USERS = "S-1-5-32-555"


class LogonFailedException(Exception):
    pass


class WindowsUtils(object):
    _FW_IP_PROTOCOL_TCP = 6
    _FW_IP_PROTOCOL_UDP = 17
    _FW_SCOPE_ALL = 0
    _FW_SCOPE_LOCAL_SUBNET = 1

    _NET_FW_ACTION_BLOCK = 0
    _NET_FW_ACTION_ALLOW = 1

    _NERR_GroupNotFound = 2220
    _NERR_UserNotFound = 2221
    _ERROR_ACCESS_DENIED = 5
    _ERROR_NO_SUCH_MEMBER = 1387
    _ERROR_MEMBER_IN_ALIAS = 1378
    _ERROR_INVALID_MEMBER = 1388

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

        args = ["msiexec.exe", "/i", '"%s"' % msi_path, ui, "/l*v",
                '"%s"' % log_path]

        if features:
            args.append("ADDLOCAL=%s" % ",".join(features))

        if properties:
            for (k, v) in properties.items():
                args.append('%(k)s="%(v)s"' %
                            {"k": k, "v": str(v).replace('"', '""')})

        LOG.debug("Installing MSI: %s" % args)
        # When passing a args list, peopen escapes quotes and other
        # characters. This can be avoided by passing the entire command
        # line as a string
        utils.execute_process(" ".join(args))

    def activate_iscsi_initiator(self):
        utils.execute_process(["Start-Service", "MSiSCSI"], powershell=True)
        utils.execute_process(["Set-Service", "MSiSCSI", "-startuptype", "automatic"], powershell=True)

        LOG.debug("iSCSI initiator activated")

    def enable_ansible_on_host(self):
        script = os.path.join(utils.get_resources_dir(), "ConfigureRemotingForAnsible.ps1")
        utils.execute_process(script, powershell=True)

        LOG.debug("Remote for Ansible configured")

    def restart_nova_neutron(self):
        utils.execute_process(["Restart-Service", "nova-compute"], powershell=True)
        utils.execute_process(["Restart-Service", "neutron-hyperv-agent"], powershell=True)

        LOG.debug("OpenStack Hyper-V services restarted")


    def check_os_version(self, major, minor):
        os_version_str = self._conn_cimv2.Win32_OperatingSystem()[0].Version
        os_version = list(map(int, os_version_str.split(".")))
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

    def get_system_dir(self, sysnative=True):
        if sysnative and self.check_sysnative_dir_exists():
            return self.get_sysnative_dir()
        else:
            return self.get_system32_dir()

    def execute_powershell(self, args="", sysnative=True):
        base_dir = self.get_system_dir(sysnative)
        powershell_path = os.path.join(base_dir,
                                       'WindowsPowerShell\\v1.0\\'
                                       'powershell.exe')

        return self.run_safe_process(
            powershell_path,
            '-ExecutionPolicy RemoteSigned -NoExit -Command %s' % args,
            new_console=True)

    def create_user_logon_session(self, username, password, domain='.'):
        token = wintypes.HANDLE()
        ret_val = advapi32.LogonUserW(six.text_type(username),
                                      six.text_type(domain),
                                      six.text_type(password), 2, 0,
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

    def get_group_by_sid(self, sid):
        l = self._conn_cimv2.Win32_Group(SID=sid)
        if l:
            return (l[0].Domain, l[0].Name)
        else:
            raise exceptions.GroupNotFoundException()

    def add_user_to_local_group(self, username, groupname):
        lmi = Win32_LOCALGROUP_MEMBERS_INFO_3()
        lmi.lgrmi3_domainandname = six.text_type(username)

        ret_val = netapi32.NetLocalGroupAddMembers(0, six.text_type(groupname),
                                                   3, ctypes.addressof(lmi), 1)

        if ret_val == self._NERR_GroupNotFound:
            raise exceptions.GroupNotFoundException()
        elif ret_val == self._ERROR_ACCESS_DENIED:
            raise exceptions.AccessDeniedException()
        elif ret_val == self._ERROR_NO_SUCH_MEMBER:
            raise exceptions.UserNotFoundException()
        elif ret_val == self._ERROR_MEMBER_IN_ALIAS:
            # The user is already a member of the group
            pass
        elif ret_val == self._ERROR_INVALID_MEMBER:
            raise exceptions.BaseVMagineException('Invalid user')
        elif ret_val != 0:
            raise exceptions.BaseVMagineException('Unknown error')


def kill_process(pid):
    hProc = None
    try:
        hProc = win32api.OpenProcess(win32con.PROCESS_TERMINATE, 0, pid)
        if hProc:
            win32api.TerminateProcess(hProc, 0)
    finally:
        if hProc:
            hProc.Close()
