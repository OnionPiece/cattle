#!/bin/python

import service_bash_runner as runner
import service_config as config


def build_for_role(role, custom_file=None):
    role_items = config.load_conf('./common/roles.yaml').get(role, [])
    for item in role_items:
        runner.install_repos(item, custom_file)
        runner.install_packages(item, custom_file)
        runner.init_db(item, custom_file)
        config.config_component(item, custom_file)
        runner.run_pre_commands(item, custom_file)
        runner.start_service(item, custom_file)
        runner.run_post_commands(item, custom_file)


if __name__ == '__main__':
    import sys
    role = len(sys.argv) >= 2 and sys.argv[1]
    custom_file = len(sys.argv) == 3 and sys.argv[2]
    build_for_role(role, custom_file)
