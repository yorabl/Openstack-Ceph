__author__ = 'yrabl'

import paramiko


class Host(object):

    def __init__(self, params, hostname):
        self.address = params.get(hostname, 'host_address')
        self.role = params.get(hostname, 'role')
        self.host_username = params.get(hostname, 'username')
        self.password = params.get(hostname, 'password')
        self.user = params.get('DEFAULT', 'user')
        self.ceph_conf_path = params.get('DEFAULT', 'ceph_conf_file_path')
        self.uuid = params.get('DEFAULT', 'uuid')
        self.ssh = paramiko.SSHClient()


    def open_ssh_connection(self):
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(hostname=self.address, username=self.host_username, password=self.password)

    def close_ssh_connection(self):
        self.ssh.close()

    def run_bash_command(self, bash_command):
        stdin, stdout, stderr = self.ssh.exec_command(bash_command)

        output = stdout.read()
        return output

    def install_software(self, software):
        self.open_ssh_connection()

        cmd = "yum install -y %s" % (software)
        self.run_bash_command(cmd)
        self.close_ssh_connection()

    def copy_file(self, source, destination):
        ftp = self.ssh.open_sftp()
        ftp.get(source, destination)
        ftp.close()

    def reset_services(self, component):
        self.open_ssh_connection()

        cmd = "openstack-service restart %s" % (component)
        self.run_bash_command(cmd)

        self.close_ssh_connection()
        print "Restarting the %s services" % (component)

class CephHost(Host):

    def __init__(self, params, hostname):
        Host.__init__(self, params, hostname)

        self.pg_num = params.get('DEFAULT', 'ceph_pool_pg')
        self.pools = {'glance':params.get('DEFAULT', 'set_glance'), 'cinder': params.get('DEFAULT', 'set_cinder'),
                      'cinder-backup': params.get('DEFAULT', 'set_cinder_backup'),
                      'nova': params.get('DEFAULT', 'set_nova')}

    def create_pools(self):
        self.open_ssh_connection()

        for component in self.pools:
            if self.pools[component] == 'y':
                cmd = "ceph osd pool create %s-%s %s" % (self.user, component, self.pg_num)
                self.run_bash_command(cmd)
                print "Pool: %s-%s has been created" % (self.user, component)

        self.close_ssh_connection()


    def create_client(self, component):

        self.open_ssh_connection()
        if component == "cinder":

            cmd = "ceph auth get-or-create client.%s-cinder mon 'allow r' osd 'allow class-read " \
                    "object_prefix rbd_children, allow rwx pool=%s-cinder, allow rwx pool=%s-nova , " \
                    "allow rx pool=%s-glance'" % (self.user, self.user, self.user, self.user)

            self.run_bash_command(cmd)
            print "client.%s-cinder has been created" % (self.user)

        if component == 'glance':

            cmd = "ceph auth get-or-create client.%s-glance mon 'allow r' osd " \
                  "'allow class-read object_prefix rbd_children, allow rwx pool=%s-glance'" % \
                  (self.user, self.user)
            self.run_bash_command(cmd)
            print "client.%s-glance has been created" % (self.user)

        if component == "cinder-backup":

            cmd = "ceph auth get-or-create client.%s-cinder-backup mon 'allow r' osd 'allow class-read " \
                  "object_prefix rbd_children, allow rwx pool=%s-cinder-backup'" % \
                  (self.user, self.user)
            self.run_bash_command(cmd)
            print "client.%s-cinder-backup has been created" % (self.user)

        self.close_ssh_connection()

    def get_keyring(self, component):
        self.open_ssh_connection()

        cmd = "ceph auth get client.%s-%s" % (self.user, component)
        keyring = self.run_bash_command(cmd)

        self.close_ssh_connection()
        return keyring

    def get_key(self, component):
        self.open_ssh_connection()

        cmd = "ceph auth get-key client.%s-%s" % (self.user, component)
        key = self.run_bash_command(cmd)

        self.close_ssh_connection()
        return key

    def get_ceph_conf(self):
        self.open_ssh_connection()

        cmd = "cat %s" % (self.ceph_conf_path)
        conf = self.run_bash_command(cmd)

        self.close_ssh_connection()
        return conf

