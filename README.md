# A simple script tool to deploy OpenStack dev/test environment.
Followed https://docs.openstack.org/mitaka/install-guide-rdo/.

## HOW TO RUN
1. git clone this.
2. cd cattle
3. edit custom.yaml by setting your controller IP
4. python start.py ROLE custom.yaml
   ROLE can be: controller, network, compute
   

## SUPPORTS
Go check SUPPORT_LIST


## LIMITATION
0. all passwords are "password", not matter for MQ, DB, keystone...
1. eth0 will be considered as management network NIC
2. eth1 will be considered as data network NIC (SDN)
3. For node who will run neutron-vpn-agent, eth2 will be considered as
   external network NIC
4. to make things simple, mysql_secure_installation is skipped.
  https://stackoverflow.com/questions/20760908/
    what-is-purpose-of-using-mysql-secure-installation
5. MultiStrOpts doesn't get good support. Check below *MultiStrOpts* sub-section.
6. Need at least 2 network nodes if you need Neutron L3 and above services.


### ROLES
You can find roles definations in common/roles.yaml. Each items under a role are
some other yamls also under common folder, like hosts for common/hosts.yaml, and
db for common/db.yaml. Items under a role will run in list order.

Items under a role have works such as installing packages for services,
intiliaze database, config configurations, running some commands. Each work
should appear only once in a role.
The running order of actions is:
 - installing packages
 - initialize database
 - setting configurations
 - running commands need to be executed before service get started
 - enabling and starting service
 - running commands need to be exected after service get started
 

## YAML file defination
--- Format for AN_ITEM_CALLED_IN_A_ROLE.yaml ---
# file name: AN_ITEM_CALLED_IN_A_ROLE.yaml
AN_ITEM_CALLED_IN_A_ROLE:
    conf:
        file: /etc/xxx/yyy.conf  # conf file path to config
        sep: ' '  # seperator(e.g. ' ') to be used, '=' is default
        type: 'raw'  # 'raw': directly use given data in *options* to cover
                     # target file;
                     # 'no_section': consider data in *options* are key pairs
                     # but with no section;
                     # leave this out, consider data in *options* are key pairs
                     # with secions, like most OpenStack configuration options.
        options:
            DEFAULT:
                opt_1: single_value
                opt_2:
                    - list_value_1
                    - list_value_2
            another_section:
                opt_1: some_value
                ...
        (or)
        options: |  # need type is 'raw'
            CONSIDER_THIS_PARAGRAPH_ARE_CONTENT_TO_BE_WRITTEN_IN_TARGET_FILE
            ANOTHER_LINE_TO_WRITE
            FINAL_LINE
    database:
        name: database_name
        user: username_to_access_database # you can leave this out if it's same
                                          # to *name*
        password: database_password
    packages:
        - package_1 to be installed
        - package_2 to be installed
        - ...
    pre_commands:
        - command 1 need to be run before service get started
        - command 2
        - ...
      (or)
    pre_commands: |
        command-1
        ...
    services:
        - service name to be start
        - another service to be start
    post_commands:
        - command 1
        - command 2
        - ...
      (or)
    post_commands:
        - command 1
        - ...

--- pre_commands and post_commands ---
Those commands will be written into a bash file, then that bash file will be
executed. So, it's possible to run pre or post commands like:
  source /root/admin_openrc
  openstack service create ....
  ...

--- MultiStrOpts ---
E.g. neutron has options provider_services, like:
  [service_providers]
  service_provider=VPN:strongswan:neutron_vpnaas.services.vpn.service_drivers.\
    ipsec.IPsecVPNDriver:default
  service_provider=FIREWALL:Iptables:neutron.agent.linux.iptables_firewall.\
    OVSHybridIptablesFirewallDriver:default
  service_provider=VPN:Openvpn:neutron_vpnaas.services.vpn.service_drivers.\
    openvpn.OpenVPNDriver
  service_provider=LOADBALANCERV2:Haproxy:neutron_lbaas.drivers.haproxy.\
    plugin_driver.HaproxyOnHostPluginDriver:default
doesn't get supported yet. A workaround is using pre_commands. E.g.:
    ...
    conf:
        service_providers:
            service_provider: VPN:...
            fw_service_provider: FIREWALL:...
            openvpn_service_provider: VPN:...
            lb_service_provider: LOADBALANCERV2:...
        ...
    pre_commands:
        - sed -i 's/^fw_service_provider = /service_provider = /g' \
            /etc/neutron/neutron.conf
        - sed -i 's/^openvpn_service_provider = /service_provider = /g' \
            /etc/neutron/neutron.conf
        - sed -i 's/^lb_service_provider = /service_provider = /g'
            /etc/neutron/neutron.conf
            

### custom.yaml ###
Custom.yaml is used to do some custom definations if the default ones under
common is not enough to use, like controller IP in custom.
You can add custom data for multiple items, e.g.:
  hosts:
      ...
  yum:
      ...
and yes, keep in the same format as ones under common folder.
For *conf*, it has behavior like common_data_dict.update(custom_data_dict),
and for *services*, *packages*, *pre_commands*, *post_commands*, the behavior
is common_data_or_op_list.extend(custom_data_or_op_list). *database* is not
supported yet.
