# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
# Licensed under the AGPLv3, see LICENCE file for details.


class BaseVMagineException(Exception):
    def __init__(self, message=None):
        super(BaseVMagineException, self).__init__(message)


class CouldNotBootException(BaseVMagineException):
    def __init__(self, message="Could not boot"):
        super(CouldNotBootException, self).__init__(message)


class CancelDeploymentException(BaseVMagineException):
    def __init__(self):
        msg = "Deployment cancelled by the user"
        super(CancelDeploymentException, self).__init__(msg)


class GroupNotFoundException(BaseVMagineException):
    pass


class UserNotFoundException(BaseVMagineException):
    pass


class AccessDeniedException(BaseVMagineException):
    pass


class ConfigFileErrorException(BaseVMagineException):
    pass


class InvalidIPAddressException(BaseVMagineException):
    pass


class InvalidUrlException(BaseVMagineException):
    pass
