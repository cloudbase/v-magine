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
from stackinabox import vfd

LOG = logging


def _get_kickstart_template():
    return os.path.join(utils.get_resources_dir(), "ks.template")


def _generate_kickstart_file(params):
    with open(_get_kickstart_template(), "rb") as f:
        ks = f.read()

    LOG.debug("Kickstart params: %s" % params)
    for (key, value) in params.items():
        ks = ks.replace("<%%%s%%>" % key, value)

    ks_fd, ks_file = tempfile.mkstemp()
    os.write(ks_fd, ks)
    os.close(ks_fd)

    return ks_file


def generate_kickstart_vfd(vfd_path, params):
    ks_file = _generate_kickstart_file(params)
    try:
        vfd_manager = vfd.get_vfd_manager()
        vfd_manager.create_vfd(vfd_path, "ks")
        vfd_manager.copy_to_vfd(vfd_path, ks_file, "/ks.cfg")
    except Exception as ex:
        if os.path.exists(vfd_path):
            os.remove(vfd_path)
        raise
    finally:
        os.remove(ks_file)
