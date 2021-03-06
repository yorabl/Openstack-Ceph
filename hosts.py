__author__ = 'yrabl'

import paramiko


class Host(object):
    def __init__(self, params, hostname):
        self.parameters = {
            'host_address': params.get(hostname, 'host_address'),
            'host_role': params.get(hostname, 'role'),
            'host_username': params.get(hostname, 'username'),
            'host_password': params.get(hostname, 'password'),
            'user': params.get('DEFAULT', 'user'),
            'ceph.conf path': params.get('DEFAULT', 'ceph_conf_file_path'),
            'uuid': params.get('DEFAULT', 'uuid')}

        self.ssh = paramiko.SSHClient()

    def open_ssh_connection(self):
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(hostname=self.parameters['host_address'],
                         username=self.parameters['host_username'],
                         password=self.parameters['host_password'])

    def close_ssh_connection(self):
        self.ssh.close()

    def run_bash_command(self, bash_command):
        stdin, stdout, stderr = self.ssh.exec_command(bash_command)

        output = stdout.read()
        return output

    def install_software(self, software):
        self.open_ssh_connection()

        cmd = "yum install -y %s" % software
        self.run_bash_command(cmd)
        self.close_ssh_connection()

    def copy_file(self, source, destination):
        ftp = self.ssh.open_sftp()
        ftp.get(source, destination)
        ftp.close()

    def reset_services(self, component):
        self.open_ssh_connection()

        cmd = "for daemon in `systemctl -a | grep openstack-%s | awk '{ print$2 }'`; do systemctl restart $daemon; done" % component
        self.run_bash_command(cmd)

        self.close_ssh_connection()
        print "Restarting the %s services" % component

    def set_parameter(self, conf_file, section, parameter, value):
        self.open_ssh_connection()

        cmd = "crudini --set %s %s %s %s" % \
              (conf_file, section, parameter, value)
        self.run_bash_command(cmd)

        self.close_ssh_connection()


class CephHost(Host):
    def __init__(self, params, hostname):
        Host.__init__(self, params, hostname)
        self.parameters['pg_num'] = params.get('DEFAULT', 'ceph_pool_pg')
        self.pools = {'glance': params.get('DEFAULT', 'set_glance'),
                      'cinder': params.get('DEFAULT', 'set_cinder'),
                      'cinder-backup': params.get('DEFAULT', 'set_cinder_backup'),
                      'nova': params.get('DEFAULT', 'set_nova')}

    def delete_pools(self, roles):

        self.open_ssh_connection()

        if 'all' in roles:
            components = ['cinder', 'cinder-backup  ', 'glance', 'nova']

            for component in components:

                cmd = "sudo ceph osd pool delete %s-%s %s-%s --yes-i-really-really-mean-it" % \
                      (self.parameters['user'], component, self.parameters['user'], component)

                self.run_bash_command(cmd)

                print "%s-%s has been deleted" % (self.parameters['user'], component)
        else:
            for role in roles:

                cmd = "sudo ceph osd pool delete %s-%s %s-%s --yes-i-really-really-mean-it" % \
                    (self.parameters['user'], role, self.parameters['user'], role)
                self.run_bash_command(cmd)

                print "%s-%s has been deleted" % (self.parameters['user'],  role)

        self.close_ssh_connection()

    def reset_pools(self, roles):
        self.delete_pools(roles)
        self.create_pools()

    def create_pools(self):
        self.open_ssh_connection()

        for component in self.pools:
            if self.pools[component] == 'y':
                cmd = "sudo ceph osd pool create %s-%s %s" % \
                      (self.parameters['user'], component, self.parameters['pg_num'])
                self.run_bash_command(cmd)

                print "Pool: %s-%s has been created" % \
                      (self.parameters['user'], component)

        self.close_ssh_connection()

    def create_client(self, component):

        self.open_ssh_connection()
        if component == "cinder":
            cmd = "sudo ceph auth get-or-create client.%s-cinder mon 'allow r' osd 'allow class-read " \
                  "object_prefix rbd_children," \
                  "allow rwx pool=%s-cinder, " \
                  "allow rwx pool=%s-nova , " \
                  "allow rx pool=%s-glance'" % \
                  (self.parameters['user'], self.parameters['user'],
                   self.parameters['user'], self.parameters['user'])

            self.run_bash_command(cmd)

            print "client.%s-cinder has been created" % \
                  self.parameters['user']

        if component == 'glance':
            cmd = "sudo ceph auth get-or-create client.%s-glance mon 'allow r' osd " \
                  "'allow class-read object_prefix rbd_children, allow rwx pool=%s-glance'" % \
                  (self.parameters['user'], self.parameters['user'])
            self.run_bash_command(cmd)
            print "client.%s-glance has been created" % \
                  self.parameters['user']

        if component == "cinder-backup":
            cmd = "sudo ceph auth get-or-create client.%s-cinder-backup mon 'allow r' osd 'allow class-read " \
                  "object_prefix rbd_children, allow rwx pool=%s-cinder-backup'" % \
                  (self.parameters['user'], self.parameters['user'])
            self.run_bash_command(cmd)
            print "client.%s-cinder-backup has been created" % \
                  self.parameters['user']

        self.close_ssh_connection()

    def get_keyring(self, component):
        self.open_ssh_connection()

        cmd = "sudo ceph auth get client.%s-%s" % (self.parameters['user'], component)
        keyring = self.run_bash_command(cmd)

        self.close_ssh_connection()
        return keyring

    def get_key(self, component):
        self.open_ssh_connection()

        cmd = "sudo ceph auth get-key client.%s-%s" % (self.parameters['user'], component)
        key = self.run_bash_command(cmd)

        self.close_ssh_connection()
        return key

    def get_ceph_conf(self):
        self.open_ssh_connection()

        cmd = "sudo cat %s" % self.parameters['ceph.conf path']
        conf = self.run_bash_command(cmd)

        self.close_ssh_connection()
        return conf


