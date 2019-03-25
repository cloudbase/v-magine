# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
# Licensed under the AGPLv3, see LICENCE file for details.

import logging
import re

import fastestmirror
from six.moves.urllib import request

from v_magine import constants
from v_magine import exceptions
from v_magine import utils

LOG = logging

DEFAULT_CENTOS_RELEASE = "7.6.1810"
DEFAULT_CENTOS_MIRROR = "http://mirror.centos.org/centos/%s/os/%s"
CENTOS_VAULT_RELEASE_URL = "http://vault.centos.org/%s/os/%s"


def get_repo_mirrors(release=DEFAULT_CENTOS_RELEASE, arch="x86_64",
                     max_mirrors=8, sort_by_speed=True):
    default_mirror = DEFAULT_CENTOS_MIRROR % (release, arch)
    vault_release_url = CENTOS_VAULT_RELEASE_URL % (release, arch)

    # After a new CentOS release, previous ones are not available in the
    # mirrors any more and the only way to retrieve them is via the vault
    if not utils.check_url_exists(default_mirror):
        LOG.warn("Mirrors not available for release %s, using CentOS vault",
                 release)
        if utils.check_url_exists(vault_release_url):
            return [vault_release_url]
        else:
            raise exceptions.InvalidUrlException(
                "CentOS mirrors not found for release %s " % release)

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
    if default_mirror not in mirrors:
        mirrors.append(default_mirror)

    return mirrors
