# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
# Licensed under the AGPLv3, see LICENCE file for details.

from glanceclient.v2 import client as glance_client
from keystoneclient.v2_0 import client as keystone_client


class GlanceClient(object):
    def __init__(self):
        self._glance = None

    def login(self, tenant_name, username, password, auth_url):
        keystone = keystone_client.Client(tenant_name=tenant_name,
                                          username=username,
                                          password=password,
                                          auth_url=auth_url)

        glance_endpoint = keystone.service_catalog.url_for(
            service_type='image', endpoint_type='publicURL')
        self._glance = glance_client.Client(glance_endpoint,
                                            token=keystone.auth_token)

    def get_images(self):
        return list(self._glance.images.list())

    def delete_image(self, image_id):
        self._glance.images.delete(image_id)

    def create_image(self, image_name, disk_format, container_format, data,
                     hypervisor_type, visibility="public"):
        image = self._glance.images.create(
            name=image_name, disk_format=disk_format, visibility=visibility,
            container_format=container_format, hypervisor_type=hypervisor_type)
        self._glance.images.upload(image['id'], data)