class GlanceHost(Host):
    def __init__(self, params, hostname):
        Host.__init__(self, params, hostname)
        self.parameters['conf_path'] = params.get('GLANCE', 'conf_file')
        self.parameters['store'] = params.get('GLANCE', 'store')
        self.parameters['stores'] = params.get("GLANCE", 'stores')
        self.parameters['section'] = params.get("GLANCE", 'stores_section')
        self.parameters['chunk_size'] = params.get("GLANCE", 'rbd_store_chunk_size')
        self.parameters['show_direct_url'] = params.get("GLANCE", 'show_image_direct_url')
        self.parameters['enable_v1_api'] = params.get('GLANCE', 'enable_v1_api')
        self.parameters['enable_v2_api'] = params.get('GLANCE', 'enable_v2_api')
        self.parameters['packages'] = params.get('DEFAULT', 'ceph_packages')

    #to do: add a check that if the file exists - don't do anything.
    #       add the --run-over-keyrings flag
    def set_keyring(self, ceph_host):
        keyring = ceph_host.get_keyring('glance')

        self.open_ssh_connection()
        cmd = "echo -e \"" + keyring + "\" > /etc/ceph/ceph.client.%s-glance.keyring" % \
              self.parameters['user']

        self.run_bash_command(cmd)

        cmd = "chown glance:glance /etc/ceph/ceph.client.%s-glance.keyring" % \
              self.parameters['user']
        self.run_bash_command(cmd)

        self.close_ssh_connection()
        print "Glance's Ceph keyring is set"

    def set_ceph_conf_file(self, ceph_host):
        ceph_conf = ceph_host.get_ceph_conf()
        self.open_ssh_connection()

        cmd = "echo -e \"" + ceph_conf + "\" > /etc/ceph/ceph.conf"

        self.run_bash_command(cmd)

        self.close_ssh_connection()
        print "The Ceph configuration file has been set in the Glance host"

    def set_glance_conf(self):

        self.set_parameter(self.parameters['conf_path'], self.parameters['section'],
                           'default_store', self.parameters['store'])

        self.set_parameter(self.parameters['conf_path'], 'DEFAULT',
                           'show_image_direct_url', self.parameters['show_direct_url'])

        self.set_parameter(self.parameters['conf_path'], 'DEFAULT',
                           'enable_v1_api', self.parameters['enable_v1_api'])

        self.set_parameter(self.parameters['conf_path'], 'DEFAULT',
                           'enable_v2_api', self.parameters['enable_v2_api'])

        self.set_parameter(self.parameters['conf_path'], self.parameters['section'],
                           'stores', self.parameters['stores'])

        self.set_parameter(self.parameters['conf_path'], self.parameters['section'],
                           'rbd_store_pool', '%s' % self.parameters['user'] + '-glance')

        self.set_parameter(self.parameters['conf_path'], self.parameters['section'],
                           'rbd_store_user', '%s' % self.parameters['user'] + '-glance')

        self.set_parameter(self.parameters['conf_path'], self.parameters['section'],
                           'rbd_store_ceph_conf', self.parameters['ceph.conf path'])

        self.set_parameter(self.parameters['conf_path'], self.parameters['section'],
                           'rbd_store_chunk_size', self.parameters['chunk_size'])

        self.set_parameter(self.parameters['conf_path'], self.parameters['section'],
                           'stores', "\" %s \"" % self.parameters['stores'])

        print "The Glance configuration has been changed"


