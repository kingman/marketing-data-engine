import os
import pytest
import time

from google.cloud import dataform_v1beta1
from google.cloud import workflows_v1
from google.cloud.workflows import executions_v1
from google.cloud.workflows.executions_v1 import Execution
from google.cloud.workflows.executions_v1.types import executions


from google.cloud import bigquery

from google.cloud import workflows_v1

PROJECT = os.getenv("PROJECT_ID")
LOCATION = os.getenv("REGION", "us-central1")
GA4_PROPERTY = os.getenv("GA4_PROPERTY_ID")

@pytest.mark.dataform
def test_dataform_execution():
    assert PROJECT, "'PROJECT_ID' environment variable not set."
    assert GA4_PROPERTY, "'GA4_PROPERTY_ID' environment variable not set."

    # Initial workflow run
    workflow_execution = execute_workflow(PROJECT, LOCATION, f"dataform-{GA4_PROPERTY}-incremental")
    assert workflow_execution.state == executions.Execution.State.SUCCEEDED
    invocation = wait_latest_dataform(PROJECT, LOCATION)
    assert invocation, "Dataform invocation not found"
    check_analytics_tables_are_populated(PROJECT, GA4_PROPERTY)

    # Run the workflow the 2nd time to trigger incremental flow
    workflow_execution = execute_workflow(PROJECT, LOCATION, f"dataform-{GA4_PROPERTY}-incremental")
    assert workflow_execution.state == executions.Execution.State.SUCCEEDED
    invocation = wait_latest_dataform(PROJECT, LOCATION)
    assert invocation, "Dataform invocation not found"
    check_ads_tables_are_populated(PROJECT, GA4_PROPERTY)

def wait_latest_dataform(project, location, timeout_seconds=300):
    client = dataform_v1beta1.DataformClient()
    parent = f"projects/{project}/locations/{location}/repositories/marketing-analytics"
    request = dataform_v1beta1.ListWorkflowInvocationsRequest(parent=parent)
    latest_start_time = 0
    try:
        page_result = client.list_workflow_invocations(request=request)
        for response in page_result:
            if response.invocation_timing.start_time.seconds > latest_start_time:
                latest_start_time = response.invocation_timing.start_time.seconds
                latest_invocation = response
        if latest_invocation:
            start_time = time.time()
            while time.time() - start_time < timeout_seconds:
                 request = dataform_v1beta1.GetWorkflowInvocationRequest(name=latest_invocation.name)

                 invocation = client.get_workflow_invocation(request=request)

                 if invocation.state.name in ("SUCCEEDED", "FAILED", "CANCELLED"):
                     return invocation
                 print(f"Invocation in state: {invocation.state.name}")
                 time.sleep(30) # check every half minute.

            print(f"Timeout waiting for Dataform run: {latest_invocation.name}")
            return None #timeout reached.


    except Exception as e:
        print(f"Error retrieving Dataform run: {e}")
        return None


def execute_workflow(project: str, location: str, workflow: str) -> Execution:
    execution_client = executions_v1.ExecutionsClient()
    workflows_client = workflows_v1.WorkflowsClient()
    parent = workflows_client.workflow_path(project, location, workflow)

    # Execute the workflow.
    response = execution_client.create_execution(request={"parent": parent})
    print(f"Created execution: {response.name}")

    # Wait for execution to finish, then print results.
    execution_finished = False
    backoff_delay = 1  # Start wait with delay of 1 second
    print("Poll for result...")
    while not execution_finished:
        execution = execution_client.get_execution(
            request={"name": response.name}
        )
        execution_finished = execution.state != executions.Execution.State.ACTIVE

        # If we haven't seen the result yet, wait a second.
        if not execution_finished:
            print("- Waiting for results...")
            time.sleep(backoff_delay)
            # Double the delay to provide exponential backoff.
            backoff_delay *= 2
        else:
            print(f"Execution finished with state: {execution.state.name}")
            print(f"Execution results: {execution.result}")
            return execution
    # [END workflows_api_quickstart_execution]

def check_analytics_tables_are_populated(project, ga4_property_id):
    client = bigquery.Client(project=project)
    dataset_id = f'marketing_ga4_base_{ga4_property_id}'
    tables = [
        "browser",
        "collected_traffic_source",
        "device_type",
        "event",
        "location",
        "normalized_device_type",
        "pseudo_user_privacy_info",
        "pseudo_users",
        "session",
        "traffic_source"]
    for table in tables:
        assert not is_table_empty(client, project, dataset_id, table), f"{dataset_id}.{table} is empty"

def check_ads_tables_are_populated(project, ga4_property_id):
    client = bigquery.Client(project=project)
    dataset_id = f'marketing_ads_base_{ga4_property_id}'
    tables = [
        "dim_ads"]
    for table in tables:
        assert not is_table_empty(client, project, dataset_id, table), f"{dataset_id}.{table} is empty"


def is_table_empty(client, project_id, dataset_id, table_id):
    """Checks if a BigQuery table is empty."""
    table_ref = bigquery.DatasetReference(project_id, dataset_id).table(table_id)

    table = client.get_table(table_ref)

    if table.num_rows == 0:
        return True
    else:
        return False

   