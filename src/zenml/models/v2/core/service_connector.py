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
"""Models representing service connectors."""

import json
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, List, Optional, Union
from uuid import UUID

from pydantic import Field, SecretStr, root_validator

from zenml.constants import STR_FIELD_MAX_LENGTH
from zenml.logger import get_logger
from zenml.models.v2.base.scoped import (
    ShareableFilter,
    ShareableRequest,
    ShareableResponse,
    ShareableResponseBody,
    ShareableResponseMetadata,
)
from zenml.models.v2.base.update import update_model
from zenml.models.v2.misc.service_connector_type import (
    ServiceConnectorTypeModel,
)

logger = get_logger(__name__)

# ------------------ Request Model ------------------


class ServiceConnectorRequest(ShareableRequest):
    """Request model for service connectors."""

    name: str = Field(
        title="The service connector name.",
        max_length=STR_FIELD_MAX_LENGTH,
    )
    connector_type: Union[str, "ServiceConnectorTypeModel"] = Field(
        title="The type of service connector.",
    )
    description: str = Field(
        default="",
        title="The service connector instance description.",
    )
    auth_method: str = Field(
        title="The authentication method that the connector instance uses to "
        "access the resources.",
        max_length=STR_FIELD_MAX_LENGTH,
    )
    resource_types: List[str] = Field(
        default_factory=list,
        title="The type(s) of resource that the connector instance can be used "
        "to gain access to.",
    )
    resource_id: Optional[str] = Field(
        default=None,
        title="Uniquely identifies a specific resource instance that the "
        "connector instance can be used to access. If omitted, the connector "
        "instance can be used to access any and all resource instances that "
        "the authentication method and resource type(s) allow.",
        max_length=STR_FIELD_MAX_LENGTH,
    )
    supports_instances: bool = Field(
        default=False,
        title="Indicates whether the connector instance can be used to access "
        "multiple instances of the configured resource type.",
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        title="Time when the authentication credentials configured for the "
        "connector expire. If omitted, the credentials do not expire.",
    )
    expiration_seconds: Optional[int] = Field(
        default=None,
        title="The duration, in seconds, that the temporary credentials "
        "generated by this connector should remain valid. Only applicable for "
        "connectors and authentication methods that involve generating "
        "temporary credentials from the ones configured in the connector.",
    )
    configuration: Dict[str, Any] = Field(
        default_factory=dict,
        title="The service connector configuration, not including secrets.",
    )
    secrets: Dict[str, Optional[SecretStr]] = Field(
        default_factory=dict,
        title="The service connector secrets.",
    )
    labels: Dict[str, str] = Field(
        default_factory=dict,
        title="Service connector labels.",
    )

    # Analytics
    ANALYTICS_FIELDS: ClassVar[List[str]] = [
        "connector_type",
        "auth_method",
        "resource_types",
    ]

    def get_analytics_metadata(self) -> Dict[str, Any]:
        """Format the resource types in the analytics metadata.

        Returns:
            Dict of analytics metadata.
        """
        metadata = super().get_analytics_metadata()
        if len(self.resource_types) == 1:
            metadata["resource_types"] = self.resource_types[0]
        else:
            metadata["resource_types"] = ", ".join(self.resource_types)
        metadata["connector_type"] = self.type
        return metadata

    # Helper methods
    @property
    def type(self) -> str:
        """Get the connector type.

        Returns:
            The connector type.
        """
        if isinstance(self.connector_type, str):
            return self.connector_type
        return self.connector_type.connector_type

    @property
    def emojified_connector_type(self) -> str:
        """Get the emojified connector type.

        Returns:
            The emojified connector type.
        """
        if not isinstance(self.connector_type, str):
            return self.connector_type.emojified_connector_type

        return self.connector_type

    @property
    def emojified_resource_types(self) -> List[str]:
        """Get the emojified connector type.

        Returns:
            The emojified connector type.
        """
        if not isinstance(self.connector_type, str):
            return [
                self.connector_type.resource_type_dict[
                    resource_type
                ].emojified_resource_type
                for resource_type in self.resource_types
            ]

        return self.resource_types

    def validate_and_configure_resources(
        self,
        connector_type: "ServiceConnectorTypeModel",
        resource_types: Optional[Union[str, List[str]]] = None,
        resource_id: Optional[str] = None,
        configuration: Optional[Dict[str, Any]] = None,
        secrets: Optional[Dict[str, Optional[SecretStr]]] = None,
    ) -> None:
        """Validate and configure the resources that the connector can be used to access.

        Args:
            connector_type: The connector type specification used to validate
                the connector configuration.
            resource_types: The type(s) of resource that the connector instance
                can be used to access. If omitted, a multi-type connector is
                configured.
            resource_id: Uniquely identifies a specific resource instance that
                the connector instance can be used to access.
            configuration: The connector configuration.
            secrets: The connector secrets.

        Raises:
            ValueError: If the connector configuration is not valid.
        """
        _validate_and_configure_resources(
            connector=self,
            connector_type=connector_type,
            resource_types=resource_types,
            resource_id=resource_id,
            configuration=configuration,
            secrets=secrets,
        )


