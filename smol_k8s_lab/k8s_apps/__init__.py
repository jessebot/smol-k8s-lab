#!/usr/bin/env python3.11
"""
       Name: base_install
DESCRIPTION: installs helm repos, updates them, and installs charts for metallb,
             cert-manager, and ingress-nginx
     AUTHOR: @jessebot
    LICENSE: GNU AFFERO GENERAL PUBLIC LICENSE Version 3
"""
import logging as log
from rich.prompt import Prompt
from ..k8s_tools.homelabHelm import prepare_helm
from ..k8s_tools.k8s_lib import K8s
from ..utils.bw_cli import BwCLI
from ..utils.pretty_printing.console_logging import header
from .ingress.ingress_nginx_controller import configure_ingress_nginx
from .ingress.cert_manager import configure_cert_manager
from .identity_provider.keycloak import configure_keycloak
from .identity_provider.zitadel import configure_zitadel
from .identity_provider.vouch import configure_vouch
from .metallb import configure_metallb
from .secrets_management.external_secrets_operator import configure_external_secrets
from .secrets_management.infisical import configure_infisical
from .social.federated import configure_matrix, configure_mastodon, configure_nextcloud


def setup_k8s_secrets_management(k8s_obj: K8s,
                                 k8s_distro: str = "",
                                 eso_dict: dict = {},
                                 bitwarden_eso_provider_dict: dict = {},
                                 infisical_dict: dict = {},
                                 bitwarden: BwCLI = None) -> True:
    """
    sets up k8s secrets management tooling
    """
    # secrets management section
    header_msg = "🤫 Setting up K8s secret management with [green]"

    # setup external secrets operator and bitwarden external secrets
    if eso_dict['enabled']:
        header_msg += 'External Secrets Operator[/]'
        if bitwarden_eso_provider_dict['enabled']:
            header_msg += ' and [blue]Bitwarden[/] as the Provider'
        header(header_msg)
        configure_external_secrets(k8s_obj,
                                   eso_dict,
                                   bitwarden_eso_provider_dict,
                                   k8s_distro,
                                   bitwarden)

    # setup infisical - an secrets manager and operator for k8s
    elif infisical_dict['enabled']:
        header_msg += 'Infisical Secrets Operator[/]'
        header(header_msg)
        configure_infisical(k8s_obj, infisical_dict)

    return True


def setup_oidc_provider(k8s_obj: K8s,
                        keycloak_dict: dict = {},
                        zitadel_dict: dict = {},
                        vouch_dict: dict = {},
                        bw: BwCLI = None,
                        argocd_fqdn: str = "") -> True:
    header("Setting up [green]OIDC[/]/[green]Oauth[/] Applications")

    keycloak_enabled = keycloak_dict['enabled']
    zitadel_enabled = zitadel_dict['enabled']

    # setup keycloak if we're using that for OIDC
    if keycloak_enabled:
        log.debug("Setting up keycloak")
        configure_keycloak(k8s_obj, keycloak_dict, bw)
        realm = keycloak_dict['argo']['secret_keys']['default_realm']

    # setup zitadel if we're using that for OIDC
    elif zitadel_enabled:
        log.debug("Setting up zitadel")
        zitadel = configure_zitadel(k8s_obj, zitadel_dict, argocd_fqdn, bw)
        log.debug(f"zitadel obj fresh out of configure_zitadel is {zitadel}")

    if vouch_dict:
        if vouch_dict['enabled']:
            log.debug("Setting up vouch")
            if keycloak_enabled:
                configure_vouch(k8s_obj,
                                vouch_dict,
                                'keycloak',
                                keycloak_dict['argo']['secret_keys']['hostname'],
                                bw,
                                realm)
            elif zitadel_enabled:
                log.debug(f"zitadel obj is {zitadel}")
                configure_vouch(k8s_obj,
                                vouch_dict,
                                'zitadel',
                                zitadel_dict['argo']['secret_keys']['hostname'],
                                bw,
                                "",
                                zitadel)
            else:
                configure_vouch(k8s_obj, vouch_dict, '', '', bw)
    return True


def setup_base_apps(k8s_obj: K8s,
                    k8s_distro: str = "",
                    metallb_dict: dict = {},
                    cert_manager_dict: dict = {},
                    argo_enabled: bool = False,
                    argo_secrets_enabled: bool = False) -> bool:
    """ 
    Uses Helm to install all base apps: metallb, ingess-nginx, and cert-manager
    All Needed for getting Argo CD up and running.
    """
    metallb_enabled = metallb_dict['enabled']
    # make sure helm is installed and the repos are up to date
    prepare_helm(k8s_distro, metallb_enabled, argo_enabled, argo_secrets_enabled)

    # needed for metal (non-cloud provider) installs
    if metallb_enabled:
        header("Installing [green]metallb[/green] so we have an IP address pool.")
        if metallb_dict['init']['enabled']:
            cidr = metallb_dict['init']['values']['address_pool']
            if not cidr:
                m = "[green]Please enter a comma seperated list of IPs or CIDRs"
                cidr = Prompt.ask(m).split(',')

            configure_metallb(cidr)

    # ingress controller: so we can accept traffic from outside the cluster
    # nginx just because that's most supported, treafik support may be added later
    header("Installing [green]ingress-nginx-controller[/green] to access web apps "
           "outside the cluster")
    configure_ingress_nginx(k8s_distro)

    # manager SSL/TLS certificates via lets-encrypt
    header("Installing [green]cert-manager[/green] for TLS certificates...")
    cert_manager_init = cert_manager_dict['init']['enabled']
    if cert_manager_init:
        email = cert_manager_dict['argo']['secret_keys']['email']
    else:
        email = ""
    configure_cert_manager(k8s_obj, email)

    # success!
    return True


def setup_federated_apps(k8s_obj: K8s,
                         nextcloud_dict: dict = {},
                         mastodon_dict: dict = {},
                         matrix_dict: dict = {},
                         bw: BwCLI = None) -> True:
    """
    Setup any federated apps with initialization supported
    returns True when done
    """
    if nextcloud_dict['enabled']:
        configure_nextcloud(k8s_obj, nextcloud_dict, bw)

    if mastodon_dict['enabled']:
        configure_mastodon(k8s_obj, mastodon_dict, bw)

    if matrix_dict['enabled']:
        configure_matrix(k8s_obj, matrix_dict, bw)

    return True
