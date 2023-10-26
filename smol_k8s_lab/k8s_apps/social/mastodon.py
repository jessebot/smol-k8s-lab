from smol_k8s_lab.bitwarden.bw_cli import BwCLI, create_custom_field
from smol_k8s_lab.k8s_apps.minio import BetterMinio
from smol_k8s_lab.k8s_tools.argocd_util import install_with_argocd
from smol_k8s_lab.k8s_tools.k8s_lib import K8s
from smol_k8s_lab.k8s_tools.kubernetes_util import update_secret_key
from smol_k8s_lab.utils.passwords import create_password
from smol_k8s_lab.utils.rich_cli.console_logging import sub_header, header
from smol_k8s_lab.utils.subproc import subproc

import logging as log


def configure_mastodon(k8s_obj: K8s,
                       config_dict: dict,
                       bitwarden: BwCLI = None,
                       minio_obj: BetterMinio = {}) -> bool:
    """
    creates a mastodon app and initializes it with secrets if you'd like :)
    """
    header("Setting up [green]Mastodon[/green], so you can self host your social media"
           '🐘')
    if config_dict['init']['enabled']:
        # declare custom values for mastodon
        secrets = config_dict['argo']['secret_keys']
        init_values = config_dict['init']['values']

        # configure the admin user credentials
        mastodon_hostname = secrets['hostname']
        username = init_values['admin_user']
        email = init_values['admin_email']

        # configure the smtp credentials
        smtp_user = init_values['smtp_user']
        smtp_pass = init_values['smtp_password']
        smtp_host = init_values['smtp_host']

        # configure s3 credentials if they're in use
        s3_access_id = init_values.get('s3_access_id', 'mastodon')
        s3_access_key = init_values.get('s3_access_key', '')
        s3_endpoint = secrets.get('s3_endpoint', "minio")
        s3_bucket = secrets.get('s3_bucket', "mastodon")

        # create the bucket if the user is using minio
        if minio_obj and s3_endpoint == "minio":
            s3_access_key = minio_obj.create_access_credentials(s3_access_id)
            minio_obj.create_bucket(s3_bucket, s3_access_id)

        rake_secrets = generate_rake_secrets(bitwarden)

        if bitwarden:
            # admin credentials
            email_obj = create_custom_field("email", email)
            sub_header("Creating secrets in Bitwarden")
            password = bitwarden.generate()
            admin_id = bitwarden.create_login(
                    name='mastodon-admin-credentials',
                    item_url=mastodon_hostname,
                    user=username,
                    password=password,
                    fields=[email_obj]
                    )

            # PostgreSQL credentials
            mastodon_pgsql_password = bitwarden.generate()
            postrges_pass_obj = create_custom_field("postgresPassword",
                                                    mastodon_pgsql_password)
            db_id = bitwarden.create_login(
                    name='mastodon-pgsql-credentials',
                    item_url=mastodon_hostname,
                    user='mastodon',
                    password=mastodon_pgsql_password,
                    fields=[postrges_pass_obj]
                    )

            # Redis credentials
            mastodon_redis_password = bitwarden.generate()
            redis_id = bitwarden.create_login(
                    name='mastodon-redis-credentials',
                    item_url=mastodon_hostname,
                    user='mastodon',
                    password=mastodon_redis_password
                    )

            # SMTP credentials
            mastodon_smtp_host_obj = create_custom_field("smtpHostname", smtp_host)
            smtp_id = bitwarden.create_login(
                    name='mastodon-smtp-credentials',
                    item_url=mastodon_hostname,
                    user=smtp_user,
                    password=smtp_pass,
                    fields=[mastodon_smtp_host_obj]
                    )

            # S3 credentials
            mastodon_s3_host_obj = create_custom_field("s3Endpoint", s3_endpoint)
            mastodon_s3_bucket_obj = create_custom_field("s3Bucket", s3_bucket)
            s3_id = bitwarden.create_login(
                    name='mastodon-s3-credentials',
                    item_url=mastodon_hostname,
                    user=s3_access_id,
                    password=s3_access_key,
                    fields=[
                        mastodon_s3_host_obj,
                        mastodon_s3_bucket_obj
                        ]
                    )

            # mastodon secrets
            secret_key_base_obj = create_custom_field(
                    "SECRET_KEY_BASE",
                    rake_secrets['SECRET_KEY_BASE']
                    )
            otp_secret_obj = create_custom_field(
                    "OTP_SECRET",
                    rake_secrets['OTP_SECRET']
                    )
            vapid_pub_key_obj = create_custom_field(
                    "VAPID_PUBLIC_KEY",
                    rake_secrets['VAPID_PUBLIC_KEY']
                    )
            vapid_priv_key_obj = create_custom_field(
                    "VAPID_PRIVATE_KEY",
                    rake_secrets['VAPID_PRIVATE_KEY']
                    )

            secrets_id = bitwarden.create_login(
                    name='mastodon-server-credentials',
                    item_url=mastodon_hostname,
                    user="mastodon",
                    password="none",
                    fields=[
                        secret_key_base_obj,
                        otp_secret_obj,
                        vapid_priv_key_obj,
                        vapid_pub_key_obj
                        ]
                    )
            
            # update the mastodon values for the argocd appset
            fields = {
                    'mastodon_admin_credentials_bitwarden_id': admin_id,
                    'mastodon_smtp_credentials_bitwarden_id': smtp_id,
                    'mastodon_postgres_credentials_bitwarden_id': db_id,
                    'mastodon_redis_bitwarden_id': redis_id,
                    'mastodon_s3_credentials_bitwarden_id': s3_id,
                    'mastodon_server_secrets_bitwarden_id': secrets_id
                    }
            update_secret_key(k8s_obj, 'appset-secret-vars', 'argocd', fields,
                              'secret_vars.yaml')

            # reload the argocd appset secret plugin
            try:
                k8s_obj.reload_deployment('argocd-appset-secret-plugin', 'argocd')
            except Exception as e:
                log.error(
                        "Couldn't scale down the "
                        "[magenta]argocd-appset-secret-plugin[/] deployment "
                        f"in [green]argocd[/] namespace. Recieved: {e}"
                        )

            # reload the bitwarden ESO provider
            try:
                k8s_obj.reload_deployment('bitwarden-eso-provider', 'external-secrets')
            except Exception as e:
                log.error(
                        "Couldn't scale down the [magenta]bitwarden-eso-provider"
                        "[/] deployment in [green]external-secrets[/] namespace."
                        f"Recieved: {e}"
                        )

        # these are standard k8s secrets yaml
        else:
            # admin creds k8s secret
            password = create_password()
            k8s_obj.create_secret('mastodon-admin-credentials', 'mastodon',
                          {"username": username,
                           "password": password,
                           "email": email})

            # postgres creds k8s secret
            mastodon_pgsql_password = create_password()
            k8s_obj.create_secret('mastodon-pgsql-credentials', 'mastodon',
                          {"password": mastodon_pgsql_password,
                           'postrgesPassword': mastodon_pgsql_password})

            # redis creds k8s secret
            mastodon_redis_password = create_password()
            k8s_obj.create_secret('mastodon-redis-credentials', 'mastodon',
                                  {"password": mastodon_redis_password})

            # mastodon rake secrets
            k8s_obj.create_secret('mastodon-server-secrets', 'mastodon',
                                  rake_secrets)

    install_with_argocd(k8s_obj, 'mastodon', config_dict['argo'])