# ------------------ Update Model ------------------


@update_model
class ServiceConnectorUpdate(ServiceConnectorRequest):
    """Model used for service connector updates.

    Most fields in the update model are optional and will not be updated if
    omitted. However, the following fields are "special" and leaving them out
    will also cause the corresponding value to be removed from the service
    connector in the database:

    * the `resource_id` field
    * the `expiration_seconds` field

    In addition to the above exceptions, the following rules apply:

    * the `configuration` and `secrets` fields together represent a full
    valid configuration update, not just a partial update. If either is
    set (i.e. not None) in the update, their values are merged together and
    will replace the existing configuration and secrets values.
    * the `secret_id` field value in the update is ignored, given that
    secrets are managed internally by the ZenML store.
    * the `labels` field is also a full labels update: if set (i.e. not
    `None`), all existing labels are removed and replaced by the new labels
    in the update.

    NOTE: the attributes here override the ones in the base class, so they
    have a None default value.
    """

    resource_types: Optional[List[str]] = Field(  # type: ignore[assignment]
        default=None,
        title="The type(s) of resource that the connector instance can be used "
        "to gain access to.",
    )
    configuration: Optional[Dict[str, Any]] = Field(  # type: ignore[assignment]
        default=None,
        title="The service connector configuration, not including secrets.",
    )
    secrets: Optional[Dict[str, Optional[SecretStr]]] = Field(  # type: ignore[assignment]
        default=None,
        title="The service connector secrets.",
    )
    labels: Optional[Dict[str, str]] = Field(  # type: ignore[assignment]
        default=None,
        title="Service connector labels.",
    )


# ------------------ Response Model ------------------


class ServiceConnectorResponseBody(ShareableResponseBody):
    """Response body for service connectors."""

    description: str = Field(
        default="",
        title="The service connector instance description.",
    )
    connector_type: Union[str, "ServiceConnectorTypeModel"] = Field(
        title="The type of service connector.",
    )
    auth_method: str = Field(
        title="The authentication method that the connector instance uses to "
        "access the resources.",
        max_length=STR_FIELD_MAX_LENGTH,
    )
    resource_types: List[str] = Field(
        default_factory=list,
        title="The type(s) of resource that the connector instance can be used "
        "to gain access to.",
    )
    resource_id: Optional[str] = Field(
        default=None,
        title="Uniquely identifies a specific resource instance that the "
        "connector instance can be used to access. If omitted, the connector "
        "instance can be used to access any and all resource instances that "
        "the authentication method and resource type(s) allow.",
        max_length=STR_FIELD_MAX_LENGTH,
    )
    supports_instances: bool = Field(
        default=False,
        title="Indicates whether the connector instance can be used to access "
        "multiple instances of the configured resource type.",
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        title="Time when the authentication credentials configured for the "
        "connector expire. If omitted, the credentials do not expire.",
    )


