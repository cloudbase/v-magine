import fastestmirror
import logging
import urllib2

from stackinabox import constants

LOG = logging

DEFAULT_CENTOS_MIRROR = "http://mirror.centos.org/centos/7/os/x86_64"


def get_repo_mirrors(release="7", arch="x86_64", max_mirrors=8,
                     sort_by_speed=True):
    url_base = "http://mirrorlist.centos.org/?release={0}&arch={1}&repo=os"
    url = url_base.format(release, arch)

    mirrors = []
    try:
        req = urllib2.Request(url, headers={'User-Agent':
                                            constants.PRODUCT_NAME})
        mirrors = urllib2.urlopen(req).read().split("\n")[:-1]
    except Exception as ex:
        LOG.exception(ex)
        LOG.error("Failed to get list of CentOS mirrors")

    try:
        if sort_by_speed:
            mirrors = fastestmirror.FastestMirror(mirrors).get_mirrorlist()
    except Exception as ex:
        LOG.exception(ex)
        LOG.error("Failed to sort the list of CentOS mirrors by speed")

    if max_mirrors:
        mirrors = mirrors[:max_mirrors - 1]

    # Always add the default mirror
    if DEFAULT_CENTOS_MIRROR not in mirrors:
        mirrors.append(DEFAULT_CENTOS_MIRROR)

    return mirrors