class CinderHost(Host):
    def __init__(self, params, hostname):
        Host.__init__(self, params, hostname)
        self.parameters['conf_path'] = params.get('CINDER', 'conf_file')
        self.parameters['backend_name'] = params.get('CINDER', 'backend_name')
        self.parameters['driver'] = params.get('CINDER', 'driver')
        self.parameters['rbd_flatten_volume_from_snapshot'] = params.get('CINDER', 'rbd_flatten_volume_from_snapshot')
        self.parameters['rbd_max_clone_depth'] = params.get('CINDER', 'rbd_max_clone_depth')
        self.parameters['rbd_store_chunk_size'] = params.get('CINDER', 'rbd_store_chunk_size')
        self.parameters['rados_connect_timeout'] = params.get('CINDER', 'rados_connect_timeout')
        self.parameters['glance_client_api'] = params.get('CINDER', 'glance_client_api')
        self.parameters['packages'] = params.get('DEFAULT', 'ceph_packages')

    def set_keyring(self, ceph_host):

        keyring = ceph_host.get_keyring('cinder')
        self.open_ssh_connection()

        cmd = "echo -e \"" + keyring + "\" > /etc/ceph/ceph.client.%s-cinder.keyring" % \
              self.parameters['user']
        self.run_bash_command(cmd)

        cmd = "chown cinder:cinder /etc/ceph/ceph.client.%s-cinder.keyring" % \
              self.parameters['user']
        self.run_bash_command(cmd)

        self.close_ssh_connection()
        print "Cinder's Ceph keyring is set"

    def set_ceph_conf_file(self, ceph_host):
        ceph_conf = ceph_host.get_ceph_conf()
        self.open_ssh_connection()

        cmd = "echo -e \"" + ceph_conf + "\" > /etc/ceph/ceph.conf"
        self.run_bash_command(cmd)

        self.close_ssh_connection()
        print "The Ceph configuration file has been set"

    #def set_type(self):
        #self.open_ssh_connection()

        #cmd = "cinder --os-username %s --os-password %s type-create %s" % \
        #      (self.parameters['os_user'], self.parameters['os_password'], self.parameters['backend_name'])
        #self.run_bash_command(cmd)

        #cmd = "cinder --os-username %s --os-password %s type-key %s set volume_backend_name = %s" % \
        #      (self.parameters['os_user'], self.parameters['os_password'],
        #       self.parameters['backend_name'], self.parameters['backend_name'])
        #self.run_bash_command(cmd)

        #self.close_ssh_connection()

    def set_cinder_conf(self):

        self.set_parameter(self.parameters['conf_path'], 'DEFAULT',
                           'enabled_backends', self.parameters['backend_name'])

        self.set_parameter(self.parameters['conf_path'], 'DEFAULT',
                           'glance_api_version', self.parameters['glance_client_api'])

        self.set_parameter(self.parameters['conf_path'], self.parameters['backend_name'],
                           'volume_driver', self.parameters['driver'])

        self.set_parameter(self.parameters['conf_path'], self.parameters['backend_name'],
                           'volume_backend_name',
                           '%s-%s' % (self.parameters['user'], self.parameters['backend_name']))

        self.set_parameter(self.parameters['conf_path'], self.parameters['backend_name'],
                           'rbd_pool', '%s-' % (self.parameters['user']) + 'cinder')

        self.set_parameter(self.parameters['conf_path'], self.parameters['backend_name'],
                           'rbd_ceph_conf', self.parameters['ceph.conf path'])

        self.set_parameter(self.parameters['conf_path'], self.parameters['backend_name'],
                           'rbd_flatten_volume_from_snapshot',
                           self.parameters['rbd_flatten_volume_from_snapshot'])

        self.set_parameter(self.parameters['conf_path'], self.parameters['backend_name'],
                           'rbd_max_clone_depth', self.parameters['rbd_max_clone_depth'])

        self.set_parameter(self.parameters['conf_path'], self.parameters['backend_name'],
                           'rbd_store_chunk_size', self.parameters['rbd_store_chunk_size'])

        self.set_parameter(self.parameters['conf_path'], self.parameters['backend_name'],
                           'rados_connect_timeout', self.parameters['rados_connect_timeout'])

        self.set_parameter(self.parameters['conf_path'], self.parameters['backend_name'],
                           'rbd_user', '%s-' % (self.parameters['user']) + 'cinder')

        self.set_parameter(self.parameters['conf_path'], self.parameters['backend_name'],
                           'rbd_secret_uuid', self.parameters['uuid'])

        print "The Cinder configuration has been changed"


