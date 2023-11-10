from base64 import standard_b64decode as b64dec
from json import loads
import logging as log
from .zitadel_api import Zitadel
from smol_k8s_lab.bitwarden.bw_cli import BwCLI, create_custom_field
from smol_k8s_lab.k8s_tools.k8s_lib import K8s
from smol_k8s_lab.k8s_tools.argocd_util import (install_with_argocd,
                                                wait_for_argocd_app,
                                                check_if_argocd_app_exists,
                                                update_argocd_appset_secret)
from smol_k8s_lab.utils.passwords import create_password
from smol_k8s_lab.utils.rich_cli.console_logging import sub_header, header


def configure_zitadel(k8s_obj: K8s,
                      config_dict: dict,
                      api_tls_verify: bool = False,
                      argocd_hostname: str = "",
                      bitwarden: BwCLI = None) -> dict | None:
    """
    Installs zitadel as a Argo CD Applications. If config_dict['init']['enabled']
    is True, it also configures Argo CD as OIDC Clients.

    Required Arguments:
        k8s_obj:      K8s(), kubrenetes client for creating secrets
        config_dict:  dict, Argo CD parameters for zitadel

    Optional Arguments:
        argocd_hostname:  str, the hostname of Argo CD
        bitwarden:        BwCLI obj, [optional] contains bitwarden session

    If no init: Returns True if successful.
    If init AND vouch_hostname, returns vouch credentials
    """
    header("Setting up [green]Zitadel[/green], our identity management solution", "👥")
    secrets = config_dict['argo']['secret_keys']
    if secrets:
        zitadel_hostname = secrets['hostname']

    # check to make sure the app instead already installed with Argo CD
    app_installed = check_if_argocd_app_exists('zitadel')

    if config_dict['init']['enabled'] and not app_installed:
        log.debug("Creating core key and DB credenitals for zitadel...")
        db_admin_user = "postgres"
        init_values = config_dict['init']['values']
        # configure s3 credentials if they're in use
        s3_access_id = init_values.get('s3_access_id', 'zitadel')
        s3_access_key = init_values.get('s3_access_key', '')
        s3_endpoint = secrets.get('s3_endpoint', "")
        s3_bucket = secrets.get('s3_bucket', "zitadel-postgresql")
        if config_dict['argo']['directory_recursion']:
            default_minio = True
        else:
            default_minio = False
        create_minio_tenant = init_values.get('create_minio_tenant',
                                              default_minio)

        # creates the initial root credentials secret for the minio tenant
        if create_minio_tenant:
            if not s3_access_key:
                s3_access_key = create_password()

            credentials_exports = {
                    'config.env': f"""MINIO_ROOT_USER={s3_access_id}
            MINIO_ROOT_PASSWORD={s3_access_key}"""}
            k8s_obj.create_secret('default-tenant-env-config',
                                  config_dict['argo']['namespace'],
                                  credentials_exports)

        if bitwarden:
            # S3 credentials
            if "http" not in s3_endpoint:
                s3_endpoint = "https://" + s3_endpoint
            s3_host_obj = create_custom_field("s3Endpoint", s3_endpoint)
            s3_bucket_obj = create_custom_field("s3Bucket", s3_bucket)
            s3_id = bitwarden.create_login(
                    name='zitadel-s3-credentials',
                    item_url=zitadel_hostname,
                    user=s3_access_id,
                    password=s3_access_key,
                    fields=[s3_host_obj, s3_bucket_obj]
                    )

            # create zitadel core key
            new_key = bitwarden.generate()
            core_id = bitwarden.create_login(name="zitadel-core-key",
                                             user="admin-service-account",
                                             item_url=zitadel_hostname,
                                             password=new_key)

            # create db credentials password dict
            db_password = bitwarden.generate()
            db_admin_password = bitwarden.generate()
            db_admin_user_obj = create_custom_field("adminUser",
                                                    db_admin_user)
            db_admin_pass_obj = create_custom_field("adminPassword",
                                                    db_admin_password)
            db_id = bitwarden.create_login(name="zitadel-db-credentials",
                                           user="zitadel",
                                           item_url=zitadel_hostname,
                                           password=db_password,
                                           fields=[db_admin_user_obj,
                                                   db_admin_pass_obj])

            # update the zitadel values for the argocd appset
            update_argocd_appset_secret(
                    k8s_obj,
                    {'zitadel_core_bitwarden_id': core_id,
                     'zitadel_db_bitwarden_id': db_id,
                     'zitadel_s3_credentials_bitwarden_id': s3_id}
                    )

            # reload the bitwarden ESO provider
            try:
                k8s_obj.reload_deployment('bitwarden-eso-provider', 'external-secrets')
            except Exception as e:
                log.error(
                        "Couldn't scale down the [magenta]bitwarden-eso-provider[/]"
                        "deployment in [green]external-secrets[/] namespace. Recieved: "
                        f"{e}"
                        )
        else:
            new_key = create_password()
            secret_dict = {'masterkey': new_key}
            k8s_obj.create_secret(name="zitadel-core-key",
                                  namespace="zitadel",
                                  str_data=secret_dict)

            db_password = create_password()
            db_admin_password = create_password()
            db_secret_dict = {
                    'username': 'zitadel',
                    'password': db_password,
                    'adminUsername': db_admin_user,
                    'adminPassword': db_admin_password
                    }
            k8s_obj.create_secret(name="zitadel-db-credentials",
                                  namespace="zitadel",
                                  str_data=db_secret_dict)

    # install Zitadel using ArgoCD
    if not app_installed:
        install_with_argocd(k8s_obj, 'zitadel', config_dict['argo'])

        # only continue through the rest of the function if we're initializes a
        # user and argocd client in zitadel
        if config_dict['init']['enabled']:
            initial_user_dict = config_dict['init']['values']
            # Before initialization, we need to wait for zitadel's API to be up
            wait_for_argocd_app('zitadel')
            wait_for_argocd_app('zitadel-web-app')
            vouch_dict = initialize_zitadel(k8s_obj=k8s_obj,
                                            zitadel_hostname=zitadel_hostname,
                                            api_tls_verify=api_tls_verify,
                                            user_dict=initial_user_dict,
                                            argocd_hostname=argocd_hostname,
                                            bitwarden=bitwarden)
            return vouch_dict
    else:
        log.info("Zitadel is already installed 🎉")

        if bitwarden and config_dict['init']['enabled']:
            # get the zitadel service account private key json for generating a jwt
            adm_secret_file = k8s_obj.get_secret(
                    'zitadel-admin-sa',
                    'zitadel'
                    )['data']['zitadel-admin-sa.json']

            # setup and return the zitadel python api wrapper
            zitadel = Zitadel(
                    zitadel_hostname,
                    loads(b64dec(str.encode(adm_secret_file)).decode('utf8')),
                    api_tls_verify
                    )
            try:
                zitadel.set_user_by_login_name(
                        config_dict['init']['values']['username']
                        )
            except Exception as e:
                log.error(e)

            try:
                zitadel.set_project_by_name(
                        config_dict['init']['values']['project']
                        )
            except Exception as e:
                log.error(e)
                raise Exception(e)

            # makes sure we update the appset secret with bitwarden IDs regardless
            db_id = bitwarden.get_item(
                    f"zitadel-db-credentials-{zitadel_hostname}"
                    )[0]['id']

            s3_id = bitwarden.get_item(
                    f"zitadel-s3-credentials-{zitadel_hostname}"
                    )[0]['id']

            core_id = bitwarden.get_item(
                    f"zitadel-core-key-{zitadel_hostname}"
                    )[0]['id']

            argo_oidc_item = bitwarden.get_item(
                    f"argocd-oidc-credentials-{argocd_hostname}"
                    )[0]

            argo_client_id = argo_oidc_item['login']['username']

            # update the zitadel values for the argocd appset

            update_argocd_appset_secret(
                    k8s_obj,
                    {
                    'zitadel_core_bitwarden_id': core_id,
                    'zitadel_db_bitwarden_id': db_id,
                    'zitadel_s3_credentials_bitwarden_id': s3_id,
                    'argo_cd_oidc_issuer': f"https://{zitadel_hostname}",
                    'argo_cd_oidc_client_id': argo_client_id,
                    'argo_cd_oidc_logout_url': f"https://{zitadel_hostname}/oidc/v1/end_session",
                    'argo_cd_oidc_bitwarden_id': argo_oidc_item['id']
                    }
                    )

            # sync_argocd_app('zitadel')
            # sync_argocd_app('argo-cd')

            return zitadel


