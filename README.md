Overview
---------
This little tool connects to each server and set it up according to its role.
All the hosts configuration and other settings are in the config.ini, to change them edit the file.

The Ceph role:
(1) Connecting to the Ceph server
(2) Creating the pools
(3) Creating the Ceph client
Note: if there's a Ceph client with the name already exists the settings will not change.
That client should be deleted before running the Set Ceph.

The Openstack roles:
(1) Installing the Ceph's client packages
(2) Copying the Ceph client keyring and the Ceph configuration file to the server
(3) Setting the parameters in the configuration file according to the role: cinder/glance/nova.conf
(4) Restart the service

How to use:

run the command:
python set_ceph.py [configuration file] [--delete-pools <component>] [--reset-pools <component> ]

components are:
- cinder
- glance
- cinder-backup
- nova
