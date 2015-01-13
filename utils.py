__author__ = 'yrabl'

import ConfigParser


def get_config(config_file):
    params = ConfigParser.ConfigParser()
    params.read(config_file)

    return params


def find_host_role(params, role):
    hosts = []

    for host in params.get('DEFAULT', 'host_names').split("," " "):

        if (params.get(host, 'role')) == role:
            hosts.append(host)
    return hosts


def check_ceph_host(params):
    ceph_host = find_host_role(params, 'ceph')

    if len(ceph_host) == 0:
        stderr = "ERROR: there is no Ceph server in the configuration file"
        print stderr
        exit()
    else:
        return ceph_host


def print_help():
    man = "usage: set-ceph.py \t\t[<configuration file>]\n" \
          "\t\t[--delete--pools <component> <component>...]\n" \
          "\t\t[--reset-pools]" \
          "Optional arguments: \n" \
          "\t --delete--pools <component>...\n" \
          "\t --reset-pools"

    print man