def initialize_zitadel(k8s_obj: K8s,
                       zitadel_hostname: str,
                       api_tls_verify: bool = False,
                       user_dict: dict = {},
                       argocd_hostname: str = "",
                       bitwarden: BwCLI = None) -> dict | None:
    """
    Sets up initial zitadel user, Argo CD client
    Arguments:
      k8s_obj:           K8s(), kubrenetes client for creating secrets
      zitadel_hostname:  str, the hostname of Zitadel
      api_tls_verify:    bool, whether or not to verify the TLS cert on request to api
      user_dict:         dict of initial username, email, first name, last name
                         gender, and project to create
      argocd_hostname:   str, the hostname of Argo CD for oidc app
      bitwarden:         BwCLI obj, [optional] session to use for bitwarden

    returns Zitadel() with admin user/admin service account created with session token
    """

    sub_header("Configuring zitadel as your OIDC SSO for Argo CD")

    # get the zitadel service account private key json for generating a jwt
    adm_secret = k8s_obj.get_secret('zitadel-admin-sa', 'zitadel')
    adm_secret_file = adm_secret['data']['zitadel-admin-sa.json']
    private_key_obj = loads(b64dec(str.encode(adm_secret_file)).decode('utf8'))
    # setup the zitadel python api wrapper
    zitadel =  Zitadel(zitadel_hostname, private_key_obj, api_tls_verify)

    # create our first project
    project_name = user_dict.pop('project')
    zitadel.create_project(project_name)

    log.info("Creating a groups Zitadel Action (sends group info to Argo CD)")
    zitadel.create_groups_claim_action()

    # create Argo CD OIDC Application
    log.info("Creating an Argo CD application...")
    redirect_uris = f"https://{argocd_hostname}/auth/callback"
    logout_uris = [f"https://{argocd_hostname}"]
    argocd_client = zitadel.create_application("argocd",
                                               redirect_uris,
                                               logout_uris)

    # create roles for both Argo CD Admins and regular users
    zitadel.create_role("argocd_administrators", "Argo CD Administrators",
                        "argocd_administrators")
    zitadel.create_role("argocd_users", "Argo CD Users", "argocd_users")

    # fields for updating the appset secret
    fields = {
            'argo_cd_oidc_issuer': f"https://{zitadel_hostname}",
            'argo_cd_oidc_client_id': argocd_client['client_id'],
            'argo_cd_oidc_logout_url': f"https://{zitadel_hostname}/oidc/v1/end_session"
            }

    # if bitwarden is enabled, we store the argocd odic secret there
    if bitwarden:
        sub_header("Creating OIDC secret for Argo CD in Bitwarden")
        id = bitwarden.create_login(name='argocd-oidc-credentials',
                                    item_url=argocd_hostname,
                                    user=argocd_client['client_id'],
                                    password=argocd_client['client_secret'])
        fields['argo_cd_oidc_bitwarden_id'] = id
    else:
        # the argocd secret needs labels.app.kubernetes.io/part-of: "argocd"
        k8s_obj.create_secret('argocd-oidc-credentials',
                              'argocd',
                              {'user': argocd_client['client_id'],
                               'password': argocd_client['client_secret']},
                              labels={'app.kubernetes.io/part-of': 'argocd'})

    # create zitadel admin user that the project is setup
    header("Creating a Zitadel user...")
    user_id = zitadel.create_user(bitwarden=bitwarden, **user_dict)
    zitadel.set_user_by_login_name(user_dict['username'])
    try:
        zitadel.create_user_grant(['argocd_administrators'])
    except Exception as e:
        log.error(e)
        zitadel.update_user_grant(['argocd_administrators'])

    # grant admin access to first user
    sub_header("creating user IAM membership with IAM_OWNER")
    zitadel.create_iam_membership(user_id, 'IAM_OWNER')

    # update appset-secret-vars secret with issuer, client_id, logout_url
    update_argocd_appset_secret(k8s_obj, fields)

    return zitadel
