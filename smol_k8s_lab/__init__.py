#!/usr/bin/env python3.11
"""
           NAME: smol-k8s-lab
    DESCRIPTION: Works with k3s and KinD (k0s and k3d are experimental)
         AUTHOR: jessebot(AT)linux(d0t)com
        LICENSE: GNU AFFERO GENERAL PUBLIC LICENSE
"""

from click import option, command
import logging
from os import path
from rich.logging import RichHandler
from rich.panel import Panel
from sys import exit

# custom libs and constants
from .env_config import check_os_support, process_configs
from .constants import KUBECONFIG, HOME_DIR, INITIAL_USR_CONFIG, VERSION
from .k8s_tools.argocd_util import install_with_argocd
from .k8s_tools.k8s_lib import K8s
from .k8s_distros.base import create_k8s_distro, delete_cluster
from .k8s_apps.base_install import install_base_apps
from .k8s_apps.oidc import setup_oidc_provider
from .k8s_apps.infisical import configure_infisical
from .k8s_apps.external_secrets_operator import configure_external_secrets
from .k8s_apps.federated import (configure_nextcloud, configure_matrix,
                                 configure_mastodon)
from .pretty_printing.console_logging import CONSOLE, sub_header, header
from .pretty_printing.help_text import RichCommand, options_help
from .utils.bw_cli import BwCLI
HELP = options_help()
HELP_SETTINGS = dict(help_option_names=['-h', '--help'])


def process_log_config(log_dict: dict = {'log':
                                         {'level': 'warn', 'file': None}}):
    """
    Sets up rich logger for the entire project. (ᐢ._.ᐢ) <---- who is he? :3
    Returns logging.getLogger("rich")
    """
    # determine logging level
    level = log_dict.get('level', 'warn')
    log_level = getattr(logging, level.upper(), None)

    # these are params to be passed into logging.basicConfig
    opts = {'level': log_level, 'format': "%(message)s", 'datefmt': "[%X]"}

    # we only log to a file if one was passed into config.yaml
    # determine logging level
    log_file = log_dict.get('file', None)

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


# an ugly list of decorators, but these are the opts/args for the whole script
@command(cls=RichCommand, context_settings=HELP_SETTINGS)
@option('--config', '-c', metavar="CONFIG_FILE", type=str,
        default=path.join(HOME_DIR, '.config/smol-k8s-lab/config.yaml'),
        help=HELP['config'])
