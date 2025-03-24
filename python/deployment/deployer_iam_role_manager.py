import os
from dataclasses import dataclass
from google.cloud import resourcemanager_v3
from google.cloud import iam_admin_v1
from google.iam.v1 import iam_policy_pb2
from google.cloud.iam_admin_v1 import types
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

@dataclass
class DeploymentUserConfig:
    project_id: str
    user_account: str
    use_deployer_service_account: bool
    deployer_account: str

    def __post_init__(self):
        if not self.use_deployer_service_account:
            self.deployer_account = self.user_account
        elif not self.deployer_account:
            self.deployer_account = f"deployer@{self.project_id}.iam.gserviceaccount.com"
        self.user_account_member_str = _get_account_member_string(self.user_account)
        self.deployer_account_member_str = _get_account_member_string(self.deployer_account)
        self.project_resource = f"projects/{self.project_id}"


def _get_account_member_string(account_id):
    service_account_member_prefix = r"serviceAccount:"
    user_account_member_prefix = r"user:"
    account_id = account_id.strip()
    if account_id.startswith((service_account_member_prefix, user_account_member_prefix)):
        return account_id
    elif r"gserviceaccount" in account_id:
        return f"{service_account_member_prefix}{account_id}"
    else:
        return f"{user_account_member_prefix}{account_id}"


def get_deployment_user_project_roles(deployment_user_config: DeploymentUserConfig):
    client = resourcemanager_v3.ProjectsClient()
    request = iam_policy_pb2.GetIamPolicyRequest(resource=deployment_user_config.project_resource)
    response = client.get_iam_policy(request=request)
    deployment_user_config.deployer_account_roles = [binding.role for binding in response.bindings if deployment_user_config.deployer_account_member_str in binding.members]
    deployment_user_config.user_account_roles = [binding.role for binding in response.bindings if deployment_user_config.user_account_member_str in binding.members]


def get_roles_from_file(filepath):
    """Reads roles from a file, one role per line."""
    try:
        with open(filepath, "r") as f:
            return [line.strip() for line in f]
    except FileNotFoundError:
        logger.error(f"Roles file not found: {filepath}")
        return []
    except Exception as e:
        logger.error(f"Error reading roles file: {e}")
        return []

def get_missing_roles(deployment_user_config: DeploymentUserConfig, required_roles):
    get_deployment_user_project_roles(deployment_user_config)
    existing_roles = set(deployment_user_config.deployer_account_roles)
    return filter_missing_roles(existing_roles, required_roles)

def filter_missing_roles(existing_roles, required_roles):
    if "roles/owner" in existing_roles or "roles/admin" in existing_roles:
        return
    return [role for role in required_roles if role not in existing_roles]


def check_service_account_impersonation(deployment_user_config: DeploymentUserConfig):
    if deployment_user_config.use_deployer_service_account and deployment_user_config.user_account != deployment_user_config.deployer_account:
        token_creator_role = "roles/iam.serviceAccountTokenCreator"
        missing_roles = filter_missing_roles(deployment_user_config.user_account_roles, [token_creator_role])
        if missing_roles:
            logger.error(f"Missing {token_creator_role} on user account: {deployment_user_config.user_account}, which is required for service account impersonation.")
            return
    logger.info(f"The user account: {deployment_user_config.user_account} has the required role for running deployment with service account impersonation.")


def parse_deployment_user_config_from_env():
    project_id = os.environ.get("PROJECT_ID")
    if not project_id:
        logger.error("Environment variable PROJECT_ID is missing.")
        return
    user_account = os.environ.get("CURRENT_USER")
    if not user_account:
        logger.error("Environment variable CURRENT_USER is missing.")
        return
    use_deployer_sa = os.environ.get("MAJ_USE_DEPLOYER_SA")
    if use_deployer_sa:
        use_deployer_service_account = use_deployer_sa.lower() == "true"
    else:
        use_deployer_service_account = False
    
    return DeploymentUserConfig(
        project_id=project_id,
        user_account=user_account,
        use_deployer_service_account=use_deployer_service_account,
        deployer_account=os.environ.get("DEPLOYER_ACCOUNT")
    )
    

def check_missing_roles():
    deployment_user_config = parse_deployment_user_config_from_env()
    if not deployment_user_config:
        return

    ROLES_FILE_PATH = "scripts/deployer_roles.txt"    
    required_roles = get_roles_from_file(ROLES_FILE_PATH)
    if not required_roles:
        logger.error("Required roles list is empty.")
        return

    missing_roles = get_missing_roles(deployment_user_config, required_roles)
    if missing_roles:
        logger.error(f"Following required roles are missing for account: {deployment_user_config.deployer_account}")
        for role in missing_roles:
            logger.error(role)
    else:
        logger.info(f"{deployment_user_config.deployer_account=} has all the required roles.")
    check_service_account_impersonation(deployment_user_config)
    return deployment_user_config.deployer_account


if __name__ == "__main__":
    check_missing_roles()