# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
# Licensed under the AGPLv3, see LICENCE file for details.

import logging
import os
import tempfile

from v_magine import utils
from v_magine import diskimage

LOG = logging


def _get_kickstart_template():
    return os.path.join(utils.get_resources_dir(), "ks.template")


def _generate_kickstart_file(params):
    with open(_get_kickstart_template(), "rb") as f:
        ks = f.read()

    LOG.debug("Kickstart params: %s" % params)
    for (key, value) in params.items():
        ks = ks.replace("<%%%s%%>" % key, value)

    ks_file = os.path.join(tempfile.gettempdir(), 'ks.cfg')
    with open(ks_file, "wb") as f:
        f.write(ks)

    return ks_file


def generate_kickstart_image(ks_image_path, params):
    ks_file = _generate_kickstart_file(params)
    try:
        image_manager = diskimage.get_image_manager()
        image_manager.create_image(ks_image_path, ks_file, label="ks")
    except Exception:
        if os.path.exists(ks_image_path):
            os.remove(ks_image_path)
        raise
    finally:
        os.remove(ks_file)