@option('--delete', '-D', is_flag=True, help=HELP['delete'])
@option('--setup', '-s', is_flag=True, help=HELP['setup'])
@option('--k9s', '-K', is_flag=True, help=HELP['k9s'])
@option('--version', '-v', is_flag=True, help=HELP['version'])
def main(config: str = "",
         delete: bool = False,
         setup: bool = False,
         k9s: bool = False,
         log_file: str = "",
         version: bool = False):
    """
    Quickly install a k8s distro for a homelab setup. Installs k3s
    with metallb, ingess-nginx, cert-manager, and argocd
    """
    # only return the version if --version was passed in
    if version:
        print(f'\n🎉 v{VERSION}\n')
        return True

    if setup:
        # installs required/extra tooling: kubectl, helm, k9s, argocd, krew
        from .utils.setup_k8s_tools import do_setup
        do_setup()

    # make sure this OS is supported
    check_os_support()

    # process all of the config file, or create a new one and also grab secrets
    USR_CFG, SECRETS = process_configs(INITIAL_USR_CONFIG, delete)

    # setup logging immediately
    log = process_log_config(USR_CFG['log'])
    log.debug("Logging configured.")

    k8s_distros = USR_CFG['k8s_distros']
    if delete:
        logging.debug("Cluster deletion was requested")
        for distro, metadata in k8s_distros.items():
            if metadata.get('enabled', False):
                # exits the script after deleting the cluster
                delete_cluster(distro)
        exit()

    bw = None
    # if we're using bitwarden, unlock the vault
    pw_manager_enabled = USR_CFG['local_password_manager']['enabled']
    pw_manager = USR_CFG['local_password_manager']['name']
    if pw_manager_enabled and pw_manager == 'bitwarden':
        bw = BwCLI(USR_CFG['local_password_manager']['overwrite'])
        bw.unlock()

    for distro, metadata in k8s_distros.items():
        # if the cluster isn't enabled, just continue on
        if not k8s_distros[distro].get('enabled', False):
            continue
        # this is a dict of all the apps we can install
        apps = USR_CFG['apps']
        # check immediately if metallb is enabled
        metallb_enabled = apps['metallb']['enabled']

        # install the actual KIND, k0s, k3s, or k3d (experimental) cluster
        create_k8s_distro(distro, metadata, metallb_enabled)

        argo_enabled = apps['argo_cd']['enabled']

        k8s_obj = K8s()

        # installs all the base apps: metallb, ingess-nginx, and cert-manager
        install_base_apps(k8s_obj, distro, apps['metallb'], apps['cert-manager'],
                          argo_enabled, apps['argo_cd_appset_secret_plugin']['enabled'])

        # 🦑 Install Argo CD: continuous deployment app for k8s
        if argo_enabled:
            # user can configure a special domain for argocd
            argocd_fqdn = SECRETS['argo_cd_hostname']
            from .k8s_apps.argocd import configure_argocd
            configure_argocd(k8s_obj, argocd_fqdn, bw,
                             apps['argo_cd_appset_secret_plugin']['enabled'],
                             SECRETS)

            # setup bitwarden external secrets if we're using that
            if apps['external_secrets_operator']['enabled']:
                eso = apps.pop('external_secrets_operator')
                bitwarden_eso_provider = apps.pop('bitwarden_eso_provider')
                configure_external_secrets(k8s_obj, eso['argo'],
                                           bitwarden_eso_provider, distro, bw)

            # setup infisical - an secrets manager and operator for k8s
            if apps['infisical']['enabled']:
                infisical = apps.pop('infisical')
                configure_infisical(k8s_obj, infisical)

            # header("Setting up OIDC/Oauth applications")
            # vouch doesn't need to be installed below, as it's installed here
            vouch = apps.pop('vouch')
            keycloak = apps.pop('keycloak')
            zitadel = apps.pop('zitadel')

            # setup keycloak if we're using that for OIDC
            if keycloak['enabled']:
                setup_oidc_provider(k8s_obj, 'keycloak', keycloak, vouch, bw)
            # setup zitadel if we're using that for OIDC
            elif zitadel['enabled']:
                setup_oidc_provider(k8s_obj, 'zitadel', zitadel, vouch, bw, argocd_fqdn)

            if apps['nextcloud']['enabled']:
                nextcloud = apps.pop('nextcloud')
                configure_nextcloud(k8s_obj, nextcloud, bw)

            if apps['mastodon']['enabled']:
                mastodon = apps.pop('mastodon')
                configure_mastodon(k8s_obj, mastodon, bw)

            if apps['matrix']['enabled']:
                matrix = apps.pop('matrix')
                configure_matrix(k8s_obj, matrix, bw)

            # after argocd, keycloak, bweso, and vouch are up, we install all
            # apps as Argo CD Applications
            header("Installing the rest of the Argo CD apps")
            for app_key, app in apps.items():
                if app.get('enabled', True):
                    if not app['argo'].get('part_of_app_of_apps', False):
                        argo_app = app_key.replace('_', '-')
                        sub_header(f"Installing app: {argo_app}")
                        install_with_argocd(k8s_obj, argo_app, app['argo'])

            # lock the bitwarden vault on the way out, to be polite :3
            if bw:
                bw.lock()

    # we're done :D
    print("")
    CONSOLE.print(Panel("\nSmol K8s Lab completed!\n\nMake sure you run:\n"
                        f"[b]export KUBECONFIG={KUBECONFIG}\n",
                        title='[green]◝(ᵔᵕᵔ)◜ Success!',
                        subtitle='♥ [cyan]Have a nice day[/] ♥',
                        border_style="cornflower_blue"))
    print("")

    subproc(['k9s --command applications.argoproj.io'])


if __name__ == '__main__':
    main()
