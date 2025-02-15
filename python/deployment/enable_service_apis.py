import os
from google.cloud import service_usage_v1
import logging
import logging.config

logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "[%(levelname)s|%(module)s|L%(lineno)d] %(asctime)s: %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "simple",
            "stream": "ext://sys.stdout",
        }
    },
    "loggers": {
        "root": {
            "level": "DEBUG",
            "handlers": [
                "console",
            ],
        }
    },
}

logging.config.dictConfig(logging_config)
logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

def get_project_api_services(project_id, api_names):
    client = service_usage_v1.ServiceUsageClient()
    request = service_usage_v1.BatchGetServicesRequest(parent=f"projects/{project_id}", names=api_names)
    response = client.batch_get_services(request=request)
    return [(service.name, service.state) for service in response.services]

def get_api_names_from_file(filepath, project_id):
    with open(filepath, "r") as f:
      return [f"projects/{project_id}/services/{line.strip()}" for line in f]

def enable_project_api_services(project_id, service_ids):
    client = service_usage_v1.ServiceUsageClient()
    index = 0
    while (index+1)*20 < len(service_ids):
        service_ids_sub_list = service_ids[index*20:(index+1)*20]
        _enable_project_api_services(client, project_id, service_ids_sub_list)        
        index += 1
    service_ids_sub_list = service_ids[index*20:]
    _enable_project_api_services(client, project_id, service_ids_sub_list)

def _enable_project_api_services(client, project_id, service_ids):
    request = service_usage_v1.BatchEnableServicesRequest(parent=f"projects/{project_id}", service_ids=service_ids)
    operation = client.batch_enable_services(request=request)
    response = operation.result()
    logger.info(response)


def service_apis_setup():
    PROJECT_ID = os.environ.get("PROJECT_ID")
    if not PROJECT_ID:
        logger.error("Environment variable PROJECT_ID is not set.")
        return
    else:
        API_FILE_PATH = "scripts/project_apis.txt"
    try:
        api_names = get_api_names_from_file(API_FILE_PATH, PROJECT_ID)
    except FileNotFoundError:
        logger.error(f"API file not found: {API_FILE_PATH}")
        return
    except Exception as e:
        logger.error(f"Error reading API file: {e}")
        return

    if api_names:
        try:
            project_api_services = get_project_api_services(PROJECT_ID, api_names)
            not_enabled_services = filter(lambda x: x[1] != service_usage_v1.State.ENABLED, project_api_services)
            not_enabled_service_ids = [service[0].split(r'/')[-1] for service in not_enabled_services]
            if not_enabled_service_ids:
                enable_project_api_services(PROJECT_ID, not_enabled_service_ids)
            else:
                logger.info("All required service APIs are enabled.")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    service_apis_setup()
