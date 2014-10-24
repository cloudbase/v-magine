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

import os

from stackinabox import utils

def _get_openssl_bin():
    openssl_dir = os.path.join(utils.get_resources_dir(), "openssl")
    return os.path.join(openssl_dir, "openssl")


def get_random_password():
    openssl_bin = _get_openssl_bin()
    (out, err) = utils.execute_process([openssl_bin, "rand", "-base64", "30"])
    return out[:-len(os.linesep)]


def get_password_md5(password):
    openssl_bin = _get_openssl_bin()
    (out, err) = utils.execute_process([openssl_bin, "passwd", "-1", password])
    return out[:-len(os.linesep)]
