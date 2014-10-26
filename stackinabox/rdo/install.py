import paramiko


class RDOInstaller(object):

    def __init__(self, stdout_callback, stderr_callback):
        self._stdout_callback = stdout_callback
        self._stderr_callback = stderr_callback
        self._ssh = None

    def _exec_cmd_check_exit_status(self, cmd):
        if not self._ssh:
            raise Exception("SSH connection non started")

        chan = self._ssh.get_transport().open_session()
        chan.exec_command(cmd)

        running = True
        while running:
            if chan.recv_ready():
                self._stdout_callback(chan.recv(4096).decode('ascii'))
            if chan.recv_stderr_ready():
                self._stderr_callback(chan.recv_stderr(4096).decode('ascii'))
            if chan.exit_status_ready():
                running = False

        exit_status = chan.recv_exit_status()
        if exit_status:
            raise Exception("Command failed with exit code: %d" % exit_status)

    def connect(self):
        self.disconnect()
        print "connecting"
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._ssh.connect('10.0.0.65', username='root',
                          key_filename="c:\\dev\\rdo.key")
        print "connected"

    def disconnect(self):
        if self._ssh:
            self._ssh.close()
            self._ssh = None

    def update_os(self):
        print "Updating OS"
        self._exec_cmd_check_exit_status('yum update -y')
        print "OS updated"

    def install_rdo(self):
        install_script = 'install-rdo.sh'
        print "Copying %s" % install_script
        sftp = self._ssh.open_sftp()
        sftp.put(install_script, '/root/%s' % install_script)
        sftp.close()
        print "%s copied" % install_script

        print "Installing RDO"
        self._exec_cmd_check_exit_status(
            '/bin/chmod u+x /root/%(install_script)s && '
            '/root/%(install_script)s' % { 'install_script' : install_script})
        print "RDO installed"
