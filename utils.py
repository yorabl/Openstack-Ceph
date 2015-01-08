__author__ = 'yrabl'

import ConfigParser
from hosts import CephHost
from hosts import CinderBackupHost
from hosts import CinderHost
from hosts import GlanceHost
from hosts import NovaHost

def getConfig(configFile):
    params = ConfigParser.ConfigParser()
    params.read(configFile)

    return params

def findHostRole(params, role):
    hosts = []

    for host in params.get('DEFAULT', 'host_names').split("," " "):

        if (params.get(host, 'role')) == role:
            hosts.append(host)
    return hosts

def check_ceph_host(params):
    ceph_host = findHostRole(params, 'ceph')

    if len(ceph_host) == 0:
        stderr = "ERROR: there is no Ceph server in the configuration file"
        print stderr
        exit()
    else:
        return ceph_host

