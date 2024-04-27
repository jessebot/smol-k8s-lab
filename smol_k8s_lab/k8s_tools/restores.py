"""
       Name: restores.py
DESCRIPTION: restore stuff with k8up (restic on k8s) and cnpg operator
     AUTHOR: @jessebot
    LICENSE: GNU AFFERO GENERAL PUBLIC LICENSE Version 3
"""
# internal libraries
from smol_k8s_lab.constants import XDG_CACHE_DIR
from smol_k8s_lab.k8s_tools.k8s_lib import K8s
from smol_k8s_lab.k8s_tools.helm import Helm
from smol_k8s_lab.utils.subproc import subproc

# external libraries
from json import loads
import logging as log
from os import path, environ
from time import sleep
import yaml


def restore_seaweedfs(k8s_obj: K8s,
                      app: str,
                      namespace: str,
                      s3_endpoint: str,
                      s3_bucket: str,
                      access_key_id: str,
                      secret_access_key: str,
                      restic_repo_password: str,
                      s3_pvc_capacity: str,
                      storage_class: str = "local-path",
                      volume_snapshot_id: str = "",
                      master_snapshot_id: str = "",
                      filer_snapshot_id: str = ""
                      ):
    """
    recreate the seaweedfs PVCs for a given namespace and restore them via restic
    """
    # this recreates all the seaweedfs PVCs
    pvc_dict = {"kind": "PersistentVolumeClaim",
                "apiVersion": "v1",
                "metadata": {
                  "name": "",
                  "namespace": namespace,
                  "annotations": {"k8up.io/backup": "true"}
                  },
                "spec": {
                  "storageClassName": storage_class,
                  "accessModes": ["ReadWriteOnce"],
                  "resources": {
                    "requests": {"storage": s3_pvc_capacity}
                    }
                  }
                }

    snapshots = {'swfs-volume-data': volume_snapshot_id,
                 'swfs-master-data': master_snapshot_id,
                 'swfs-filer-data': filer_snapshot_id}

    for swfs_pvc, snapshot_id in snapshots.items():
        # set the pvc name accordingly
        pvc_dict["metadata"]["name"] = swfs_pvc

        # master and filer have preset smaller capacities
        if swfs_pvc == "swfs-master-data":
            pvc_dict["spec"]["resources"]["requests"]["storage"] = "2Gi"

        if swfs_pvc == "swfs-filer-data":
            pvc_dict["spec"]["resources"]["requests"]["storage"] = "5Gi"

        # apply the pvc_dict
        k8s_obj.apply_custom_resources([pvc_dict])

        # label the PVCs so Argo CD doesn't complain
        subproc([f"kubectl label pvc -n {namespace} {swfs_pvc} "
                 f"argocd.argoproj.io/instance={app}-s3-pvc"])

        # build a k8up restore file and apply it
        k8up_restore_pvc(k8s_obj, app, swfs_pvc, namespace,
                         s3_endpoint, s3_bucket, access_key_id, secret_access_key,
                         restic_repo_password, snapshot_id)