class CinderBackupHost(Host):
    def __init__(self, params, hostname):
        Host.__init__(self, params, hostname)
        self.parameters['conf_path'] = params.get('CINDER-BACKUP', 'conf_file')
        self.parameters['backup_driver'] = params.get('CINDER-BACKUP', 'backup_driver')
        self.parameters['backup_ceph_chunk_size'] = params.get('CINDER-BACKUP', 'backup_ceph_chunk_size')
        self.parameters['backup_ceph_stripe_unit'] = params.get('CINDER-BACKUP', 'backup_ceph_stripe_unit')
        self.parameters['backup_ceph_stripe_count'] = params.get('CINDER-BACKUP', 'backup_ceph_stripe_count')
        self.parameters['restore_discard_excess_bytes'] = params.get('CINDER-BACKUP', 'restore_discard_excess_bytes')
        self.parameters['packages'] = params.get('DEFAULT', 'ceph_packages')

    def set_keyring(self, ceph_host):
        keyring = ceph_host.get_keyring('cinder-backup')

        self.open_ssh_connection()
        cmd = "echo -e \"" + keyring + "\" > /etc/ceph/ceph.client.%s-cinder-backup.keyring" % self.parameters['user']
        self.run_bash_command(cmd)

        cmd = "chown cinder:cinder /etc/ceph/ceph.client.%s-cinder-backup.keyring" % self.parameters['user']
        self.run_bash_command(cmd)

        self.close_ssh_connection()
        print "Cinder-backup's keyring is set"

    def set_ceph_conf_file(self, ceph_host):
        ceph_conf = ceph_host.get_ceph_conf()
        self.open_ssh_connection()

        cmd = "echo -e \"" + ceph_conf + "\" > /etc/ceph/ceph.conf"

        self.run_bash_command(cmd)
        self.close_ssh_connection()
        print "The Ceph configuration file has been set"

    def set_cinder_backup_conf(self):

        self.set_parameter(self.parameters['conf_path'], 'DEFAULT',
                           'backup_driver', self.parameters['backup_driver'])

        self.set_parameter(self.parameters['conf_path'], 'DEFAULT',
                           'backup_ceph_pool', '%s-' % self.parameters['user'] + 'cinder-backup')

        self.set_parameter(self.parameters['conf_path'], 'DEFAULT',
                           'backup_ceph_chunk_size', self.parameters['backup_ceph_chunk_size'])

        self.set_parameter(self.parameters['conf_path'], 'DEFAULT',
                           'backup_ceph_stripe_unit', self.parameters['backup_ceph_stripe_unit'])

        self.set_parameter(self.parameters['conf_path'], 'DEFAULT',
                           'backup_ceph_stripe_count', self.parameters['backup_ceph_stripe_count'])

        self.set_parameter(self.parameters['conf_path'], 'DEFAULT',
                           'restore_discard_excess_bytes',
                           self.parameters['restore_discard_excess_bytes'])
        self.set_parameter(self.parameters['conf_path'], 'DEFAULT',
                           'backup_ceph_user', '%s-' % self.parameters['user'] + 'cinder-backup')

        print "The Cinder-Backup configuration is set"