class ServiceConnectorResponseMetadata(ShareableResponseMetadata):
    """Response metadata for service connectors."""

    configuration: Dict[str, Any] = Field(
        default_factory=dict,
        title="The service connector configuration, not including secrets.",
    )
    secret_id: Optional[UUID] = Field(
        default=None,
        title="The ID of the secret that contains the service connector "
        "secret configuration values.",
    )
    expiration_seconds: Optional[int] = Field(
        default=None,
        title="The duration, in seconds, that the temporary credentials "
        "generated by this connector should remain valid. Only applicable for "
        "connectors and authentication methods that involve generating "
        "temporary credentials from the ones configured in the connector.",
    )
    secrets: Dict[str, Optional[SecretStr]] = Field(
        default_factory=dict,
        title="The service connector secrets.",
    )
    labels: Dict[str, str] = Field(
        default_factory=dict,
        title="Service connector labels.",
    )


class ServiceConnectorResponse(
    ShareableResponse[
        ServiceConnectorResponseBody, ServiceConnectorResponseMetadata
    ]
):
    """Response model for service connectors."""

    name: str = Field(
        title="The service connector name.",
        max_length=STR_FIELD_MAX_LENGTH,
    )

    def get_hydrated_version(self) -> "ServiceConnectorResponse":
        """Get the hydrated version of this service connector.

        Returns:
            an instance of the same entity with the metadata field attached.
        """
        from zenml.client import Client

        return Client().zen_store.get_service_connector(self.id)

    # Helper methods
    @property
    def type(self) -> str:
        """Get the connector type.

        Returns:
            The connector type.
        """
        if isinstance(self.connector_type, str):
            return self.connector_type
        return self.connector_type.connector_type

    @property
    def emojified_connector_type(self) -> str:
        """Get the emojified connector type.

        Returns:
            The emojified connector type.
        """
        if not isinstance(self.connector_type, str):
            return self.connector_type.emojified_connector_type

        return self.connector_type

    @property
    def emojified_resource_types(self) -> List[str]:
        """Get the emojified connector type.

        Returns:
            The emojified connector type.
        """
        if not isinstance(self.connector_type, str):
            return [
                self.connector_type.resource_type_dict[
                    resource_type
                ].emojified_resource_type
                for resource_type in self.resource_types
            ]

        return self.resource_types

    @property
    def is_multi_type(self) -> bool:
        """Checks if the connector is multi-type.

        A multi-type connector can be used to access multiple types of
        resources.

        Returns:
            True if the connector is multi-type, False otherwise.
        """
        return len(self.resource_types) > 1

    @property
    def is_multi_instance(self) -> bool:
        """Checks if the connector is multi-instance.

        A multi-instance connector is configured to access multiple instances
        of the configured resource type.

        Returns:
            True if the connector is multi-instance, False otherwise.
        """
        return (
            not self.is_multi_type
            and self.supports_instances
            and not self.resource_id
        )

    @property
    def is_single_instance(self) -> bool:
        """Checks if the connector is single-instance.

        A single-instance connector is configured to access only a single
        instance of the configured resource type or does not support multiple
        resource instances.

        Returns:
            True if the connector is single-instance, False otherwise.
        """
        return not self.is_multi_type and not self.is_multi_instance

    @property
    def full_configuration(self) -> Dict[str, str]:
        """Get the full connector configuration, including secrets.

        Returns:
            The full connector configuration, including secrets.
        """
        config = self.configuration.copy()
        config.update(
            {k: v.get_secret_value() for k, v in self.secrets.items() if v}
        )
        return config

    def has_expired(self) -> bool:
        """Check if the connector credentials have expired.

        Verify that the authentication credentials associated with the connector
        have not expired by checking the expiration time against the current
        time.

        Returns:
            True if the connector has expired, False otherwise.
        """
        if not self.expires_at:
            return False

        return self.expires_at < datetime.now(timezone.utc)

    def set_connector_type(
        self, value: Union[str, "ServiceConnectorTypeModel"]
    ) -> None:
        """Auxiliary method to set the connector type."""
        self.get_body().connector_type = value

    def validate_and_configure_resources(
        self,
        connector_type: "ServiceConnectorTypeModel",
        resource_types: Optional[Union[str, List[str]]] = None,
        resource_id: Optional[str] = None,
        configuration: Optional[Dict[str, Any]] = None,
        secrets: Optional[Dict[str, Optional[SecretStr]]] = None,
    ) -> None:
        """Validate and configure the resources that the connector can be used to access.

        Args:
            connector_type: The connector type specification used to validate
                the connector configuration.
            resource_types: The type(s) of resource that the connector instance
                can be used to access. If omitted, a multi-type connector is
                configured.
            resource_id: Uniquely identifies a specific resource instance that
                the connector instance can be used to access.
            configuration: The connector configuration.
            secrets: The connector secrets.

        Raises:
            ValueError: If the connector configuration is not valid.
        """
        _validate_and_configure_resources(
            connector=self,
            connector_type=connector_type,
            resource_types=resource_types,
            resource_id=resource_id,
            configuration=configuration,
            secrets=secrets,
        )

    # Body and metadata properties
    @property
    def description(self) -> str:
        """The `description` property.

        Returns:
            the value of the property.
        """
        return self.get_body().description

    @property
    def connector_type(self) -> Union[str, "ServiceConnectorTypeModel"]:
        """The `connector_type` property.

        Returns:
            the value of the property.
        """
        return self.get_body().connector_type

    @property
    def auth_method(self) -> str:
        """The `auth_method` property.

        Returns:
            the value of the property.
        """
        return self.get_body().auth_method

    @property
    def resource_types(self) -> List[str]:
        """The `resource_types` property.

        Returns:
            the value of the property.
        """
        return self.get_body().resource_types

    @property
    def resource_id(self) -> Optional[str]:
        """The `resource_id` property.

        Returns:
            the value of the property.
        """
        return self.get_body().resource_id

    @property
    def supports_instances(self) -> bool:
        """The `supports_instances` property.

        Returns:
            the value of the property.
        """
        return self.get_body().supports_instances

    @property
    def expires_at(self) -> Optional[datetime]:
        """The `expires_at` property.

        Returns:
            the value of the property.
        """
        return self.get_body().expires_at

    @property
    def configuration(self) -> Dict[str, Any]:
        """The `configuration` property.

        Returns:
            the value of the property.
        """
        return self.get_metadata().configuration

    @property
    def secret_id(self) -> Optional[UUID]:
        """The `secret_id` property.

        Returns:
            the value of the property.
        """
        return self.get_metadata().secret_id

    @property
    def expiration_seconds(self) -> Optional[int]:
        """The `expiration_seconds` property.

        Returns:
            the value of the property.
        """
        return self.get_metadata().expiration_seconds

    @property
    def secrets(self) -> Dict[str, Optional[SecretStr]]:
        """The `secrets` property.

        Returns:
            the value of the property.
        """
        return self.get_metadata().secrets

    @property
    def labels(self) -> Dict[str, str]:
        """The `labels` property.

        Returns:
            the value of the property.
        """
        return self.get_metadata().labels


