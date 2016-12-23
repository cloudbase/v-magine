# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
# Licensed under the AGPLv3, see LICENCE file for details.

import logging
import os
import paramiko
import time

from v_magine import exceptions
from v_magine import utils

LOG = logging


class RDOInstaller(object):

    def __init__(self, stdout_callback, stderr_callback):
        self._stdout_callback = stdout_callback
        self._stderr_callback = stderr_callback
        self._ssh = None

    @utils.retry_on_error(sleep_seconds=5)
    def _exec_shell_cmd_check_exit_status(self, cmd):
        chan = self._ssh.invoke_shell(term=self._term_type,
                                      width=self._term_cols,
                                      height=self._term_rows)
        # Close session after the command executed
        time.sleep(3)
        chan.send("%s\nexit\n" % cmd)

        running = True
        while running:
            if chan.recv_ready():
                data = chan.recv(4096).decode('ascii')
                self._stdout_callback(data)
            if chan.recv_stderr_ready():
                data = chan.recv_stderr(4096).decode('ascii')
                self._stderr_callback(data)
            if chan.exit_status_ready():
                running = False

        exit_status = chan.recv_exit_status()
        if exit_status:
            raise Exception("Command failed with exit code: %d" % exit_status)

    @utils.retry_on_error()
    def _exec_cmd(self, cmd):
        chan = self._ssh.get_transport().open_session()
        chan.exec_command(cmd)
        return chan.recv_exit_status()

    @utils.retry_on_error(max_attempts=30, sleep_seconds=30)
    def connect(self, host, ssh_key_path, username, password, term_type,
                term_cols, term_rows):
        LOG.debug("Connection info: %s" % str((host, username, password)))

        self.disconnect()
        LOG.debug("connecting")

        self._term_type = term_type
        self._term_cols = term_cols
        self._term_rows = term_rows

        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._ssh.connect(host, username=username, password=password,
                          key_filename=ssh_key_path)
        LOG.debug("connected")

    def disconnect(self):
        if self._ssh:
            self._ssh.close()
            self._ssh = None

    def update_os(self):
        LOG.info("Updating OS")
        self._exec_shell_cmd_check_exit_status('yum update -y')
        LOG.info("OS updated")

    def reboot(self):
        LOG.info("Rebooting")
        self._exec_cmd("reboot")
        self.disconnect()

    def _exec_utils_function(self, cmd):
        centos_utils = "centos-utils.sh"
        self._copy_resource_file(centos_utils)
        return self._exec_cmd(". /root/%(centos_utils)s && %(cmd)s" %
                              {"centos_utils": centos_utils, "cmd": cmd})

    def check_new_kernel(self):
        return self._exec_utils_function("check_new_kernel")

    def _get_config_value(self, config_file, section, name):
        stdin, stdout, stderr = self._ssh.exec_command(
            '/usr/bin/openstack-config --get \"%(config_file)s\" '
            '\"%(section)s\" \"%(name)s\"' %
            {'config_file': config_file, 'section': section, 'name': name})

        if stdout.channel.recv_exit_status() != 0:
            raise exceptions.ConfigFileErrorException(
                "Could not read configuration file \"%s\"" % config_file)

        return stdout.read()[:-1]

    def get_nova_config(self):
        config_file = "/etc/nova/nova.conf"

        config_names = {"oslo_messaging_rabbit":
                        [
                            "rabbit_host",
                            "rabbit_port",
                            "rabbit_userid",
                            "rabbit_password"
                        ],
                        "neutron":
                        [
                            "url",
                            "auth_url",
                            "project_name",
                            "user_domain_name",
                            "project_domain_name",
                            "username",
                            "password"
                        ],
                        "glance":
                        [
                            "api_servers"
                        ],
                        "keystone_authtoken":
                        [
                            "project_name",
                            "username",
                            "password"
                        ]}

        config = {}
        for (section, names) in config_names.items():
            config[section] = {}
            for name in names:
                config[section][name] = self._get_config_value(
                    config_file, section, name)
        return config

    @utils.retry_on_error()
    def _copy_resource_file(self, file_name):
        LOG.debug("Copying %s" % file_name)
        sftp = self._ssh.open_sftp()
        path = os.path.join(utils.get_resources_dir(), file_name)
        sftp.put(path, '/root/%s' % file_name)
        sftp.close()
        LOG.debug("%s copied" % file_name)

    @utils.retry_on_error(sleep_seconds=5)
    def check_hyperv_compute_services(self, host_name):
        if (self._exec_utils_function(
                "source ~/keystonerc_admin && check_nova_service_up %s" %
                host_name) != 0):
            raise Exception("The Hyper-V nova-compute service is not enabled "
                            "in RDO")
        if (self._exec_utils_function(
                "source ~/keystonerc_admin && check_neutron_agent_up %s" %
                host_name) != 0):
            raise Exception("The Hyper-V neutron agent is not enabled in RDO")

    @staticmethod
    def _shell_escape(s):
        return s.replace("\\", "\\\\").replace("'", "\\'")

    def install_rdo(self, rdo_admin_password, fip_range, fip_range_start,
                    fip_range_end, fip_gateway, fip_name_servers):
        install_script = 'install-rdo.sh'
        self._copy_resource_file(install_script)

        LOG.info("Installing RDO")
        self._exec_shell_cmd_check_exit_status(
            '/bin/chmod u+x /root/%(install_script)s && '
            '/root/%(install_script)s '
            '$\'%(rdo_admin_password)s\' '
            '\"%(fip_range)s\" \"%(fip_range_start)s\" \"%(fip_range_end)s\" '
            '\"%(fip_gateway)s\" %(fip_name_servers)s' %
            {'install_script': install_script,
             'rdo_admin_password': self._shell_escape(rdo_admin_password),
             'fip_range': fip_range,
             'fip_range_start': fip_range_start,
             'fip_range_end': fip_range_end,
             'fip_gateway': fip_gateway if fip_gateway is not None else '',
             'fip_name_servers': " ".join(fip_name_servers)})
        LOG.info("RDO installed")

    def install_lis(self):
        lis_archive = "LIS.tar.gz"

        LOG.info("Installing LIS")
        self._copy_resource_file(lis_archive)
        self._exec_shell_cmd_check_exit_status(
            'LIS_DIR=$(mktemp -d) && pushd $LIS_DIR && '
            'tar zxvf /root/%(lis_archive)s && ./install.sh && '
            'popd && rm -rf $LIS_DIR' %
            {'lis_archive': lis_archive})
        LOG.info("LIS installed")
