import os

from v_magine import constants
from v_magine import utils


def create_iso_image(iso_path, content_path, label=constants.PRODUCT_NAME):
    if os.path.exists(iso_path):
        os.remove(iso_path)

    normalized_path = content_path.replace("\\", "/")
    mkisofs = os.path.join(utils.get_bin_dir(), "mkisofs.exe")
    utils.execute_process([mkisofs,
                           '-o', iso_path,
                           '-ldots',
                           '-allow-lowercase',
                           '-allow-multidot',
                           '-l',
                           '-publisher', constants.PRODUCT_NAME,
                           '-quiet',
                           '-J',
                           '-r',
                           '-V', label,
                           normalized_path])
