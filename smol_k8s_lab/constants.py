#!/usr/bin/env python3.11
"""
NAME: constants.py
DESC: everything to do with initial configuration of a new environment
"""

from getpass import getuser
from importlib.metadata import version as get_version
from os import environ, path, uname, makedirs
from pathlib import Path
from ruamel.yaml import YAML
from shutil import copyfile
from xdg_base_dirs import xdg_cache_home, xdg_config_home

# env
SYSINFO = uname()
# this will be something like ('Darwin', 'x86_64')
OS = (SYSINFO.sysname, SYSINFO.machine)

HOME_DIR = environ["HOME"]
USER = getuser()

# pathing
PWD = path.dirname(__file__)

# for smol-k8s-lab configs and cache
XDG_CACHE_DIR = path.join(xdg_cache_home(), 'smol-k8s-lab')
# make sure the cache directory exists (typically ~/.cache/smol-k8s-lab)
Path(XDG_CACHE_DIR).mkdir(exist_ok=True)
XDG_CONFIG_DIR = path.join(xdg_config_home(), 'smol-k8s-lab')
XDG_CONFIG_FILE = path.join(xdg_config_home(), 'smol-k8s-lab/config.yaml')

# for specifically the kubeconfig file
XDG_KUBE_FILE = path.join(xdg_config_home(), 'kube/config')
# default to ~/.config/kube/config if no KUBECONFIG or XDG_CONFIG set
KUBECONFIG = environ.get("KUBECONFIG", XDG_KUBE_FILE)
KUBE_DIR = path.dirname(KUBECONFIG)
# create the directory if it doesn't exist
Path(KUBE_DIR).mkdir(exist_ok=True)

# version of smol-k8s-lab
VERSION = get_version('smol-k8s-lab')
# grabs the default packaged config file from default dot files
DEFAULT_CONFIG_FILE = path.join(PWD, 'config/default_config.yaml')

def load_yaml(yaml_config_file=XDG_CONFIG_FILE):
    """
    load config yaml files for smol-k8s-lab and return as dicts
    """
    # create default pathing and config file if it doesn't exist
    if not path.exists(yaml_config_file):
        Path(XDG_CONFIG_DIR).mkdir(parents=True, exist_ok=True)
        copyfile(DEFAULT_CONFIG_FILE, XDG_CONFIG_FILE)

    yaml = YAML()
    # open the yaml config file and then return the dict
    with open(yaml_config_file, 'r') as yaml_file:
        return yaml.load(yaml_file)


DEFAULT_CONFIG = load_yaml(DEFAULT_CONFIG_FILE)
INITIAL_USR_CONFIG = load_yaml()

# sets the default speech files and loads them for each language
# if you don't see your language, please submit a PR :)
SPEECH_TEXT = path.join(PWD, 'config/audio')

# we default save all generated speech files to your XDG_DATA_HOME env var
SPEECH_MP3_DIR = path.join(PWD, 'audio')
if not path.exists(SPEECH_MP3_DIR):
    makedirs(SPEECH_MP3_DIR, exist_ok=True)

DEFAULT_DISTRO_OPTIONS = DEFAULT_CONFIG['k8s_distros']

if 'Darwin' in OS[0]:
    # macOS can't run k3s yet
    DEFAULT_DISTRO_OPTIONS.pop('k3s')
    DEFAULT_DISTRO = 'kind'
else:
    DEFAULT_DISTRO = 'k3s'

DEFAULT_APPS = DEFAULT_CONFIG['apps']
