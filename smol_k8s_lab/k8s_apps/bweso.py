from ..k8s_tools.argocd import install_with_argocd
from ..k8s_tools.k8s_lib import K8s
from ..utils.bw_cli import BwCLI


def setup_bweso(k8s_obj: K8s() = K8s(),
                bweso_argo_dict: dict = {},
                bitwarden: BwCLI() = BwCLI()):
    """
    Creates an initial secret for use with the bitwarden provider for ESO
    """
    bw_client_id = bitwarden.clientID
    bw_client_secret = bitwarden.clientSecret
    bw_host = bitwarden.host
    bw_pass = bitwarden.pw

    # this is a standard k8s secrets yaml
    k8s_obj.create_secret('bweso-login', 'external-secrets',
                          {"BW_PASSWORD": bw_pass,
                           "BW_CLIENTSECRET": bw_client_secret,
                           "BW_CLIENTID": bw_client_id,
                           "BW_HOST": bw_host})

    install_with_argocd('bitwarden-eso-provider', bweso_argo_dict)
    return True
