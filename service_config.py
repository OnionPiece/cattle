#!/bin/python2.7

import collections
import os
import six
import time
import yaml


SECTION_HOLDER = 'section_holder'
EQUAL_SEP = '='
LINES = 'lines'
OPTIONS = 'options'
COMMENTED_OPTIONS = 'commented_options'

RAW_TYPE = 'raw'
NO_SECTION_TYPE = 'no_section'


def load_conf(filename=None):
    ret = {}
    if filename and os.path.exists(filename):
        with open(filename) as f:
            ret.update(yaml.safe_load(f) or {})
    return ret


def load_target_file(filename, sep='=', with_section=True, multi_value=False):
    if not os.path.exists(filename):
        return {}
    file_data = collections.OrderedDict()
    current_section = None
    inner_index = 0
    if not with_section:
        current_section = SECTION_HOLDER
        file_data[current_section] = {
            LINES: [],
            OPTIONS: {},
            COMMENTED_OPTIONS: {}
        }

    for line in open(filename, 'r').readlines():
        line = line.strip()
        if not line:
            if current_section:
                file_data[current_section][LINES].append(line)
                inner_index += 1
            continue

        if line[0] == '[' and line[-1] == ']':
            current_section = line[1: -1]
            file_data[current_section] = {
                LINES: [line],
                OPTIONS: {},
                COMMENTED_OPTIONS: {}
            }
            inner_index = 1
        else:
            if sep == EQUAL_SEP:
                if sep in line:
                    opt = line.split('=')[0].strip()
                    if opt[0] == '#':
                        file_data[current_section][COMMENTED_OPTIONS].update(
                            {'# %s' % opt[1:].strip(): inner_index})
                    else:
                        file_data[current_section][OPTIONS].update(
                            {opt: inner_index})
            else:
                if line[0] != '#' and line[0] != '<' and line[-1] != '>':
                    fields = line.split()
                    if len(fields) == 2 or multi_value:
                        file_data[current_section][OPTIONS].update(
                            {fields[0]: inner_index})
                    else:
                        # we are not goint handle this
                        pass
            file_data[current_section][LINES].append(line)
            inner_index += 1
    return file_data


def update_key_pair_options(target_data, sep, new_options):
    for section in new_options:
        if section in target_data:
            for key, value in six.iteritems(new_options[section]):
                if isinstance(value, list):
                    line_data = '%s %s %s' % (key, sep, ','.join(value))
                elif value:
                    line_data = '%s %s %s' % (key, sep, value)
                else:
                    line_data = key
                target_line = target_data[section][OPTIONS].get(key, 0)
                target_line = target_line or (
                    target_data[section][COMMENTED_OPTIONS].get(
                        '# %s' % key, 0))
                if target_line:
                    target_data[section][LINES][target_line] = line_data
                else:
                    target_data[section][LINES].insert(-2, '')
                    target_data[section][LINES].insert(-2, line_data)
        else:
            if target_data:
                target_data.setdefault(section, {LINES: ['', '']})
            else:
                target_data.setdefault(section, {LINES: []})
            target_data[section][LINES].extend(['[%s]' % section, ''])
            target_data[section][LINES].extend([
                '%s %s %s\n' % (
                    key, value and sep or '',
                    isinstance(value, list) and ','.join(value) or value or '')
                for key, value in six.iteritems(new_options[section])])
    return '\n'.join(['\n'.join(section[LINES])
                      for section in six.itervalues(target_data)])


def update_no_section_key_pair_options(target_data, options_sep, new_options):
    for option, value in six.iteritems(new_options):
        line_data = '%s %s %s' % (option, options_sep, value)
        if option in target_data[SECTION_HOLDER][OPTIONS]:
            target_line = target_data[SECTION_HOLDER][OPTIONS].get(option, -1)
            if target_line >= 0:
                target_data[SECTION_HOLDER][LINES][target_line] = line_data
            else:
                target_data[SECTION_HOLDER][LINES].append(line_data)
        else:
            target_data[SECTION_HOLDER][LINES].append(line_data)
    return '\n'.join(target_data[SECTION_HOLDER][LINES])


def set_conf_file(target_file, options_type, options_sep, new_settings,
                  file_mod):
    options_sep = options_sep or '='
    options_type = options_type
    file_mod = file_mod and int(file_mod, 8) or 0o644

    data = ''
    if options_type == RAW_TYPE:
        data = new_settings
    elif options_type == NO_SECTION_TYPE:
        target_data = load_target_file(target_file, sep=options_sep,
                                       with_section=False, multi_value=True)
        data = update_no_section_key_pair_options(
            target_data, options_sep, new_settings)
    else:
        target_data = load_target_file(target_file)
        data = update_key_pair_options(target_data, options_sep, new_settings)

    tmp_file = target_file + '.tmp'
    with open(tmp_file, 'w+') as f:
        f.write(data)
    os.chmod(tmp_file, file_mod)
    if os.path.exists(target_file):
        os.rename(target_file,
                  '%s-%s' % (target_file,
                             time.strftime('%Y%m%d-%H%M%S', time.gmtime())))
    os.rename(tmp_file, target_file)


def log_call(func, *args):
    def wrap(*args):
        print '=' * 60
        print '%s is calling for %s' % (func.__doc__, args[0])
        func(*args)
        print '%s finished calling with %s' % (func.__doc__, args[0])
        print '=' * 60
    return wrap


@log_call
def config_component(component, custom_conf_file=None):
    """Handle component configuration"""

    common_conf = load_conf('./common/%s.yaml' % component).get(
        component, {}).get('conf', {})
    custom_conf = load_conf(custom_conf_file).get(component, {}).get(
        'conf', {})
    if not (common_conf or custom_conf):
        return

    target_file = custom_conf.get('file') or common_conf['file']
    options_sep = custom_conf.get('sep') or common_conf.get('sep')
    options_type = custom_conf.get('type') or common_conf.get('type')
    file_mod = custom_conf.get('file_mod') or common_conf.get('file_mod')
    new_settings = common_conf.get('options', {})
    if options_type == RAW_TYPE:
        new_settings = custom_conf.get('options') or common_conf.get(
            'options', '')
    else:
        for section, opts in six.iteritems(custom_conf.get('options', {})):
            if section in new_settings:
                new_settings.update(opts)
            else:
                new_settings[section] = opts
    set_conf_file(target_file, options_type, options_sep, new_settings,
                  file_mod)
