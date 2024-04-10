#!/usr/bin/env python3.11
"""
       Name: restores
DESCRIPTION: restore stuff with k8up and cnpg operator
     AUTHOR: @jessebot
    LICENSE: GNU AFFERO GENERAL PUBLIC LICENSE Version 3
"""
# internal libraries
from smol_k8s_lab.constants import PWD, XDG_CACHE_DIR
from smol_k8s_lab.k8s_tools.k8s_lib import K8s
from smol_k8s_lab.k8s_tools.helm import Helm
from smol_k8s_lab.utils.subproc import subproc

# external libraries
from os import path
import yaml


def restore_seaweedfs(app: str,
                      namespace: str,
                      s3_endpoint: str,
                      s3_bucket: str,
                      s3_user: str,
                      s3_password: str,
                      restic_password: str,
                      volume_snapshot_id: str,
                      master_snapshot_id: str,
                      filer_snapshot_id: str,
                      k8s_obj: K8s):
    """
    recreate the seaweedfs PVCs for a given namespace and restore them via restic
    """
    # this recreates all the seaweedfs PVCs
    k8s_obj.apply_manifests(path.join(PWD, 'config/seaweedfs_pvcs.yaml'),
                            namespace)

    snapshots = {'swfs-volume-data': volume_snapshot_id,
                 'swfs-master-data': master_snapshot_id,
                 'swfs-filer-data': filer_snapshot_id}

    for swfs_pvc, snapshot_id in snapshots.items():
        # label the PVCs so Argo CD doesn't complain
        subproc([f"kubectl label pvc -n {namespace} {swfs_pvc} "
                 f"argocd.argoproj.io/instance: {app}-s3-pvc"])

        # build a k8up restore file and apply it
        restore_pvc(app, swfs_pvc, namespace, s3_endpoint, s3_bucket, snapshot_id)


def restore_pvc(app: str,
                pvc: str,
                namespace: str,
                s3_endpoint: str,
                s3_bucket: str,
                snapshot_id: str,
                k8s_obj: K8s):
    """
    builds a k8up restore manifest and applies it
    """
    restore_dict = {'apiVersion': 'k8up.io/v1',
                    'kind': 'Restore',
                    'metadata': {
                        'name': '',
                        'namespace': ''
                        },
                    'spec': {
                        'failedJobHistoryLimit': 5,
                        'successfulJobHistoryLimit': 1,
                        'podSecurityContext': {
                            'runAsUser': 0
                            },
                        'snapshot': '',
                        'restoreMethod': {
                            'folder': {
                                'claimName': ''
                                }
                            },
                        'backend': {
                            'repoPasswordSecretRef': {
                                'name': '',
                                'key': 'resticRepoPassword'
                                },
                            's3': {
                                'endpoint': '',
                                'bucket': '',
                                'accessKeyIDSecretRef': {
                                    'name': '',
                                    'key': 'applicationKeyId'
                                    },
                                'secretAccessKeySecretRef': {
                                    'name': '',
                                    'key': 'applicationKey'
                                    }
                                }
                            }
                        }
                    }

    restore_dict['metadata']['name'] = pvc
    restore_dict['metadata']['namespace'] = namespace
    # TODO: verify that snapshot id will default to latest if not passed in
    if snapshot_id:
        restore_dict['spec']['snapshot'] = snapshot_id
    restore_dict['spec']['restoreMethod']['folder']['claimName'] = pvc
    restore_dict['spec']['backend']['repoPasswordSecretRef']['name'] = f"{app}-backups-credentials"
    restore_dict['spec']['backend']['s3']['endpoint'] = s3_endpoint
    restore_dict['spec']['backend']['s3']['bucket'] = s3_bucket
    restore_dict['spec']['backend']['s3']['accessKeyIDSecretRef']['name'] = f"{app}-backups-credentials"
    restore_dict['spec']['backend']['s3']['secretAccessKeySecretRef']['name'] = f"{app}-backups-credentials"
    # apply the k8up restore job
    k8s_obj.apply_custom_resources(restore_dict)


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
            "name": "cnpg",
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
                  "endpointURL": f"http://{s3_endpoint}",
                  "s3Credentials": {
                    "accessKeyId": {
                      "name": f"{app}-pgsql-credentials",
                      "key": "ACCESS_KEY_ID"
                      },
                    "secretAccessKey": {
                      "name": f"{app}-pgsql-credentials",
                      "key": "ACCESS_SECRET_KEY"
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

    release_dict = {"release_name": f"{app}-postgres-cluster",
                    "namespace": namespace,
                    "values_file": values_file_name}
    release = Helm.chart(**release_dict)

    # this actually applies the helm chart release we've defined above
    release.install(True)