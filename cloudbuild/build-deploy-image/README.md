# How use this image
1. Create artifact registry:
    ```bash
    gcloud artifacts repositories create ci \
      --project=$PROJECT_ID \
      --location=$LOCATION \
      --repository-format=docker
    ```
1. Run Cloud Build to build this deployer image in your project:

    ```bash
    cd cloudbuild/build-deploy-image
    gcloud builds submit \
      --project=$PROJECT_ID \
      --region=$LOCATION \
      --service-account "projects/${PROJECT_ID}/serviceAccounts/${BUILDER_SA_EMAIL}" \
      --default-buckets-behavior=regional-user-owned-bucket .
    ```
  **Note:** make sure the environment variables: `PROJECT_ID`, `LOCATION`, `BUILDER_SA_EMAIL` are set according to your requirements and the builder service account has the permissions for running a Cloud Build job that push the result image onto Artifact Registry.
