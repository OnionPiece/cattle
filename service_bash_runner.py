#!/bin/python2.7

import os
import subprocess

import service_config


GIT_CLONE = (
    "git clone ssh://%(user)s@review.polex.io:29418/openstack/%(proj)s "
    "/opt/%(proj)s && scp -p -P 29418 "
    "%(user)s@review.polex.io:hooks/commit-msg /opt/%(proj)s/.git/hooks/")
OWNER_CHANGE = "chown -R %(proj)s:%(proj)s /opt/%(proj)s"
UPDATE_PYTHON_PTH = (
    "grep %(proj)s -q /usr/lib/python2.7/site-packages/OS_repos.pth || "
    "echo '/opt/%(proj)s' >> /usr/lib/python2.7/site-packages/OS_repos.pth")
CHECKOUT_BRANCH = (
    'cd /opt/%(proj)s && git checkout %(branch)s')
CREATE_CONFIG_DIR = (
    'ls /etc/ | grep -q %(proj)s || mkdir /etc/%(proj)s')
GEN_CONFIG_BRANCH = (
    'cd /opt/%(proj)s && bash ./tools/generate_config_file_samples.sh '
    '--config-dir /etc/%(proj)s')

def bash_runner(cmd_file, cmds_str, check_return=False):
    if check_return:
        with open(cmd_file, 'w+') as f:
            f.write(cmds_str)
        cmd = subprocess.Popen('bash %s' % cmd_file, shell=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cmd.wait()
        os.remove(cmd_file)
        if cmd.returncode not in [0]:
            print ''.join(cmd.stdout.readlines() + cmd.stderr.readlines())
            os.sys.exit(1)
    else:
        with open(cmd_file, 'w+') as f:
            f.write(cmds_str)
        os.system('bash %s' % cmd_file)
        os.remove(cmd_file)


def get_common_conf(component, key):
    return service_config.load_conf(
        './common/%s.yaml' % component).get(component, {}).get(key)


def get_custom_conf(component, custom_file, key):
    return service_config.load_conf(custom_file).get(component, {}).get(key)


@service_config.log_call
def init_db(component, custom_file=None):
    "Init database for component"

    common_conf = get_common_conf(component, 'database') or {}
    custom_conf = get_custom_conf(component, custom_file, 'database') or {}
    name = custom_conf.get('name') or common_conf.get('name')
    user = custom_conf.get('user') or common_conf.get('user') or name
    password = custom_conf.get('password') or common_conf.get('password')

    if not (name and password):
        return

    cmds = """
        mysql -uroot -e "create database %(name)s"
        mysql -uroot -e "GRANT ALL PRIVILEGES ON %(name)s.* TO \
          '%(user)s'@'localhost' IDENTIFIED BY '%(password)s'"
        mysql -uroot -e "GRANT ALL PRIVILEGES ON %(name)s.* TO \
          '%(user)s'@'%%' IDENTIFIED BY '%(password)s'"
    """ % {'name': name, 'user': user, 'password': password}

    bash_runner("/root/create_%s_database" % name, cmds)


@service_config.log_call
def install_repos(component, custom_file=None):
    "Install repos for component"

    if not component.endswith('repo'):
        return

    gerrit_user_name = get_custom_conf('gerrit', custom_file, 'user_name')
    gerrit_use_repos = get_custom_conf(
        'gerrit', custom_file, 'use_repos') or []

    if gerrit_user_name and gerrit_use_repos:
        parent_component = component.split('-')[0].split('_')[0]
        if parent_component not in gerrit_use_repos:
            return

    common_repo = get_common_conf(component, 'gerrit_repo') or {}
    custom_repo = get_custom_conf(
        component, custom_file, 'gerrit_repo') or {}
    repo_name = custom_repo.get('name') or common_repo.get('name')
    repo_branch = custom_repo.get('branch') or common_repo.get('branch')

    cfg_data = {'user': gerrit_user_name, 'proj': repo_name,
                'branch': repo_branch}
    cmds = '\n'.join([
        cmd % cfg_data
        for cmd in (GIT_CLONE, OWNER_CHANGE, UPDATE_PYTHON_PTH,
                    CHECKOUT_BRANCH, CREATE_CONFIG_DIR, GEN_CONFIG_BRANCH)
        ])
    bash_runner("/root/install_%s_repos" % component, cmds)


@service_config.log_call
def install_packages(component, custom_file=None):
    "Install packages for component"

    gerrit_user_name = get_custom_conf('gerrit', custom_file, 'user_name')
    gerrit_use_repos = get_custom_conf(
        'gerrit', custom_file, 'use_repos') or []

    if gerrit_user_name and gerrit_use_repos:
        parent_component = component.split('-')[0].split('_')[0]
        if parent_component in gerrit_use_repos and not component.endswith(
                'repo'):
            return

    common_pkgs = get_common_conf(component, 'packages') or []
    custom_pkgs = get_custom_conf(component, custom_file, 'packages') or []

    if common_pkgs or custom_pkgs:
        cmds = '\n'.join([
            "rpm -q %s || yum install -y %s" % (pkg, pkg)
            for pkg in common_pkgs + custom_pkgs])
        bash_runner("/root/install_%s_packages" % component, cmds)
        cmds = '\n'.join([
            "rpm -q %s" % pkg
            for pkg in common_pkgs + custom_pkgs])
        bash_runner("/root/check_install_%s_packages" % component, cmds, True)


def _run_commands(component, is_post, custom_file=None):
    stage = is_post and 'post' or 'pre'
    common_cmds = get_common_conf(component, stage + '_commands') or []
    custom_cmds = get_custom_conf(
        component, custom_file, stage + '_commands') or []

    if not isinstance(common_cmds, list):
        common_cmds = [common_cmds]
    if not isinstance(custom_cmds, list):
        custom_cmds = [custom_cmds]

    if not (common_cmds or custom_cmds):
        return

    cmds = '\n'.join(common_cmds + custom_cmds)
    bash_runner("/root/run_%s_%s_commands" % (component, stage), cmds)


@service_config.log_call
def run_pre_commands(component, custom_file=None):
    "Run pre_commands for component"

    _run_commands(component, False, custom_file)


@service_config.log_call
def run_post_commands(component, custom_file=None):
    "Run post_commands for component"

    _run_commands(component, True, custom_file)


@service_config.log_call
def start_service(component, custom_file=None):
    "Start component service"

    common_svcs = get_common_conf(component, 'services') or []
    custom_svcs = get_custom_conf(component, custom_file, 'services') or []

    if not (common_svcs or custom_svcs):
        return

    cmds = '\n'.join([
        "systemctl enable %s\nsystemctl restart %s" % (svc, svc)
        for svc in common_svcs + custom_svcs])
    bash_runner("/root/start_%s_services" % component, cmds)
