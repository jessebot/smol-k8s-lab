import logging as log
from os import environ
from smol_k8s_lab.bitwarden.bw_cli import BwCLI
from smol_k8s_lab.k8s_tools.argocd_util import ArgoCD


def extract_secret(value: dict = {}) -> str:
    """
    process a value that has a valueFrom dict and return the value

    supported valueFrom methods: env, bitwarden. coming soon: openbao
    """
    if isinstance(value, dict):
        value_dict = value.get('valueFrom', None)
        if not value_dict:
            log.warn(f"{value} has no valueFrom dict, so we're returning empty str")
            return ""
    else:
        log.warn(f"value, {value}, is not a dict, so we're returning it as it came in")
        return value

    # try to get variable from env var
    env_var = value_dict.get('env', None)
    if env_var:
        return environ.get(env_var, "")

    # try to get variable from bitwarden item and field
    bitwarden_item = value_dict.get('bitwarden_item', None)
    if bitwarden_item:
        bitwarden_field = value['valueFrom'].get('bitwarden_field', None)
        bw = BwCLI()
        return bw.get_item(bitwarden_item)[0][bitwarden_field]

    # try to get variable from openbao (or vault) item
    openbao_item = value_dict.get('openbao_item', None)
    if openbao_item:
        log.warn("openbao support not yet implemented")

    log.warn("No secret was found so returning empty string")
    return ""


def process_backup_vals(backup_dict: dict,
                        app: str = "",
                        argocd: ArgoCD = None) -> dict:
    """
    return a backup value dict by processing s3 values and getting any secret data

    optionally, if app name and argocd obj are passed in, we also update the
    appset secret plugin secret with the backup values
    """
    s3_values = backup_dict.get('s3', {})

    return_dict =  {
            "endpoint": s3_values.get('endpoint', ""),
            "region": s3_values.get('region', ""),
            "bucket": s3_values.get('bucket', ""),
            "s3_user": extract_secret(s3_values.get('access_key_id', '')),
            "s3_password": extract_secret(s3_values.get('secret_access_key', '')),
            "restic_repo_pass": extract_secret(backup_dict.get('restic_repo_password', '')),
            "schedule": backup_dict.get('schedule', "0 0 * * *")
            }

    if app and argocd:
        argocd.update_appset_secret({
            f"{app}_s3_backup_endpoint": return_dict['endpoint'],
            f"{app}_s3_backup_bucket": return_dict['bucket'],
            f"{app}_s3_backup_region": return_dict['region'],
            f"{app}_s3_backup_schedule": return_dict['schedule']})

    return return_dict
