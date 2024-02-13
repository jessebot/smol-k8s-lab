#!/usr/bin/env python3.11
"""
       Name: nginx_ingress_controller
DESCRIPTION: install the nginx ingress controller
     AUTHOR: @jessebot
    LICENSE: GNU AFFERO GENERAL PUBLIC LICENSE Version 3
"""
# external libraries
import logging as log

# internal libraries
from smol_k8s_lab.k8s_tools.argocd_util import install_with_argocd, check_if_argocd_app_exists
from smol_k8s_lab.k8s_tools.helm import Helm
from smol_k8s_lab.k8s_tools.k8s_lib import K8s


def configure_ingress_nginx(k8s_obj: K8s, k8s_distro: str) -> None:
    """
    install nginx ingress controller from manifests for kind and helm for k3s
    """
    url = ('https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/'
           'deploy/static/provider/kind/deploy.yaml')

    if k8s_distro == 'kind':
        # this is to wait for the deployment to come up
        k8s_obj.apply_manifests(
                manifest_file_name=url,
                namespace="ingress-nginx",
                deployment="ingress-nginx-controller",
                selector="app.kubernetes.io/component=controller"
                )
    else:
        values = {"controller.allowSnippetAnnotations": True}
        release = Helm.chart(release_name='ingress-nginx',
                             chart_name='ingress-nginx/ingress-nginx',
                             namespace='ingress-nginx',
                             set_options=values)
        release.install()


def install_ingress_nginx_argocd_app(k8s_obj: K8s, ingress_nginx_dict: dict) -> None:
    """
    install the ingress nginx Argo CD Application for easier management
    """
    if not check_if_argocd_app_exists("ingress-nginx"):
        log.info("Installing Argo CD Application: ingress-nginx")
        install_with_argocd(k8s_obj,
                            "ingress-nginx",
                            ingress_nginx_dict['argo'])
