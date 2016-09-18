# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
# Licensed under the AGPLv3, see LICENCE file for details.

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
