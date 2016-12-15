# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
# Licensed under the AGPLv3, see LICENCE file for details.

import functools
import logging
import os
import psutil
import random
import re
import subprocess
import tempfile
import time

from dns import resolver
from six.moves.urllib import parse
from six.moves.urllib import request

LOG = logging


def execute_process(args, shell=False):
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    p = subprocess.Popen(args,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         shell=shell,
                         startupinfo=si)
    (out, err) = p.communicate()
    if p.returncode:
        raise Exception("Command failed: %s" % err)
    return (out, err)


def download_file(url, target_path, report_hook=None):
    class URLopenerWithException(request.FancyURLopener):
        def http_error_default(self, url, fp, errcode, errmsg, headers):
            raise Exception("Download failed with error: %s" % errcode)
    return URLopenerWithException().retrieve(url, target_path,
                                             reporthook=report_hook)


def retry_on_error(max_attempts=10, sleep_seconds=0,
                   terminal_exceptions=[]):
    def _retry_on_error(func):
        @functools.wraps(func)
        def _exec_retry(*args, **kwargs):
            i = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except KeyboardInterrupt as ex:
                    LOG.debug("Got a KeyboardInterrupt, skip retrying")
                    LOG.exception(ex)
                    raise
                except Exception as ex:
                    if any([isinstance(ex, tex)
                            for tex in terminal_exceptions]):
                        raise

                    i += 1
                    if i < max_attempts:
                        LOG.warn("Exception occurred, retrying: %s", ex)
                        time.sleep(sleep_seconds)
                    else:
                        raise
        return _exec_retry
    return _retry_on_error


def copy_to_temp_file(src_file):
    (fd, temp_file_path) = tempfile.mkstemp()
    with open(src_file, 'rb') as f:
        os.write(fd, f.read())
    os.close(fd)
    return temp_file_path


def get_base_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_bin_dir():
    return os.path.join(get_base_dir(), "bin")


def get_web_dir():
    return os.path.join(get_base_dir(), "www")


def get_resources_dir():
    return os.path.join(get_base_dir(), "resources")


def get_pxe_files_dir():
    return os.path.join(get_base_dir(), "pxe")


def get_random_ipv4_subnet():
    # 24 bit only for now
    return ("10." + str(random.randint(1, 254)) + "." +
            str(random.randint(1, 254)) + ".0")


def get_random_mac_address():
    mac = [0xfa, 0x16, 0x3e,
           random.randint(0x00, 0xff),
           random.randint(0x00, 0xff),
           random.randint(0x00, 0xff)]
    return '-'.join(list(map(lambda x: "%02x" % x, mac)))


def add_credentials_to_url(url, username, password):
    if not url or not username:
        return url
    s = parse.urlsplit(url)
    netloc = "%s:%s@%s" % (
        parse.quote(username), parse.quote(password or ''), s.hostname)
    if s.port:
        netloc += ":%d" % s.port
    return parse.urlunsplit(s._replace(netloc=netloc))


def get_dns():
    return resolver.Resolver().nameservers


def get_proxy():
    return request.getproxies().get('http')


def get_cpu_count():
    return len(psutil.cpu_percent(interval=0, percpu=True))


def is_valid_hostname(hostname):
    if len(hostname) > 253:
        return False
    if hostname[-1] == ".":
        # Strips one dot from the right, if present
        hostname = hostname[:-1]
    allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in hostname.split("."))
