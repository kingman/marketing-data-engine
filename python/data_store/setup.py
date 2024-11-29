# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import sys
from dataclasses import dataclass
from google.api_core.client_info import ClientInfo
from google.cloud import bigquery
from typing import Optional

@dataclass
class BqDatasetUserPermission:
    """
    Represents a BigQuery dataset user permission configuration.

    Attributes:
        user_email: The email address of the user.
        project_id: The ID of the Google Cloud project.
        dataset: The ID of the BigQuery dataset.
        role: The role to grant the user (default: "OWNER").
    """
    user_email: str
    project_id: str
    dataset: str
    role: str="OWNER"

    def __post_init__(self):
        self.dataset_id = f'{self.project_id}.{self.dataset}'

class GoogleClientManager:
    """
    Manages the BigQuery client instance.
    """
    bq_client: Optional[bigquery.Client] = None
    client_info = ClientInfo(user_agent="cloud-solutions/marketing-analytics-jumpstart-deploy-v1.0")

    @classmethod
    def get_bq_client(cls):
        """
        Returns a BigQuery client instance, creating one if it doesn't exist.
        """
        if cls.bq_client is None:
            cls.bq_client = bigquery.Client(client_info=cls.client_info)
        return cls.bq_client


def parse_hcl_obj_list(hcl_obj_list_str: str, user_email: str):
    """
    Parses a string containing an HCL-like list of objects into a list of BqDatasetUserPermission objects.

    Args:
        hcl_obj_list_str: The HCL-like string to parse.
        user_email: The email address to associate with the permissions.

    Returns:
        A list of BqDatasetUserPermission objects.
    """
    return [BqDatasetUserPermission(
        project_id=obj['project'],
        dataset=obj['dataset'],
        user_email=user_email

    ) for obj in json.loads(hcl_obj_list_str
                            .replace(r' ', '')
                            .replace(r'="', r'":"')
                            .replace(r'{', r'{"')
                            .replace(r',', r',"'))]


def get_env_config():
    """
    Retrieves BigQuery dataset permission configurations from environment variables.

    Returns:
        A list of BqDatasetUserPermission objects.
    """
    TF_VAR_source_ga4_export_project_id = os.getenv("TF_VAR_source_ga4_export_project_id")
    TF_VAR_source_ga4_export_dataset = os.getenv("TF_VAR_source_ga4_export_dataset")
    TF_VAR_source_ads_export_data = os.getenv("TF_VAR_source_ads_export_data")
    _DEPLOYER_SA = os.getenv("_DEPLOYER_SA")
    if not _DEPLOYER_SA:
        message = (
            f"Environment variables missing; "
            f"{_DEPLOYER_SA=}, "
        )
        print(message)
        sys.exit(1)
    if not TF_VAR_source_ga4_export_project_id or not TF_VAR_source_ga4_export_dataset:
        message = (
            f"Environment variables missing; "
            f"{TF_VAR_source_ga4_export_project_id=}, "
            f"{TF_VAR_source_ga4_export_dataset=}, "
        )
        print(message)
        sys.exit(1)
    permission_list = []
    
    access_ga4_export_permission = BqDatasetUserPermission(
        project_id=TF_VAR_source_ga4_export_project_id,
        dataset=TF_VAR_source_ga4_export_dataset,
        user_email=_DEPLOYER_SA
    )
    permission_list.append(access_ga4_export_permission)

    if TF_VAR_source_ads_export_data:
        access_ads_export_permissions =  parse_hcl_obj_list(TF_VAR_source_ads_export_data, _DEPLOYER_SA)
        permission_list.extend(access_ads_export_permissions)
    
    return permission_list

def get_dataset(dataset_id: str):
    """
    Retrieves a BigQuery dataset by ID.

    Args:
        dataset_id: The ID of the dataset in the format 'project_id.dataset_id'.

    Returns:
        The BigQuery dataset object.
    """
    client = GoogleClientManager.get_bq_client()
    try:
        return client.get_dataset(dataset_id)
    except Exception as e:
        print(f'dataset: {dataset_id} was not found, ensure the dataset does exist and the current user has access to it.')
        sys.exit(1)


def check_permission_is_set(permission: BqDatasetUserPermission):
    """
    Checks if the specified permission is already set on the dataset.

    Args:
        permission: The BqDatasetUserPermission object representing the permission.

    Returns:
        True if the permission is set, False otherwise.
    """
    for access_entry in get_dataset(permission.dataset_id).access_entries:
        if access_entry.entity_id == permission.user_email and access_entry.role == permission.role:
            return True
    return False

def verify_update(dataset, permission: BqDatasetUserPermission):
    """
    Verifies that the permission was successfully added to the dataset.

    Args:
        dataset: The updated BigQuery dataset object.
        permission: The BqDatasetUserPermission object representing the permission.
    """
    for access_entry in dataset.access_entries:
        if access_entry.entity_id == permission.user_email and access_entry.role == permission.role:
            print(f'Added entity: {permission.user_email} as {permission.role} on dataset: {permission.dataset_id}')
            return


def set_permission(permission: BqDatasetUserPermission):
    """
    Sets the specified permission on the BigQuery dataset.

    Args:
        permission: The BqDatasetUserPermission object representing the permission.
    """
    dataset = get_dataset(permission.dataset_id)
    update_entries = list(dataset.access_entries)
    update_entries.append(
        bigquery.AccessEntry(
            role=permission.role,
            entity_type="userByEmail",
            entity_id=permission.user_email,
        )
    )
    dataset.access_entries = update_entries
    client = GoogleClientManager.get_bq_client()
    updated_dataset = client.update_dataset(dataset, ["access_entries"])
    verify_update(updated_dataset, permission)


def check_and_set_permission(permission: BqDatasetUserPermission):
    """
    Checks if the permission is set and sets it if it's not.

    Args:
        permission: The BqDatasetUserPermission object representing the permission.
    """
    if not check_permission_is_set(permission):
        set_permission(permission)


def set_bq_permission():
    """
    Sets BigQuery dataset permissions based on environment variables.
    """
    permission_list = get_env_config()
    for p_config in permission_list:
        check_and_set_permission(p_config)


if __name__ == "__main__":
    set_bq_permission()