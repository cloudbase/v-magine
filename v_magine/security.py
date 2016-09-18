# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
# Licensed under the AGPLv3, see LICENCE file for details.

import logging
import os

from v_magine import constants
from v_magine import utils

LOG = logging.getLogger(__name__)


def _get_openssl_bin():
    return os.path.join(utils.get_bin_dir(), "openssl.exe")


def get_random_password():
    openssl_bin = _get_openssl_bin()
    (out, err) = utils.execute_process([openssl_bin, "rand", "-base64", "30"])
    return out[:-len(os.linesep)]


def get_password_md5(password):
    openssl_bin = _get_openssl_bin()
    (out, err) = utils.execute_process([openssl_bin, "passwd", "-1", password])
    return out[:-len(os.linesep)]


def _ensure_dir(path):
    dir_path = os.path.dirname(path)
    if not os.path.isdir(dir_path):
        os.mkdir(dir_path)


def generate_ssh_key(key_path, key_type="rsa", key_bits=2048):
    _ensure_dir(key_path)

    if os.path.exists(key_path):
        os.remove(key_path)

    pub_key_path = "%s.pub" % key_path
    if os.path.exists(pub_key_path):
        os.remove(pub_key_path)

    ssh_keygen_bin = os.path.join(utils.get_bin_dir(), "ssh-keygen.exe")
    (out, err) = utils.execute_process(
        [ssh_keygen_bin, "-t", key_type, "-b", str(key_bits), "-N", "", "-C",
         "%s controller" % constants.PRODUCT_NAME, "-f", key_path])
    LOG.debug("ssh-keygen output: %s" % out)

    return (key_path, pub_key_path)


def get_user_ssh_dir():
    return os.path.expanduser('~\\.ssh')