# ------------------ Filter Model ------------------


class ServiceConnectorFilter(ShareableFilter):
    """Model to enable advanced filtering of service connectors."""

    FILTER_EXCLUDE_FIELDS: ClassVar[List[str]] = [
        *ShareableFilter.FILTER_EXCLUDE_FIELDS,
        "scope_type",
        "resource_type",
        "labels_str",
        "labels",
    ]
    CLI_EXCLUDE_FIELDS: ClassVar[List[str]] = [
        *ShareableFilter.CLI_EXCLUDE_FIELDS,
        "scope_type",
        "labels_str",
        "labels",
    ]
    scope_type: Optional[str] = Field(
        default=None,
        description="The type to scope this query to.",
    )

    is_shared: Optional[Union[bool, str]] = Field(
        default=None,
        description="If the service connector is shared or private",
    )
    name: Optional[str] = Field(
        default=None,
        description="The name to filter by",
    )
    connector_type: Optional[str] = Field(
        default=None,
        description="The type of service connector to filter by",
    )
    workspace_id: Optional[Union[UUID, str]] = Field(
        default=None, description="Workspace to filter by"
    )
    user_id: Optional[Union[UUID, str]] = Field(
        default=None, description="User to filter by"
    )
    auth_method: Optional[str] = Field(
        default=None,
        title="Filter by the authentication method configured for the "
        "connector",
    )
    resource_type: Optional[str] = Field(
        default=None,
        title="Filter by the type of resource that the connector can be used "
        "to access",
    )
    resource_id: Optional[str] = Field(
        default=None,
        title="Filter by the ID of the resource instance that the connector "
        "is configured to access",
    )
    labels_str: Optional[str] = Field(
        default=None,
        title="Filter by one or more labels. This field can be either a JSON "
        "formatted dictionary of label names and values, where the values are "
        'optional and can be set to None (e.g. `{"label1":"value1", "label2": '
        "null}` ), or a comma-separated list of label names and values (e.g "
        "`label1=value1,label2=`. If a label name is specified without a "
        "value, the filter will match all service connectors that have that "
        "label present, regardless of value.",
    )
    secret_id: Optional[Union[UUID, str]] = Field(
        default=None,
        title="Filter by the ID of the secret that contains the service "
        "connector's credentials",
    )

    # Use this internally to configure and access the labels as a dictionary
    labels: Optional[Dict[str, Optional[str]]] = Field(
        default=None,
        title="The labels to filter by, as a dictionary",
    )

    @root_validator
    def validate_labels(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the labels string into a label dictionary and vice-versa.

        Args:
            values: The values to validate.

        Returns:
            The validated values.
        """
        labels_str = values.get("labels_str")
        labels = values.get("labels")
        if labels_str is not None:
            try:
                values["labels"] = json.loads(labels_str)
            except json.JSONDecodeError:
                # Interpret as comma-separated values instead
                values["labels"] = {
                    label.split("=", 1)[0]: label.split("=", 1)[1]
                    if "=" in label
                    else None
                    for label in labels_str.split(",")
                }
        elif labels is not None:
            values["labels_str"] = json.dumps(values["labels"])

        return values

    class Config:
        """Pydantic config class."""

        # Exclude the labels field from the serialized response
        # (it is only used internally). The labels_str field is a string
        # representation of the labels that can be used in the API.
        exclude = ["labels"]


# ------------------ Helper Functions ------------------


def _validate_and_configure_resources(
    connector: Union[ServiceConnectorRequest, ServiceConnectorResponse],
    connector_type: "ServiceConnectorTypeModel",
    resource_types: Optional[Union[str, List[str]]] = None,
    resource_id: Optional[str] = None,
    configuration: Optional[Dict[str, Any]] = None,
    secrets: Optional[Dict[str, Optional[SecretStr]]] = None,
) -> None:
    """Validate and configure the resources that a connector can be used to access.

    Args:
        connector: The connector model to validate and configure.
        connector_type: The connector type specification used to validate
            the connector configuration.
        resource_types: The type(s) of resource that the connector instance
            can be used to access. If omitted, a multi-type connector is
            configured.
        resource_id: Uniquely identifies a specific resource instance that
            the connector instance can be used to access.
        configuration: The connector configuration.
        secrets: The connector secrets.

    Raises:
        ValueError: If the connector configuration is not valid.
    """
    # The fields that need to be updated are different between the request
    # and response models. For the request model, the fields are in the
    # connector model itself, while for the response model, they are in the
    # metadata field.
    update_connector_metadata: Union[
        ServiceConnectorRequest, ServiceConnectorResponseMetadata
    ]
    update_connector_body: Union[
        ServiceConnectorRequest, ServiceConnectorResponseBody
    ]
    if isinstance(connector, ServiceConnectorRequest):
        update_connector_metadata = connector
        update_connector_body = connector
    else:
        # Updating service connector responses must only be done on hydrated
        # instances, otherwise the metadata will be missing and we risk calling
        # the ZenML store to update the connector with additional information.
        # This is just a safety measure, but it will never happen because
        # this method will always be called on a hydrated response.
        if connector.metadata is None:
            raise RuntimeError(
                "Cannot update a service connector response that has not been "
                "hydrated yet."
            )
        update_connector_metadata = connector.get_metadata()
        update_connector_body = connector.get_body()

    if resource_types is None:
        resource_type = None
    elif isinstance(resource_types, str):
        resource_type = resource_types
    elif len(resource_types) == 1:
        resource_type = resource_types[0]
    else:
        # Multiple or no resource types specified
        resource_type = None

    try:
        # Validate the connector configuration and retrieve the resource
        # specification
        (
            auth_method_spec,
            resource_spec,
        ) = connector_type.find_resource_specifications(
            connector.auth_method,
            resource_type,
        )
    except (KeyError, ValueError) as e:
        raise ValueError(f"connector configuration is not valid: {e}") from e

    if resource_type and resource_spec:
        update_connector_body.resource_types = [resource_spec.resource_type]
        update_connector_body.resource_id = resource_id
        update_connector_body.supports_instances = (
            resource_spec.supports_instances
        )
    else:
        # A multi-type connector is associated with all resource types
        # that it supports, does not have a resource ID configured
        # and, it's unclear if it supports multiple instances or not
        update_connector_body.resource_types = list(
            connector_type.resource_type_dict.keys()
        )
        update_connector_body.supports_instances = False

    if configuration is None and secrets is None:
        # No configuration or secrets provided
        return

    update_connector_metadata.configuration = {}
    update_connector_metadata.secrets = {}

    # Validate and configure the connector configuration and secrets
    configuration = configuration or {}
    secrets = secrets or {}
    supported_attrs = []
    for attr_name, attr_schema in auth_method_spec.config_schema.get(
        "properties", {}
    ).items():
        supported_attrs.append(attr_name)
        required = attr_name in auth_method_spec.config_schema.get(
            "required", []
        )
        secret = attr_schema.get("format", "") == "password"
        value = configuration.get(attr_name, secrets.get(attr_name))
        if required:
            if value is None:
                raise ValueError(
                    "connector configuration is not valid: missing "
                    f"required attribute '{attr_name}'"
                )
        elif value is None:
            continue

        # Split the configuration into secrets and non-secrets
        if secret:
            if isinstance(value, SecretStr):
                update_connector_metadata.secrets[attr_name] = value
            else:
                update_connector_metadata.secrets[attr_name] = SecretStr(value)
        else:
            update_connector_metadata.configuration[attr_name] = value

    # Warn about attributes that are not part of the configuration schema
    for attr_name in set(list(configuration.keys())) - set(supported_attrs):
        logger.warning(
            f"Ignoring unknown attribute in connector '{connector.name}' "
            f"configuration {attr_name}. Supported attributes are: "
            f"{supported_attrs}",
        )
    # Warn about secrets that are not part of the configuration schema
    for attr_name in set(secrets.keys()) - connector.secrets.keys():
        logger.warning(
            f"Ignoring unknown attribute in connector '{connector.name}' "
            f"configuration {attr_name}. Supported attributes are: "
            f"{supported_attrs}",
        )
