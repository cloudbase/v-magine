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

from v_magine import mtools
from v_magine import mkisofs

IMAGE_TYPE_ISO = "ISO"
IMAGE_TYPE_VFD = "VFD"


class BaseImageManager(object):
    def create_image(self, image_path, content_path, label):
        raise NotImplementedError()


class MkIsoFSISOManager(BaseImageManager):
    def create_image(self, image_path, content_path, label):
        mkisofs.create_iso_image(image_path, content_path, label)


class MToolsVFDManager(BaseImageManager):
    def create_image(self, image_path, content_path, label):
        mtools.create_vfd(image_path, label=label)
        mtools.copy_to_vfd(image_path, content_path)


def get_image_manager(image_type=IMAGE_TYPE_ISO):
    if image_type == IMAGE_TYPE_ISO:
        return MkIsoFSISOManager()
    elif image_type == IMAGE_TYPE_VFD:
        return MToolsVFDManager()
    else:
        raise Exception("Invalid image type: %s" % image_type)
