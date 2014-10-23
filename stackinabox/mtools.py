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
import subprocess

from stackinabox import utils

def _execute_process(args, shell=False):
    p = subprocess.Popen(args,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         shell=shell)
    (out, err) = p.communicate()
    if p.returncode:
        raise Exception("Command failed: %s" % err)


def _get_mtools_dir():
    return os.path.join(utils.get_resources_dir(), "mtools")


def create_vfd(vfd_path, size_kb=1440, label="stackinabox"):
    mformat = os.path.join(_get_mtools_dir(), "mformat.exe")
    _execute_process([mformat, "-C", "-f", str(size_kb), "-v", label,
                      "-i", vfd_path, "::"])


def copy_to_vfd(vfd_path, src_path):
    mcopy = os.path.join(_get_mtools_dir(), "mcopy.exe")
    _execute_process([mcopy, "-i", vfd_path, src_path, "::"])