def generate_rake_secrets() -> dict:
    """
    uses the mastodon tootsuite container and returns dict with the following:

    SECRET_KEY_BASE Generate with rake secret.
                    Changing it will break all active browser sessions.

    OTP_SECRET      Generate with rake secret.
                    Changing it will break two-factor authentication.

    VAPID_PRIVATE_KEY Generate with rake mastodon:webpush:generate_vapid_key.
                      Changing it will break push notifications.

    VAPID_PUBLIC_KEY  Generate with rake mastodon:webpush:generate_vapid_key.
                      Changing it will break push notifications.

    These are required for mastodon. See ref:
        https://docs.joinmastodon.org/admin/config/#secrets
    """
    final_dict = {"SECRET_KEY_BASE": "",
                  "OTP_SECRET": "",
                  "VAPID_PRIVATE_KEY": "",
                  "VAPID_PUBLIC_KEY": ""}

    # we use docker to generate all of these
    base_cmd = "docker run docker.io/tootsuite/mastodon:latest rake"

    # this is for the SECRET_KEY_BASE and OTP_SECRET values
    secret_cmd = base_cmd + " secret"
    final_dict['SECRET_KEY_BASE'] = subproc([secret_cmd]).split()[0]
    final_dict['OTP_SECRET'] = subproc([secret_cmd]).split()[0]

    # this is for the vapid keys
    vapid_cmd = base_cmd + " mastodon:webpush:generate_vapid_key"
    vapid_keys = subproc([vapid_cmd]).split()

    final_dict['VAPID_PRIVATE_KEY'] = vapid_keys[0].split("=")[1]
    final_dict['VAPID_PUBLIC_KEY'] = vapid_keys[1].split("=")[1]

    return final_dict
