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