class GlanceHost(Host):

    def __init__(self, params, hostname):
        Host.__init__(self, params, hostname)
        self.store = params.get('GLANCE', 'store')
        self.stores = params.get("GLANCE", 'stores')
        self.section = params.get("GLANCE", 'stores_section')
        self.chunk_size = params.get("GLANCE", 'rbd_store_chunk_size')
        self.show_direct_url = params.get("GLANCE", 'show_image_direct_url')
        self.enable_v1_api = params.get('GLANCE', 'enable_v1_api')
        self.enable_v2_api = params.get('GLANCE', 'enable_v2_api')
        self.packages = params.get('DEFAULT', 'ceph_packages')

#to do: add a check that if the file exists - don't do anything.
#       add the --run-over-keyrings flag
    def set_keyring(self, CephHost):

        keyring = CephHost.get_keyring('glance')

        self.open_ssh_connection()
        cmd = "echo -e \"" + keyring + "\" > /etc/ceph/ceph.client.%s-glance.keyring" % (self.user)

        self.run_bash_command(cmd)

        cmd = "chown glance:glance /etc/ceph/ceph.client.%s-glance.keyring" % (self.user)
        self.run_bash_command(cmd)

        self.close_ssh_connection()
        print "Glance's Ceph keyring is set"

    def set_ceph_conf_file(self, CephHost):

        ceph_conf = CephHost.get_ceph_conf()
        self.open_ssh_connection()

        cmd = "echo -e \"" + ceph_conf + "\" > /etc/ceph/ceph.conf"

        self.run_bash_command(cmd)

        self.close_ssh_connection()
        print "The Ceph configuration file has been set in the Glance host"

    def set_glance_conf(self):

        self.open_ssh_connection()

        cmd = "crudini --set /etc/glance/glance-api.conf %s stores %s" % \
              (self.section, self.stores)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/glance/glance-api.conf %s rbd_store_pool %s-glance" % \
              (self.section, self.user)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/glance/glance-api.conf %s rbd_store_user %s-glance" % \
              (self.section, self.user)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/glance/glance-api.conf %s rbd_store_ceph_conf %s" % \
              (self.section, self.ceph_conf_path)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/glance/glance-api.conf %s rbd_store_chunk_size %s " % \
              (self.section, self.chunk_size)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/glance/glance-api.conf %s stores \"%s \"" % (self.section, self.stores)

        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/glance/glance-api.conf %s show_image_direct_url %s" % \
              ("DEFAULT", self.show_direct_url)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/glance/glance-api.conf %s enable_v1_api %s" % \
              ("DEFAULT", self.enable_v1_api)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/glance/glance-api.conf %s enable_v2_api %s" % \
              ("DEFAULT", self.enable_v2_api)
        self.run_bash_command(cmd)

        self.close_ssh_connection()
        print "The Glance configuration has been changed"

