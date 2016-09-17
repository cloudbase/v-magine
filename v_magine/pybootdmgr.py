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

import atexit
import iniparse
import logging
import os
import subprocess
import sys

from v_magine import utils
from v_magine import windows

LOG = logging


class PyBootdManager(object):
    def __init__(self):
        self._pybootd_ini_path = None
        self._pybootd_proc = None
        self._pxelinux_cfg_dir = None

    def _get_pybootd_ini_template_path(self):
        return os.path.join(utils.get_resources_dir(), "pybootd.ini")

    def _get_pxelinux_cfg_path(self):
        return os.path.join(utils.get_resources_dir(), "pxelinux.template")

    def _generate_pybootd_ini(self, listen_address, tftp_root_url,
                              reservations, pool_start,
                              pool_count=None):
        pybootd_ini_template_path = self._get_pybootd_ini_template_path()

        pybootd_ini_path = utils.copy_to_temp_file(pybootd_ini_template_path)

        with open(pybootd_ini_path, 'rb') as f:
            cfg = iniparse.INIConfig(f)

        if not pool_count:
            pool_count = len(reservations)

        cfg.bootp.address = listen_address
        cfg.bootp.pool_start = pool_start
        cfg.bootp.pool_count = pool_count
        cfg.tftp.root = tftp_root_url

        # pybootd does not handle reservations yet
        for (mac_address, ip_addr) in reservations:
            cfg.mac[mac_address] = "enable"

        with open(pybootd_ini_path, 'wb') as f:
            f.write(str(cfg))

        return pybootd_ini_path

    def generate_mac_pxelinux_cfg(self, pxe_mac_address, params):
        mac_cfg_path = os.path.join(self._pxelinux_cfg_dir,
                                    "01-%s" % pxe_mac_address.lower())

        with open(self._get_pxelinux_cfg_path(), "rb") as f:
            pxelinux_cfg = f.read()

        for (key, value) in params.items():
            pxelinux_cfg = pxelinux_cfg.replace("<%%%s%%>" % key, value)

        with open(mac_cfg_path, "wb") as f:
            f.write(pxelinux_cfg)

    def start(self, listen_address, tftp_root_dir, pool_start, reservations,
              pool_count=None):
        self.stop()

        tftp_root_url = "file://"
        if sys.platform == "win32":
            # Note: pybootd fails if the drive is in the url
            tftp_root_url += tftp_root_dir.replace("\\", "/")[2:]
        else:
            tftp_root_url += tftp_root_dir

        self._pybootd_ini_path = self._generate_pybootd_ini(
            listen_address, tftp_root_url, reservations,
            pool_start, pool_count)

        self._pxelinux_cfg_dir = os.path.join(tftp_root_dir, "pxelinux.cfg")
        if not os.path.isdir(self._pxelinux_cfg_dir):
            os.makedirs(self._pxelinux_cfg_dir)

        args = [sys.executable, "pybootd", "--config", self._pybootd_ini_path]
        LOG.info("Starting pybootd: %s" % args)

        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        self._pybootd_proc = subprocess.Popen(args,
                                              # stdout=subprocess.PIPE,
                                              # stderr=subprocess.PIPE,
                                              shell=False,
                                              startupinfo=si)

        # Make sure we terminate the process before exiting
        # TODO(alexpilotti): Platform independence
        atexit.register(windows.kill_process, self._pybootd_proc.pid)

    def stop(self):
        if self._pybootd_proc:
            LOG.info('Killing pybootd')
            self._pybootd_proc.kill()
            self._pybootd_proc = None
        if self._pybootd_ini_path:
            os.remove(self._pybootd_ini_path)
            self._pybootd_ini_path = None
