#!/usr/bin/env python3.11
"""
           NAME: smol-k8s-lab
    DESCRIPTION: Works with k3s and KinD
         AUTHOR: jessebot(AT)linux(d0t)com
        LICENSE: GNU AFFERO GENERAL PUBLIC LICENSE
"""

from click import option, argument, command, Choice
import logging
from os import path
from pathlib import Path
from rich.panel import Panel
from rich.logging import RichHandler
from sys import exit

# custom libs and constants
from .k8s_tools.argocd import install_with_argocd
from .console_logging import CONSOLE, header, sub_header
from .constants import (XDG_CACHE_DIR, KUBECONFIG, HOME_DIR, DEFUALT_CONFIG,
                        INITIAL_USR_CONFIG, VERSION)
from .env_config import check_os_support, process_app_configs
from .help_text import RichCommand, options_help


HELP = options_help()
HELP_SETTINGS = dict(help_option_names=['-h', '--help'])
SUPPORTED_DISTROS = ['k0s', 'k3s', 'kind']
# process all of the config file, or create a new one and also grab secrets
USR_CFG, SECRETS = process_app_configs(DEFUALT_CONFIG, INITIAL_USR_CONFIG)


def setup_logger(level="", log_file=""):
    """
    Sets up rich logger for the entire project.
    (ᐢ._.ᐢ) <---- who is he? :3
    Returns logging.getLogger("rich")
    """
    # determine logging level
    if not level:
        level = USR_CFG['log']['level']

    log_level = getattr(logging, level.upper(), None)

    # these are params to be passed into logging.basicConfig
    opts = {'level': log_level, 'format': "%(message)s", 'datefmt': "[%X]"}

    # we only log to a file if one was passed into config.yaml or the cli
    if not log_file:
        log_file = USR_CFG['log'].get('file', None)

    # rich typically handles much of this but we don't use rich with files
    if log_file:
        opts['filename'] = log_file
        opts['format'] = "%(asctime)s %(levelname)s %(funcName)s: %(message)s"
    else:
        rich_handler_opts = {'rich_tracebacks': True}
        # 10 is the DEBUG logging level int value
        if log_level == 10:
            # log the name of the function if we're in debug mode :)
            opts['format'] = "[bold]%(funcName)s()[/bold]: %(message)s"
            rich_handler_opts['markup'] = True
        else:
            rich_handler_opts['show_path'] = False
            rich_handler_opts['show_level'] = False

        opts['handlers'] = [RichHandler(**rich_handler_opts)]

    # this uses the opts dictionary as parameters to logging.basicConfig()
    logging.basicConfig(**opts)

    if log_file:
        return logging
    else:
        return logging.getLogger("rich")


def install_k8s_distro(k8s_distro=""):
    """
    Install a specific distro of k8s
    Takes one variable:
        k8s_distro - string. options: 'k0s', 'k3s', or 'kind'
    Returns True
    """
    if k8s_distro == "kind":
        from .k8s_distros.kind import install_kind_cluster
        install_kind_cluster()
    elif k8s_distro == "k3s":
        from .k8s_distros.k3s import install_k3s_cluster
        extra_args = USR_CFG.get('extra_args', [])
        install_k3s_cluster(extra_args)
    elif k8s_distro == "k0s":
        from .k8s_distros.k0s import install_k0s_cluster
        install_k0s_cluster()
    return True


def delete_cluster(k8s_distro="k3s"):
    """
    Delete a k0s, k3s, or KinD cluster entirely.
    It is suggested to perform a reboot after deleting a k0s cluster.
    """
    header(f"Bye bye, [b]{k8s_distro}[/b]!")

    if k8s_distro == 'k3s':
        from .k8s_distros.k3s import uninstall_k3s
        uninstall_k3s()

    elif k8s_distro == 'kind':
        from .k8s_distros.kind import delete_kind_cluster
        delete_kind_cluster()

    elif k8s_distro == 'k0s':
        from .k8s_distros.k0s import uninstall_k0s
        uninstall_k0s()

    else:
        header("┌（・o・）┘≡З  Whoops. {k8s_distro} not YET supported.")

    sub_header("[grn]◝(ᵔᵕᵔ)◜ Success![/grn]")
    exit()


# an ugly list of decorators, but these are the opts/args for the whole script
@command(cls=RichCommand, context_settings=HELP_SETTINGS)
@argument("k8s", metavar="<k0s, k3s, kind>", default="")
@option('--config', '-c', metavar="CONFIG_FILE", type=str,
        default=path.join(HOME_DIR, '.config/smol-k8s-lab/config.yaml'),
        help=HELP['config'])
