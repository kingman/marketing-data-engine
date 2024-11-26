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
SOURCE_ROOT=$(pwd)

. scripts/common.sh

section_open "Check if the necessary dependencies are available: gcloud, uv"
    check_exec_dependency "gcloud"
    check_exec_version "gcloud"
    check_exec_dependency "uv"
    check_exec_version "uv"
section_close

section_open "Check if the necessary variables are set: PROJECT_ID"
    check_environment_variable "PROJECT_ID" "the Google Cloud project that Terraform will provision the resources in"
section_close

section_open "Enable Google Analytics API"
    enable_apis "analyticsadmin.googleapis.com"
section_close

section_open "Check if the necessary variables are set: GA4_PROPERTY_ID"
    check_environment_variable "GA4_PROPERTY_ID" "the Google Analytics 4 property where the configurations are set and re-trieved"
section_close

section_open "Check if the necessary variables are set: GA4_STREAM_ID"
    check_environment_variable "GA4_STREAM_ID" "the Google Analytics 4 data stream where the configurations are set and re-trieved"
section_close


section_open "Setting Google Application Default Credentials with required scope for accessing Google Analytics 4"
    set_application_default_credentials "${SOURCE_ROOT}"
section_close

section_open "Check the provided Google Analytics 4 property: ${GA4_PROPERTY_ID} has correct type required by the solution."
    if ! uv run ga4-setup --ga4_resource=check_property_type | grep -i '"supported": "True"' ; then
      echo "Google Analytics 4 property ${GA4_PROPERTY_ID} property_type is not supported."
      exit 1
    fi
section_close

section_open "Create solution custom events under Google Analytics 4 property: ${GA4_PROPERTY_ID} and data stream: ${GA4_STREAM_ID}"
    if ! uv run ga4-setup --ga4_resource=custom_events ; then
        echo "Failed to create soluton custom events!"
        exit 1
    fi
section_close

section_open "Create solution custom user dimensions under Google Analytics 4 property: ${GA4_PROPERTY_ID} and data stream: ${GA4_STREAM_ID}"
    if ! uv run ga4-setup --ga4_resource=custom_dimensions ; then
        echo "Failed to create soluton custom user dimensions!"
        exit 1
    fi
section_close

section_open "Get measurement protocol ID and SECRET from Google Analytics 4 property: ${GA4_PROPERTY_ID} and data stream: ${GA4_STREAM_ID}"
    TF_ENV_FILE="${SOURCE_ROOT}/infrastructure/terraform/.env_tf_ga4"
    touch "${TF_ENV_FILE}"
    if ! uv run ga4-setup --ga4_resource=measurement_properties --tf_env_file="${TF_ENV_FILE}" ; then
        echo "Failed to get measurement protocol ID and SECRET!"
        exit 1
    fi
    . "${TF_ENV_FILE}"
    rm "${TF_ENV_FILE}"
section_close

set +o nounset
set +o errexit
