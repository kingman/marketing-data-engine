#!/usr/bin/env sh

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

ERR_VARIABLE_NOT_DEFINED=2
ERR_MISSING_DEPENDENCY=3

CYAN='\033[0;36m'
BCYAN='\033[1;36m'
NC='\033[0m' # No Color
DIVIDER=$(printf %"$(tput cols)"s | tr " " "*")

get_project_id() {
    local __resultvar=$1
    VALUE=$(gcloud config get-value project | xargs)
    eval $__resultvar="'$VALUE'"
}

get_project_number() {
    local __resultvar=$1
    local PRO=$2
    VALUE=$(gcloud projects list --filter="project_id=$PRO" --format="value(PROJECT_NUMBER)" | xargs)
    eval $__resultvar="'$VALUE'"
}

# DISPLAY HELPERS

section_open() {
    section_description=$1
    printf "$DIVIDER"
    printf "${CYAN}$section_description${NC} \n"
    printf "$DIVIDER"
}

section_close() {
    printf "$DIVIDER"
    printf "${CYAN}$section_description ${BCYAN}- done${NC}\n"
    printf "\n\n"
}

check_exec_dependency() {
  EXECUTABLE_NAME="${1}"

  if ! command -v "${EXECUTABLE_NAME}" >/dev/null 2>&1; then
    echo "[ERROR]: ${EXECUTABLE_NAME} command is not available, but it's needed. Make it available in PATH and try again. Terminating..."
    exit ${ERR_MISSING_DEPENDENCY}
  fi

  unset EXECUTABLE_NAME
}

check_exec_version() {
  EXECUTABLE_NAME="${1}"

  if ! "${EXECUTABLE_NAME}" --version 2>&1; then
    echo "[ERROR]: ${EXECUTABLE_NAME} command is not available, but it's needed. Make it available in PATH and try again. Terminating..."
    exit ${ERR_MISSING_DEPENDENCY}
  fi

  unset EXECUTABLE_NAME
}

check_environment_variable() {
  _VARIABLE_NAME=$1
  _ERROR_MESSAGE=$2
  _VARIABLE_VALUE="${!_VARIABLE_NAME:-}"
  if [ -z "${_VARIABLE_VALUE}" ]; then
    echo "[ERROR]: ${_VARIABLE_NAME} environment variable that points to ${_ERROR_MESSAGE} is not defined. Terminating..."
    exit ${ERR_VARIABLE_NOT_DEFINED}
  fi
  unset _VARIABLE_NAME
  unset _ERROR_MESSAGE
  unset _VARIABLE_VALUE
}

set_environment_variable_if_not_set() {
  _VARIABLE_NAME=$1
  _VALUE_TO_SET=$2
  _VARIABLE_VALUE="${!_VARIABLE_NAME:-}"
  if [ -z "${_VARIABLE_VALUE}" ]; then
    export "${_VARIABLE_NAME}"="${_VALUE_TO_SET}"
  fi
  unset _VARIABLE_NAME
  unset _VALUE_TO_SET
  unset _VARIABLE_VALUE
}

create_service_account_and_enable_impersonation() {
  if [ -z "${SERVICE_ACCOUNT_ID:-}" ]; then
    export SERVICE_ACCOUNT_ID="deployer@$PROJECT_ID.iam.gserviceaccount.com"
    echo "using default name 'deployer' for SERVICE_ACCOUNT_ID"
  fi
  set +e # Disable errexit
  __deployer_sa=$(gcloud iam service-accounts list --format="value(email)" | grep "$SERVICE_ACCOUNT_ID")
  set -e # Re-enable errexit
  if [[ $__deployer_sa ]]; then
    echo "$__deployer_sa has already been created"
  else
    gcloud iam service-accounts create deployer \
      --description="The service account used to deploy Marketing Analytics Jumpstart resources" \
      --display-name="MAJ deployer service account" \
      --project="$PROJECT_ID"
  fi
  enable_role "roles/iam.serviceAccountTokenCreator" "user:$CURRENT_USER" "$SERVICE_ACCOUNT_ID"
  unset __deployer_sa
}

# shell script function to enable IAM roles
enable_role() {
  local __role=$1 __principal=$2 __resource=$3
  echo "granting IAM Role $__role to $__principal at resource $__resource "
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --role="$__role" --member="$__principal" 1>/dev/null
  unset __role
  unset __principal
}

# enable all roles in the roles array for service account used to deploy terraform resources
enable_deployer_roles() {
  local __principal="serviceAccount:$1"
  readarray -t roles_array <scripts/deployer_roles.txt
  for i in "${roles_array[@]}"; do
    enable_role "${i/\$\{PROJECT_ID\}/"$PROJECT_ID"}" "$__principal" "projects/$PROJECT_ID"
  done
  unset __principal
}

set_environment_variable_from_input_or_default_if_not_set() {
  _VARIABLE_NAME=$1
  _VALUE_TO_SET=$2
  _VALUE_DESC=$3
  _ENTITY_DESC=$4
  _VARIABLE_VALUE="${!_VARIABLE_NAME:-}"
  if [ -z "${_VARIABLE_VALUE}" ]; then
    echo Input ${_VALUE_DESC} for ${_ENTITY_DESC} or press Enter to use the default ${_VALUE_DESC}: ${_VALUE_TO_SET}
    read _INPUT
    if [[ ${_INPUT} == "" ]]; then
      export "${_VARIABLE_NAME}"="${_VALUE_TO_SET}"
    else
      export "${_VARIABLE_NAME}"="${_INPUT}"
    fi
  fi
  unset _VARIABLE_NAME
  unset _VALUE_TO_SET
  unset _VARIABLE_VALUE
  unset _VALUE_DESC
  unset _ENTITY_DESC
  unset _INPUT
}

