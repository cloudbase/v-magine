# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
# Licensed under the AGPLv3, see LICENCE file for details.

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
