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
import os
import subprocess
import sys

from stackinabox import utils
from stackinabox import windows

class PyBootdManager(object):
    def __init__(self):
        self._pybootd_ini_path = None
        self._pybootd_proc = None

    def _get_pybootd_ini_template_path(self):
        return os.path.join(utils.get_resources_dir(), "pybootd.ini")

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

    def start(self, listen_address, tftp_root_url, pool_start, reservations,
              pool_count=None):
        self.stop()

        self._pybootd_ini_path = self._generate_pybootd_ini(
            listen_address, tftp_root_url, reservations,
            pool_start, pool_count)

        args = [sys.executable, "-c",
                "from pybootd import daemons; daemons.main()",
                "--config", self._pybootd_ini_path]
        self._pybootd_proc = subprocess.Popen(args,
                                              #stdout=subprocess.PIPE,
                                              #stderr=subprocess.PIPE,
                                              shell=False)

        # Make sure we terminate the process before exiting
        # TODO(alexpilotti): Platform independence
        atexit.register(windows.kill_process, self._pybootd_proc.pid)

    def stop(self):
        if self._pybootd_proc:
            self._pybootd_proc.kill()
            self._pybootd_proc = None
        if self._pybootd_ini_path:
            os.remove(self._pybootd_ini_path)
            self._pybootd_ini_path = None