class NovaHost(Host):
    def __init__(self, params, hostname):
        Host.__init__(self, params, hostname)
        self.parameters['conf_path'] = params.get('NOVA', 'conf_file')
        self.parameters['images_type'] = params.get('NOVA', 'images_type')
        self.parameters['inject_password'] = params.get('NOVA', 'inject_password')
        self.parameters['inject_key'] = params.get('NOVA', 'inject_key')
        self.parameters['inject_partition'] = params.get('NOVA', 'inject_partition')
        self.parameters['live_migration_flag'] = params.get('NOVA', 'live_migration_flag')
        self.parameters['allow_resize_to_same_host'] = params.get('NOVA', 'allow_resize_to_same_host')
        self.parameters['secret_xml'] = "<secret ephemeral='no' private='no'>\n\t" \
                                        "<uuid>%s</uuid>\n\t" \
                                        "<usage type='ceph'>\n\t\t" \
                                        "<name>client.%s-cinder secret</name>\n\t" \
                                        "</usage>\n" \
                                        "</secret>" % \
                                        (self.parameters['uuid'], self.parameters['user'])
        self.parameters['packages'] = params.get('DEFAULT', 'ceph_packages')

    def set_keyring(self, ceph_host):
        keyring = ceph_host.get_keyring('cinder')
        self.open_ssh_connection()

        cmd = "echo -e \"" + keyring + "\" > /etc/ceph/ceph.client.%s-cinder.keyring" % \
              (self.parameters['user'])
        self.run_bash_command(cmd)

        self.close_ssh_connection()

    def set_ceph_conf_file(self, ceph_host):
        ceph_conf = ceph_host.get_ceph_conf()
        self.open_ssh_connection()

        cmd = "echo -e \"" + ceph_conf + "\" > /etc/ceph/ceph.conf"

        self.run_bash_command(cmd)
        self.close_ssh_connection()
        print "The Ceph configuration file has been set in %s" % \
              (self.parameters['host_address'])

    def set_libvirt_secret(self, ceph_host):
        self.open_ssh_connection()

        cmd = "echo -e  \"" + self.parameters['secret_xml']+"\" > ~/secret.xml"

        self.run_bash_command(cmd)

        cmd = "virsh secret-define --file ~/secret.xml"

        self.run_bash_command(cmd)

        key = ceph_host.get_key('cinder')
        cmd = "virsh secret-set-value --secret %s --base64 %s" % (self.parameters['uuid'], key)
        self.run_bash_command(cmd)

        self.close_ssh_connection()
        print "Libvirt secret value has been set"

    def set_user_setting(self):

        self.set_parameter(self.parameters['conf_path'], 'libvirt',
                           'rbd_user', '%s-' % self.parameters['user'] + 'cinder')

        self.set_parameter(self.parameters['conf_path'], 'libvirt',
                           'rbd_secret_uuid', self.parameters['uuid'])

    def set_nova_conf(self):

        self.set_parameter(self.parameters['conf_path'], 'DEFAULT',
                           'allow_resize_to_same_host', self.parameters['allow_resize_to_same_host'])

        self.set_parameter(self.parameters['conf_path'], 'libvirt',
                           'images_type', self.parameters['images_type'])

        self.set_parameter(self.parameters['conf_path'], 'libvirt',
                           'images_rbd_pool', '%s-' % self.parameters['user'] + 'nova')

        self.set_parameter(self.parameters['conf_path'], 'libvirt',
                           'images_rbd_ceph_conf', self.parameters['ceph.conf path'])

        self.set_parameter(self.parameters['conf_path'], 'libvirt',
                           'inject_password', self.parameters['inject_password'])

        self.set_parameter(self.parameters['conf_path'], 'libvirt',
                           'inject_key', self.parameters['inject_key'])

        self.set_parameter(self.parameters['conf_path'], 'libvirt',
                           'inject_partition', self.parameters['inject_partition'])

        self.set_parameter(self.parameters['conf_path'], 'libvirt',
                           'live_migration_flag',
                           '\"%s\"' % self.parameters['live_migration_flag'])

