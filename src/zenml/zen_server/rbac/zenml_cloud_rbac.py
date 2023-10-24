#  Copyright (c) ZenML GmbH 2023. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at:
#
#       https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
#  or implied. See the License for the specific language governing
#  permissions and limitations under the License.
"""Cloud RBAC implementation."""
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

import requests
from pydantic import BaseModel, validator

from zenml.zen_server.rbac.models import Resource
from zenml.zen_server.rbac.rbac_interface import RBACInterface
from zenml.zen_server.utils import server_config

if TYPE_CHECKING:
    from zenml.models import UserResponseModel


ZENML_CLOUD_RBAC_ENV_PREFIX = "ZENML_CLOUD_"
PERMISSIONS_ENDPOINT = "/rbac/check_permissions"
ALLOWED_RESOURCE_IDS_ENDPOINT = "/rbac/allowed_resource_ids"

SERVER_SCOPE_IDENTIFIER = "server"

SERVER_ID = server_config().external_server_id


def _convert_to_cloud_resource(resource: Resource) -> str:
    """Convert a resource to a ZenML Cloud API resource.

    Args:
        resource: The resource to convert.

    Returns:
        The converted resource.
    """
    resource_string = f"{SERVER_ID}@{SERVER_SCOPE_IDENTIFIER}:{resource.type}"

    if resource.id:
        resource_string += f"/{resource.id}"

    return resource_string


class ZenMLCloudRBACConfiguration(BaseModel):
    """ZenML Cloud RBAC configuration."""

    api_url: str

    oauth2_client_id: str
    oauth2_client_secret: str
    oauth2_audience: str
    auth0_domain: str

    @validator("api_url")
    def _strip_trailing_slashes_url(cls, url: str) -> str:
        """Strip any trailing slashes on the API URL.

        Args:
            url: The API URL.

        Returns:
            The API URL with potential trailing slashes removed.
        """
        return url.rstrip("/")

    @classmethod
    def from_environment(cls) -> "ZenMLCloudRBACConfiguration":
        """Get the RBAC configuration from environment variables.

        Returns:
            The RBAC configuration.
        """
        env_config: Dict[str, Any] = {}
        for k, v in os.environ.items():
            if v == "":
                continue
            if k.startswith(ZENML_CLOUD_RBAC_ENV_PREFIX):
                env_config[k[len(ZENML_CLOUD_RBAC_ENV_PREFIX) :].lower()] = v

        return ZenMLCloudRBACConfiguration(**env_config)

    class Config:
        """Pydantic configuration class."""

        # Allow extra attributes from configs of previous ZenML versions to
        # permit downgrading
        extra = "allow"


class ZenMLCloudRBAC(RBACInterface):
    """RBAC implementation that uses the ZenML Cloud API as a backend."""

    def __init__(self) -> None:
        """Initialize the RBAC component."""
        self._config = ZenMLCloudRBACConfiguration.from_environment()
        self._session: Optional[requests.Session] = None

    def check_permissions(
        self, user: "UserResponseModel", resources: Set[Resource], action: str
    ) -> Dict[Resource, bool]:
        """Checks if a user has permissions to perform an action on resources.

        Args:
            user: User which wants to access a resource.
            resources: The resources the user wants to access.
            action: The action that the user wants to perform on the resources.

        Returns:
            A dictionary mapping resources to a boolean which indicates whether
            the user has permissions to perform the action on that resource.
        """
        assert user.external_user_id

        if not resources:
            # No need to send a request if there are no resources
            return {}

        params = {
            "user_id": str(user.external_user_id),
            "resources": [
                _convert_to_cloud_resource(resource) for resource in resources
            ],
            "action": action,
        }
        response = self._get(endpoint=PERMISSIONS_ENDPOINT, params=params)
        value = response.json()

        assert isinstance(value, dict)
        return value

    def list_allowed_resource_ids(
        self, user: "UserResponseModel", resource: Resource, action: str
    ) -> Tuple[bool, List[str]]:
        """Lists all resource IDs of a resource type that a user can access.

        Args:
            user: User which wants to access a resource.
            resource: The resource the user wants to access.
            action: The action that the user wants to perform on the resource.

        Returns:
            A tuple (full_resource_access, resource_ids).
            `full_resource_access` will be `True` if the user can perform the
            given action on any instance of the given resource type, `False`
            otherwise. If `full_resource_access` is `False`, `resource_ids`
            will contain the list of instance IDs that the user can perform
            the action on.
        """
        assert not resource.id
        assert user.external_user_id
        params = {
            "user_id": str(user.external_user_id),
            "resource": _convert_to_cloud_resource(resource),
            "action": action,
        }
        response = self._get(
            endpoint=ALLOWED_RESOURCE_IDS_ENDPOINT, params=params
        )
        response_json = response.json()

        full_resource_access: bool = response_json["full_access"]
        allowed_ids: List[str] = response_json["ids"]

        return full_resource_access, allowed_ids

    def _get(self, endpoint: str, params: Dict[str, Any]) -> requests.Response:
        """Send a GET request using the active session.

        Args:
            endpoint: The endpoint to send the request to. This will be appended
                to the base URL.
            params: Parameters to include in the request.

        Raises:
            RuntimeError: If the request failed.

        Returns:
            The response.
        """
        url = self._config.api_url + endpoint

        response = self.session.get(url=url, params=params)
        if response.status_code == 401:
            # Refresh the auth token and try again
            self._clear_session()
            response = self.session.get(url=url, params=params)

        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            raise RuntimeError(
                "Failed while trying to contact RBAC service."
            ) from e

        return response

    @property
    def session(self) -> requests.Session:
        """Authenticate to the ZenML Cloud API.

        Returns:
            A requests session with the authentication token.
        """
        if self._session is None:
            self._session = requests.Session()
            token = self._fetch_auth_token()
            self._session.headers.update({"Authorization": "Bearer " + token})

        return self._session

    def _clear_session(self) -> None:
        """Clear the authentication session."""
        self._session = None

    def _fetch_auth_token(self) -> str:
        """Fetch an auth token for the Cloud API from auth0.

        Raises:
            RuntimeError: If the auth token can't be fetched.

        Returns:
            Auth token.
        """
        # Get an auth token from auth0
        auth0_url = f"https://{self._config.auth0_domain}/oauth/token"
        headers = {"content-type": "application/x-www-form-urlencoded"}
        payload = {
            "client_id": self._config.oauth2_client_id,
            "client_secret": self._config.oauth2_client_secret,
            "audience": self._config.oauth2_audience,
            "grant_type": "client_credentials",
        }
        try:
            response = requests.post(auth0_url, headers=headers, data=payload)
            response.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Error fetching auth token from auth0: {e}")

        access_token = response.json().get("access_token", "")

        if not access_token or not isinstance(access_token, str):
            raise RuntimeError("Could not fetch auth token from auth0.")

        return access_token