class CinderHost(Host):


    def __init__(self, params, hostname):
        Host.__init__(self, params, hostname)
        self.backend_name = params.get('CINDER', 'backend_name')
        self.driver = params.get('CINDER', 'driver')
        self.rbd_flatten_volume_from_snapshot = params.get('CINDER', 'rbd_flatten_volume_from_snapshot')
        self.rbd_max_clone_depth = params.get('CINDER', 'rbd_max_clone_depth')
        self.rbd_store_chunk_size = params.get('CINDER', 'rbd_store_chunk_size')
        self.rados_connect_timeout = params.get('CINDER', 'rados_connect_timeout')
        self.glance_client_api = params.get('CINDER', 'glance_client_api')
        self.packages = params.get('DEFAULT', 'ceph_packages')


    def set_keyring(self, CephHost):

        keyring = CephHost.get_keyring('cinder')

        self.open_ssh_connection()
        cmd = "echo -e \"" + keyring + "\" > /etc/ceph/ceph.client.%s-cinder.keyring" % (self.user)

        self.run_bash_command(cmd)

        cmd = "chown cinder:cinder /etc/ceph/ceph.client.%s-cinder.keyring" % (self.user)
        self.run_bash_command(cmd)

        self.close_ssh_connection()
        print "Cinder's Ceph keyring is set"

    def set_ceph_conf_file(self, CephHost):

        ceph_conf = CephHost.get_ceph_conf()
        self.open_ssh_connection()

        cmd = "echo -e \"" + ceph_conf + "\" > /etc/ceph/ceph.conf"

        self.run_bash_command(cmd)

        self.close_ssh_connection()
        print "The Ceph configuration file has been set"

    def set_cinder_conf(self):

        self.open_ssh_connection()

        cmd = "crudini --set /etc/cinder/cinder.conf %s enabled_backends %s" % \
              ("DEFAULT", self.backend_name)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/cinder/cinder.conf %s glance_api_version %s" % \
              ("DEFAULT", self.glance_client_api)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/cinder/cinder.conf %s volume_driver %s" % \
              (self.backend_name, self.driver)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/cinder/cinder.conf %s rbd_pool %s-cinder" % \
              (self.backend_name, self.user)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/cinder/cinder.conf %s rbd_ceph_conf %s" % \
              (self.backend_name, self.ceph_conf_path)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/cinder/cinder.conf %s rbd_flatten_volume_from_snapshot %s" % \
              (self.backend_name, self.rbd_flatten_volume_from_snapshot)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/cinder/cinder.conf %s rbd_max_clone_depth %s" % \
              (self.backend_name, self.rbd_max_clone_depth)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/cinder/cinder.conf %s rbd_store_chunk_size %s" % \
              (self.backend_name, self.rbd_store_chunk_size)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/cinder/cinder.conf %s rados_connect_timeout %s" % \
              (self.backend_name, self.rados_connect_timeout)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/cinder/cinder.conf %s rbd_user %s-cinder" % \
              (self.backend_name, self.user)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/cinder/cinder.conf %s rbd_secret_uuid %s-cinder" % \
              (self.backend_name, self.uuid)
        self.run_bash_command(cmd)

        self.close_ssh_connection()
        print "The Cinder configuration has been changed"

class CinderBackupHost(Host):
    def __init__(self, params, hostname):

        Host.__init__(self, params, hostname)
        self.backup_driver = params.get('CINDER-BACKUP', 'backup_driver')
        self.backup_ceph_chunk_size = params.get('CINDER-BACKUP', 'backup_ceph_chunk_size')
        self.backup_ceph_stripe_unit = params.get('CINDER-BACKUP','backup_ceph_stripe_unit')
        self.backup_ceph_stripe_count = params.get('CINDER-BACKUP','backup_ceph_stripe_count')
        self.restore_discard_excess_bytes = params.get('CINDER-BACKUP','restore_discard_excess_bytes')
        self.packages = params.get('DEFAULT', 'ceph_packages')

    def set_keyring(self, CephHost):

        keyring = CephHost.get_keyring('cinder-backup')

        self.open_ssh_connection()
        cmd = "echo -e \"" + keyring + "\" > /etc/ceph/ceph.client.%s-cinder-backup.keyring" % (self.user)
        self.run_bash_command(cmd)

        cmd = "chown cinder:cinder /etc/ceph/ceph.client.%s-cinder-backup.keyring" % (self.user)
        self.run_bash_command(cmd)

        self.close_ssh_connection()
        print "Cinder-backup's keyring is set"

    def set_ceph_conf_file(self, CephHost):

        ceph_conf = CephHost.get_ceph_conf()
        self.open_ssh_connection()

        cmd = "echo -e \"" + ceph_conf + "\" > /etc/ceph/ceph.conf"

        self.run_bash_command(cmd)
        self.close_ssh_connection()
        print "The Ceph configuration file has been set"

    def set_cinder_backup_conf(self):

        self.open_ssh_connection()

        cmd = "crudini --set /etc/cinder/cinder.conf %s backup_driver %s" % \
              ("DEFAULT", self.backup_driver)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/cinder/cinder.conf %s backup_ceph_chunk_size %s" % \
              ("DEFAULT", self.backup_ceph_chunk_size)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/cinder/cinder.conf %s backup_ceph_stripe_unit %s" % \
              ("DEFAULT", self.backup_ceph_stripe_unit)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/cinder/cinder.conf %s  backup_ceph_stripe_count %s" % \
              ("DEFAULT", self.backup_ceph_stripe_count)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/cinder/cinder.conf %s restore_discard_excess_bytes %s" % \
              ("DEFAULT", self.restore_discard_excess_bytes)
        self.run_bash_command(cmd)

        self.close_ssh_connection()

        print "The Cinder-Backup configuration is set"