set_environment_variable_from_input_if_not_set() {
  _VARIABLE_NAME=$1
  _VALUE_DESC=$2
  _ENTITY_DESC=$3
  _VARIABLE_VALUE="${!_VARIABLE_NAME:-}"
  if [ -z "${_VARIABLE_VALUE}" ]; then
    echo Input ${_VALUE_DESC} for ${_ENTITY_DESC}:
    _INPUT=
    while [[ ${_INPUT} = "" ]]; do
      read _INPUT
    done
    export "${_VARIABLE_NAME}"="${_INPUT}"
  fi
  unset _VARIABLE_NAME
  unset _VARIABLE_VALUE
  unset _VALUE_DESC
  unset _ENTITY_DESC
  unset _INPUT
}

run_terraform() {
  _TERRAFORM_RUN_DIR=$1
  terraform -chdir="${_TERRAFORM_RUN_DIR}" version
  terraform -chdir="${_TERRAFORM_RUN_DIR}" init -input=false
  terraform -chdir="${_TERRAFORM_RUN_DIR}" validate
  terraform -chdir="${_TERRAFORM_RUN_DIR}" apply -input=false -auto-approve
  unset _TERRAFORM_RUN_DIR
}

create_terraform_variables_file() {
  _TERRAFORM_RUN_DIR=$1
  _TERRAFORM_VARIABLE_FILE_PATH=${_TERRAFORM_RUN_DIR}/terraform.tfvars
  echo "Generate the terraform variables in ${_TERRAFORM_VARIABLE_FILE_PATH}"
  if [ -f "${_TERRAFORM_VARIABLE_FILE_PATH}" ]; then
    echo "The ${_TERRAFORM_VARIABLE_FILE_PATH} file already exists."
  else
    envsubst < "${_TERRAFORM_RUN_DIR}/terraform.tfvars.template" > "${_TERRAFORM_VARIABLE_FILE_PATH}"
  fi

  unset _TERRAFORM_RUN_DIR
  unset _TERRAFORM_VARIABLE_FILE_PATH
}

create_terraform_backend_config_file() {
  _TERRAFORM_RUN_DIR=$1
  _TF_STATE_BUCKET=$2
  _TERRAFORM_BACKEND_CONFIGURATION_FILE_PATH="${_TERRAFORM_RUN_DIR}/backend.tf"
  echo "Generating the Terraform backend configuration file: ${_TERRAFORM_BACKEND_CONFIGURATION_FILE_PATH}"
  if [ -f "${_TERRAFORM_BACKEND_CONFIGURATION_FILE_PATH}" ]; then
    echo "The ${_TERRAFORM_BACKEND_CONFIGURATION_FILE_PATH} file already exists."
  else
    tee "${_TERRAFORM_BACKEND_CONFIGURATION_FILE_PATH}" <<EOF
terraform {
  backend "gcs" {
    bucket = "${_TF_STATE_BUCKET}"
    prefix = "state"
  }
}
EOF
  fi
  unset _TERRAFORM_RUN_DIR
  unset _TF_STATE_BUCKET
  unset _TERRAFORM_BACKEND_CONFIGURATION_FILE_PATH
}

set_application_default_credentials() {
  _SOURCE_ROOT=$1
  _CREDENTIAL_FILE_DIR="${_SOURCE_ROOT}/.credentials"
  _CREDENTIAL_FILE_PATH="${_CREDENTIAL_FILE_DIR}/application_default_credentials.json"
  if [ ! -f "${_CREDENTIAL_FILE_PATH}" ]; then
    _AUTH_OUTPUT=$( gcloud auth application-default login --quiet --scopes="openid,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/sqlservice.login,https://www.googleapis.com/auth/analytics,https://www.googleapis.com/auth/analytics.edit,https://www.googleapis.com/auth/analytics.provision,https://www.googleapis.com/auth/analytics.readonly,https://www.googleapis.com/auth/accounts.reauth" 2>&1 | tee /dev/tty )
    _CRED_PATH=$( echo ${_AUTH_OUTPUT} | cut -d "[" -f2 | cut -d "]" -f1 )
    mkdir -p "${_CREDENTIAL_FILE_DIR}" && cp "${_CRED_PATH}" "${_CREDENTIAL_FILE_PATH}"
    unset _CRED_PATH
    unset _AUTH_OUTPUT
  fi
  export GOOGLE_APPLICATION_CREDENTIALS="${_CREDENTIAL_FILE_PATH}"
  unset _CREDENTIAL_FILE_PATH
  unset _CREDENTIAL_FILE_DIR
  unset _SOURCE_ROOT
}

# shell script function to check if api is enabled
check_apis_enabled(){
    local __api_endpoint=$1
    COUNTER=0
    MAX_TRIES=100
    while ! gcloud services list --project=$PROJECT_ID | grep -i $__api_endpoint && [ $COUNTER -lt $MAX_TRIES ]
    do
        sleep 6
        printf "."
        COUNTER=$((COUNTER + 1))
    done
    if [ $COUNTER -eq $MAX_TRIES ]; then
        echo "${__api_endpoint} api is not enabled, installation can not continue!"
        exit 1
    else
        echo "${__api_endpoint} api is enabled"
    fi
    unset __api_endpoint
}

# shell script function to enable api
enable_apis(){
    local __api_endpoint=$1
    gcloud services enable $__api_endpoint
    check_apis_enabled $__api_endpoint
    unset __api_endpoint
}

# enable all apis in the array
enable_all_apis() {
  readarray -t apis_array <scripts/project_apis.txt
  for i in "${apis_array[@]}"; do
    enable_api "$i"
  done
}
