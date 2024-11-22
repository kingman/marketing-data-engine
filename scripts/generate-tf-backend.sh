#!/usr/bin/env bash

# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -o errexit
set -o nounset

. scripts/common.sh

section_open "Check if the necessary dependencies are available: gcloud, gsutil, terraform, uv"
    check_exec_dependency "gcloud"
    check_exec_version "gcloud"
    check_exec_dependency "gsutil"
    check_exec_version "gsutil"
    check_exec_dependency "terraform"
    check_exec_version "terraform"
    check_exec_dependency "uv"
    check_exec_version "uv"
section_close

section_open "Check if the necessary variables are set: PROJECT_ID"
    check_environment_variable "PROJECT_ID" "the Google Cloud project that Terraform will provision the resources in"
section_close

section_open  "Setting the Google Cloud project to TF_STATE_PROJECT"
    set_environment_variable_if_not_set "TF_STATE_PROJECT" "${PROJECT_ID}"
    CURRENT_USER=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
    set_active_principal
    gcloud config unset billing/quota_project
    gcloud config set project "${TF_STATE_PROJECT}"
section_close

section_open "Enable all the required APIs"
    enable_all_apis
section_close

if [ -z "${MAJ_USE_DEPLOYER_SA:-}" ]; then
    echo "Use ${CURRENT_USER} for deployment"
else
    if [[ "${MAJ_USE_DEPLOYER_SA}" == "true" ]]; then
    section_open "Create deployer service account and enable $CURRENT_USER to use service account impersonation "
        create_service_account_and_enable_impersonation
    section_close
    section_open "Enable all the required IAM roles for deployer service account, serviceAccount:""${SERVICE_ACCOUNT_ID}"""
        enable_deployer_roles "${SERVICE_ACCOUNT_ID}"
    section_close
    section_open "Set Application Default Credentials to be used by Terraform"
        gcloud auth application-default login --impersonate-service-account="${SERVICE_ACCOUNT_ID}"
    section_close
    fi
fi

section_open  "Check and set the LOCATION variable"
    set_environment_variable_if_not_set "LOCATION" "us-central1"
section_close

section_open  "Check and set the TF_STATE_BUCKET variable"
    set_environment_variable_if_not_set "TF_STATE_BUCKET" "${TF_STATE_PROJECT}-terraform-state"
section_close

section_open "Creating a new Google Cloud Storage bucket to store the Terraform state in ${TF_STATE_PROJECT} project, bucket: ${TF_STATE_BUCKET}"
    if gsutil ls -b gs://"${TF_STATE_BUCKET}" >/dev/null 2>&1; then
        printf "The ${TF_STATE_BUCKET} Google Cloud Storage bucket already exists. \n"
    else
        gsutil mb -p "${TF_STATE_PROJECT}" --pap enforced -l "${LOCATION}" -b on gs://"${TF_STATE_BUCKET}"
        gsutil versioning set on gs://"${TF_STATE_BUCKET}"
    fi
section_close

section_open "Creating terraform backend.tf configuration file"
    TERRAFORM_RUN_DIR="infrastructure/terraform"
    create_terraform_backend_config_file "${TERRAFORM_RUN_DIR}" "${TF_STATE_BUCKET}"
section_close

printf "$DIVIDER"
printf "You got the end the of your generate-tf-backend script with everything working. \n"
printf "$DIVIDER"
