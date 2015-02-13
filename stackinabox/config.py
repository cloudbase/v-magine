from six.moves import winreg

BASE_KEY = 'SOFTWARE\\Cloudbase Solutions\\V-Magine\\'


class AppConfig(object):
    def _get_config_key_name(self, section):
        key_name = BASE_KEY
        if section:
            key_name += section.replace('/', '\\') + '\\'
        return key_name

    def set_config_value(self, name, value, section=None):
        key_name = self._get_config_key_name(section)

        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE,
                              key_name) as key:
            if type(value) in [int, bool]:
                regtype = winreg.REG_DWORD
            elif type(value) in [list]:
                regtype = winreg.REG_MULTI_SZ
            else:
                regtype = winreg.REG_SZ
            winreg.SetValueEx(key, name, 0, regtype, value)

    def get_config_value(self, name, section=None, default=None):
        key_name = self._get_config_key_name(section)

        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                key_name) as key:
                (value, regtype) = winreg.QueryValueEx(key, name)
                return value
        except WindowsError:
            return default