@option('--delete', '-D', is_flag=True, help=HELP['delete'])
@option('--setup', '-s', is_flag=True, help=HELP['setup'])
@option('--k9s', '-K', is_flag=True, help=HELP['k9s'])
@option('--log_level', '-l', metavar='LOGLEVEL', help=HELP['log_level'],
        type=Choice(['debug', 'info', 'warn', 'error']))
@option('--log_file', '-o', metavar='LOGFILE', help=HELP['log_file'])
@option('--password_manager', '-p', is_flag=True,
        help=HELP['password_manager'])
@option('--version', '-v', is_flag=True, help=HELP['version'])
def main(k8s: str = "",
         config: str = "",
         delete: bool = False,
         setup: bool = False,
         k9s: bool = False,
         log_level: str = "",
         log_file: str = "",
         password_manager: bool = False,
         version: bool = False):
    """
    Quickly install a k8s distro for a homelab setup. Installs k3s
    with metallb, ingess-nginx, cert-manager, and argocd
    """
    # only return the version if --version was passed in
    if version:
        print(f'\n🎉 v{VERSION}\n')
        return True

    # setup logging immediately
    log = setup_logger(log_level, log_file)
    log.debug("Logging configured.")

    # make sure this OS is supported
    check_os_support()

    if setup:
        # installs extra tooling such as helm, k9s, and krew
        from .setup_k8s_tools import do_setup
        do_setup()
        if not k8s:
            exit()

    # make sure we got a valid k8s distro
    if k8s not in SUPPORTED_DISTROS:
        CONSOLE.print(f'\n☹ Sorry, "[b]{k8s}[/]" is not a currently supported '
                      'k8s distro. Please try again with any of '
                      f'{SUPPORTED_DISTROS}.\n')
        exit()

    if delete:
        # exits the script after deleting the cluster
        delete_cluster(k8s)

    # make sure the cache directory exists (typically ~/.cache/smol-k8s-lab)
    Path(XDG_CACHE_DIR).mkdir(exist_ok=True)

    argo_enabled = USR_CFG['argocd']['enabled']

    # install the actual KIND, k0s, or k3s cluster
    header(f'Installing [green]{k8s}[/] cluster.')
    sub_header('This could take a min ʕ•́  ̫•̀ʔっ♡ ', False)
    install_k8s_distro(k8s, USR_CFG['k3s']['extra_args'])

    # make sure helm is installed and the repos are up to date
    from .k8s_tools.homelabHelm import prepare_helm
    prepare_helm(k8s, USR_CFG['metallb']['enabled'])

    # needed for metal (non-cloud provider) installs
    if USR_CFG['metallb']['enabled']:
        header("Installing [b]metallb[/b] so we have an ip address pool")
        from .k8s_apps.metallb import configure_metallb
        configure_metallb(USR_CFG['metallb']['address_pool'])

    # ingress controller: so we can accept traffic from outside the cluster
    header("Installing [b]ingress-nginx-controller[/b]...")
    from .k8s_apps.nginx_ingress_controller import configure_ingress_nginx
    configure_ingress_nginx(k8s)

    # manager SSL/TLS certificates via lets-encrypt
    header("Installing [b]cert-manager[/b] for TLS certificates...")
    from .k8s_apps.cert_manager import configure_cert_manager
    configure_cert_manager(USR_CFG['cert-manager']['email'])

    # kyverno: kubernetes native policy manager
    if USR_CFG['kyverno']['enabled']:
        install_with_argocd('kyverno', USR_CFG['kyverno']['argo'])

    # keycloak: self hosted IAM 
    if USR_CFG['keycloak']['enabled']:
        install_with_argocd('keycloak', USR_CFG['keycloak']['argo'])

    # 🦑 Install Argo CD: continuous deployment app for k8s
    if USR_CFG['argo_cd']['enabled']:
        # user can configure a special domain for argocd
        argocd_fqdn = USR_CFG['argo_cd']['domain']
        from .k8s_apps.argocd import configure_argocd
        configure_argocd(argocd_fqdn, password_manager)

    # we're done :D
    print("")
    CONSOLE.print(Panel("\nSmol K8s Lab completed!\n\nMake sure you run:\n"
                        f"[b]export KUBECONFIG={KUBECONFIG}\n",
                        title='[green]◝(ᵔᵕᵔ)◜ Success!',
                        subtitle='♥ [cyan]Have a nice day[/] ♥',
                        border_style="cornflower_blue"))
    print("")


if __name__ == '__main__':
    main()
