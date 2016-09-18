# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
# Licensed under the AGPLv3, see LICENCE file for details.

from v_magine.virt.hyperv import driver


def get_virt_driver():
    # TODO(alexpilotti): Add logic for additional virt drivers later on
    return driver.HyperVDriver()
