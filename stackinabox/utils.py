# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
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
import random
import subprocess
import tempfile
import time

from six.moves.urllib import request

LOG = logging

def execute_process(args, shell=False):
    p = subprocess.Popen(args,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         shell=shell)
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


def retry_action(action, error_action=None, max_attempts=10, interval=0):
    i = 0
    while True:
        try:
            return action()
            break
        except Exception as ex:
            i += 1
            if i < max_attempts:
                if error_action:
                    error_action(ex)
                if interval:
                    LOG.debug("Sleeping for %s seconds" % interval)
                    time.sleep(interval)
            else:
                raise


def copy_to_temp_file(src_file):
    (fd, temp_file_path) = tempfile.mkstemp()
    with open(src_file, 'rb') as f:
        os.write(fd, f.read())
    os.close(fd)
    return temp_file_path


def get_resources_dir():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "resources")


def get_pxe_files_dir():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "pxe")


def get_random_ipv4_subnet():
    # 24 bit only for now
    return ("10." + str(random.randint(1, 254)) + "." +
            str(random.randint(1, 254)) + ".0")


def get_random_mac_address():
    mac = [0xfa, 0x16, 0x3e,
           random.randint(0x00, 0xff),
           random.randint(0x00, 0xff),
           random.randint(0x00, 0xff)]
    return '-'.join(map(lambda x: "%02x" % x, mac))
