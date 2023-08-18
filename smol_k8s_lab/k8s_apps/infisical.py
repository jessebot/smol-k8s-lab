#!/usr/bin/env python3.11
"""
       Name: infisical
DESCRIPTION: configures infisical app and secrets operator
     AUTHOR: @jessebot
    LICENSE: GNU AFFERO GENERAL PUBLIC LICENSE Version python3
             Infisical itself is licensed under Apache 2.0 and we at
             smol-k8s-lab do not claim any of their code
"""
from rich.prompt import Prompt
from random import randbytes
from ..pretty_printing.console_logging import header
from ..k8s_tools.argocd_util import install_with_argocd
from ..utils.passwords import create_password
from ..k8s_tools.k8s_lib import K8s


def configure_infisical(k8s_obj: K8s, infisical_dict: dict = {}):
    """
    - configures the infisical app by asking for smtp credentials
    - configures backendEnvironmentVariables secrets to sign JWT tokens
    """
    header("Installing the Infisical app and Secrets operator...")
    k8s_obj.create_namespace('infisical')

    argo_dict = infisical_dict['argo']

    if infisical_dict['init']:
        mongo_password = create_mongo_secrets(k8s_obj)
        create_backend_secret(k8s_obj,
                              mongo_password,
                              argo_dict['secrets_keys']['hostname'])

    install_with_argocd(k8s_obj, 'infisical', argo_dict)
    return True


def create_backend_secret(k8s_obj: K8s,
                          mongo_password: str = "",
                          hostname: str = ""):
    """
    generates an smtp dict for env vars AND 16-bytes hex value, 32-characters hex:
    Command to generate the required value (linux): openssl rand -hex 16
    MONGO_URL should be autogenerated, we hope
    """
    base = "[green]Please enter your SMTP"
    host = Prompt.ask(f"{base} host for Infisical")
    from_address = Prompt.ask(f"{base} 'from address' for Infisical")
    username = Prompt.ask(f"{base} username for Infisical", password=True)
    password = Prompt.ask(f"{base} password for Infisical", password=True)

    mongo_url = f"mongodb://infisical:{mongo_password}@mongodb:27017/infisical"

    secrets_dict = {"SMTP_HOST": host,
                    "SITE_URL": f"https://{hostname}",
                    "SMTP_PORT": '587',
                    "SMTP_SECURE": 'true',
                    "SMTP_FROM_NAME": "Infisical",
                    "SMTP_FROM_ADDRESS": from_address,
                    "SMTP_USERNAME": username,
                    "SMTP_PASSWORD": password,
                    "ENCRYPTION_KEY": randbytes(16).hex(),
                    "JWT_SIGNUP_SECRET": randbytes(16).hex(),
                    "JWT_REFRESH_SECRET": randbytes(16).hex(),
                    "JWT_AUTH_SECRET": randbytes(16).hex(),
                    "JWT_SERVICE_SECRET": randbytes(16).hex(),
                    "JWT_MFA_SECRET": randbytes(16).hex(),
                    "JWT_PROVIDER_AUTH_SECRET": randbytes(16).hex(),
                    "MONGO_URL": mongo_url}

    k8s_obj.create_secret('infisical-backend-secrets', 'infisical',
                          secrets_dict)


def create_mongo_secrets(k8s_obj: K8s):
    """
    auth.existingSecret Existing secret with MongoDB credentials:
      keys: mongodb-passwords
            mongodb-root-password
            mongodb-metrics-password

            mongodb-replica-set-key

    returns mongo password
    """
    mongo_pass = create_password()
    secrets_dict = {"mongodb-passwords": mongo_pass,
                    "mongodb-root-password": create_password(),
                    "mongodb-metrics-password": create_password()}

    k8s_obj.create_secret('infisical-mongo-credentials', 'infisical',
                          secrets_dict)
    return mongo_pass