class NovaHost(Host):

    def __init__(self, params, hostname):
        Host.__init__(self, params, hostname)
        self.images_type = params.get('NOVA', 'images_type')
        self.inject_password = params.get('NOVA', 'inject_password')
        self.inject_key = params.get('NOVA', 'inject_key')
        self.inject_partition = params.get('NOVA', 'inject_partition')
        self.live_migration_flag = params.get('NOVA', 'live_migration_flag')
        self.secret_xml = "<secret ephemeral='no' private='no'>\n\t" \
                          "<uuid>%s</uuid>\n\t" \
                          "<usage type='ceph'>\n\t\t" \
                          "<name>client.%s-cinder secret</name>\n\t" \
                          "</usage>\n" \
                          "</secret>" % \
                          (self.uuid, self.user)
        self.packages = params.get('DEFAULT', 'ceph_packages')

    def set_keyring(self, CephHost):

        keyring = CephHost.get_keyring('cinder')

        self.open_ssh_connection()
        cmd = "echo -e \"" + keyring + "\" > /etc/ceph/ceph.client.%s-cinder.keyring" % (self.user)
        self.run_bash_command(cmd)

        self.close_ssh_connection()

    def set_ceph_conf_file(self, CephHost):

        ceph_conf = CephHost.get_ceph_conf()
        self.open_ssh_connection()

        cmd = "echo -e \"" + ceph_conf + "\" > /etc/ceph/ceph.conf"

        self.run_bash_command(cmd)
        self.close_ssh_connection()
        print "The Ceph configuration file has been set in %s" %(self.address)

    def set_libvirt_secret(self, CephHost):

        self.open_ssh_connection()

        cmd = "echo -e  \"" + self.secret_xml + "\" > ~/secret.xml"
        print cmd
        self.run_bash_command(cmd)

        cmd = "virsh secret-define --file ~/secret.xml"
        print cmd
        self.run_bash_command(cmd)

        key = CephHost.get_key('cinder')
        cmd = "virsh secret-set-value --secret %s --base64 %s" % (self.uuid, key)
        self.run_bash_command(cmd)

        self.close_ssh_connection()
        print "Libvirt secret value has been set"

    def set_user_setting(self):

        self.open_ssh_connection()

        cmd = "crudini --set /etc/nova/nova.conf %s rbd_user %s-cinder" % \
              ("libvirt", self.user)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/nova/nova.conf %s rbd_secret_uuid %s" % \
              ("libvirt", self.uuid)
        self.run_bash_command(cmd)

        self.close_ssh_connection()

    def set_nova_conf(self):

        self.open_ssh_connection()

        cmd = "crudini --set /etc/nova/nova.conf %s images_type %s" % \
              ("libvirt", self.images_type)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/nova/nova.conf %s images_rbd_pool %s-nova" % \
              ("libvirt", self.user)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/nova/nova.conf %s images_rbd_ceph_conf %s" % \
              ("libvirt", self.ceph_conf_path)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/nova/nova.conf %s inject_password %s" % \
              ("libvirt", self.inject_password)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/nova/nova.conf %s inject_key %s" % \
              ("libvirt", self.inject_key)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/nova/nova.conf %s inject_partition %s" % \
              ("libvirt", self.inject_partition)
        self.run_bash_command(cmd)

        cmd = "crudini --set /etc/nova/nova.conf %s live_migration_flag %s" % \
              ("libvirt", self.live_migration_flag)
        self.run_bash_command(cmd)


        self.close_ssh_connection()

