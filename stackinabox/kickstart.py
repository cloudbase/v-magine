# Copyright 2014 Cloudbase Solutions Srl
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

import logging
import os
import tempfile

from stackinabox import utils
from stackinabox import diskimage

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
    except Exception as ex:
        if os.path.exists(ks_image_path):
            os.remove(ks_image_path)
        raise
    finally:
        os.remove(ks_file)
