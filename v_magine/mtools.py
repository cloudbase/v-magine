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

from v_magine import constants
from v_magine import utils


def _get_mtools_dir():
    return utils.get_bin_dir()


def create_vfd(vfd_path, size_kb=1440, label=constants.PRODUCT_NAME):
    mformat = os.path.join(_get_mtools_dir(), "mformat.exe")
    utils.execute_process([mformat, "-C", "-f", str(size_kb), "-v", label,
                           "-i", vfd_path, "::"])


def copy_to_vfd(vfd_path, src_path, target_path='/'):
    mcopy = os.path.join(_get_mtools_dir(), "mcopy.exe")
    utils.execute_process([mcopy, "-i", vfd_path, src_path,
                          "::" + target_path])
