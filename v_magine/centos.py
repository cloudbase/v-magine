# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
# Licensed under the AGPLv3, see LICENCE file for details.

import logging
import re

import fastestmirror
from six.moves.urllib import request

from v_magine import constants

LOG = logging

DEFAULT_CENTOS_RELEASE = "7.3.1611"
DEFAULT_CENTOS_MIRROR = "http://mirror.centos.org/centos/%s/os/x86_64"


def get_repo_mirrors(release=DEFAULT_CENTOS_RELEASE, arch="x86_64",
                     max_mirrors=8, sort_by_speed=True):
    url_base = "http://mirrorlist.centos.org/?release={0}&arch={1}&repo=os"
    url = url_base.format(release.split('.')[0], arch)

    mirrors = []
    try:
        req = request.Request(url, headers={'User-Agent':
                                            constants.PRODUCT_NAME})
        mirrors = request.urlopen(req).read().decode().split("\n")[:-1]
    except Exception as ex:
        LOG.exception(ex)
        LOG.error("Failed to get list of CentOS mirrors")

    if len(release.split('.')) > 1:
        # Use the exact release number, mirrorlist.centos.org accepts only
        # major release numbers and returns the latest
        mirrors = [re.sub(r"(.*)/\d+(?:\.\d+)*/(.*)", r"\1/%s/\2" % release, m)
                   for m in mirrors]

    try:
        if sort_by_speed:
            mirrors = fastestmirror.FastestMirror(mirrors).get_mirrorlist()
    except Exception as ex:
        LOG.exception(ex)
        LOG.error("Failed to sort the list of CentOS mirrors by speed")

    if max_mirrors:
        mirrors = mirrors[:max_mirrors - 1]

    # Always add the default mirror
    default_mirror = DEFAULT_CENTOS_MIRROR % release
    if default_mirror not in mirrors:
        mirrors.append(default_mirror)

    return mirrors