def k8up_restore_pvc(k8s_obj: K8s,
                     app: str,
                     pvc: str,
                     namespace: str,
                     s3_endpoint: str,
                     s3_bucket: str,
                     access_key_id: str,
                     secret_access_key: str,
                     restic_repo_password: str,
                     snapshot_id: str = "latest"):
    """
    builds a k8up restore manifest and applies it
    """
    restore_dict = {'apiVersion': 'k8up.io/v1',
                    'kind': 'Restore',
                    'metadata': {
                        'name': pvc,
                        'namespace': namespace
                        },
                    'spec': {
                        'failedJobsHistoryLimit': 5,
                        'successfulJobsHistoryLimit': 1,
                        'podSecurityContext': {
                            'runAsUser': 0
                            },
                        'restoreMethod': {
                            'folder': {
                                'claimName': pvc
                                }
                            },
                        'backend': {
                            'repoPasswordSecretRef': {
                                'name': "s3-backups-credentials",
                                'key': 'resticRepoPassword'
                                },
                            's3': {
                                'endpoint': s3_endpoint,
                                'bucket': s3_bucket,
                                'accessKeyIDSecretRef': {
                                    'name': "s3-backups-credentials",
                                    'key': 'accessKeyID'
                                    },
                                'secretAccessKeySecretRef': {
                                    'name': "s3-backups-credentials",
                                    'key': 'secretAccessKey'
                                    }
                                }
                            }
                        }
                    }

    # if snapshot not passed in, restic/k8up use the latest snapshot
    if snapshot_id and snapshot_id != "latest":
        restore_dict['spec']['snapshot'] = snapshot_id
    else:
        # set restic environment variables
        env = {"PATH": environ.get("PATH"),
               "RESTIC_REPOSITORY": f"s3:{s3_endpoint}/{s3_bucket}",
               "RESTIC_PASSWORD_COMMAND": f"echo -n '{restic_repo_password}'",
               "AWS_ACCESS_KEY_ID": access_key_id,
               "AWS_SECRET_ACCESS_KEY": secret_access_key}

        snapshots = loads(subproc(["restic snapshots --latest 1 --json"], env=env))

        for snapshot in snapshots:
            # makes sure this is the snapshot for the correct path
            if pvc in snapshot["paths"][0]:
                # gets the long ID of the latest snapshot for this path
                restore_dict['spec']['snapshot'] = snapshot['id']

    # apply the k8up restore job
    k8s_obj.apply_custom_resources([restore_dict])

    # loop on check to make sure the restore is done before continuing
    check_cmd = (f"kubectl get restore -n {namespace} --no-headers -o "
                 f"custom-columns=COMPLETION:.status.finished {pvc}")
    while True:
        restore_done = subproc([check_cmd]).strip()
        log.debug(f"restore done returns {restore_done}")

        pod_cmd = (f"kubectl get pods -n {namespace} --no-headers -o "
                   f"custom-columns=NAME:.metadata.name | grep {pvc}")
        pod = subproc([pod_cmd], universal_newlines=True, shell=True)
        subproc([f"kubectl logs -n {namespace} --tail=5 {pod}"], error_ok=True)

        if restore_done != "true":
            # sleep then try again
            sleep(5)
        else:
            break


def restore_postgresql(app: str,
                       namespace: str,
                       cluster_name: str,
                       postgresql_version: float,
                       s3_endpoint: str,
                       s3_bucket: str
                       ):
    """
    restore a CNPG operator controlled postgresql cluster
    """
    restore_dict = {
            "name": cluster_name,
            "instances": 1,
            "imageName": f"ghcr.io/cloudnative-pg/postgresql:{postgresql_version}",
            "bootstrap": {
              "initdb": [],
              "recovery": {
                "source": cluster_name
                }
             },
            "certificates": {
              "server": {
                "enabled": True,
                "generate": True,
                "serverTLSSecret": "",
                "serverCASecret": ""
                },
              "client": {
                "enabled": True,
                "generate": True,
                "clientCASecret": "",
                "replicationTLSSecret": ""
                },
              "user": {
                "enabled": True,
                "username": ["app"]
                }
              },
            "backup": [],
            "externalClusters": [{
                "name": cluster_name,
                "barmanObjectStore": {
                  "destinationPath": f"s3://{s3_bucket}/",
                  "endpointURL": f"https://{s3_endpoint}",
                  "s3Credentials": {
                    "accessKeyId": {
                      "name": "s3-postgres-credentials",
                      "key": "S3_USER"
                      },
                    "secretAccessKey": {
                      "name": "s3-postgres-credentials",
                      "key": "S3_PASSWORD"
                      }
                    }
                  },
                  "wal": {
                    "maxParallel": 8
                    }
                  }],
            "monitoring": {
              "enablePodMonitor": False
              },
            "storage": {
              "size": "1Gi"
              },
            "testApp": {
              "enabled": False
              }
            }

    # this creates a values.yaml from restore_dict above
    values_file_name = path.join(XDG_CACHE_DIR, 'cnpg_restore_values.yaml')
    with open(values_file_name, 'w') as values_file:
        yaml.dump(restore_dict, values_file)

    release_dict = {"release_name": "cnpg-cluster",
                    "namespace": namespace,
                    "values_file": values_file_name,
                    "chart_name": "cnpg-cluster/cnpg-cluster"}
    release = Helm.chart(**release_dict)

    # this actually applies the helm chart release we've defined above
    release.install(True)
