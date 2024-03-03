#  Copyright (c) ZenML GmbH 2024. All Rights Reserved.
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
"""Models representing Services."""

from datetime import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Type,
    Union,
)
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList
from sqlmodel import SQLModel

from zenml.constants import STR_FIELD_MAX_LENGTH
from zenml.models.v2.base.scoped import (
    WorkspaceScopedFilter,
    WorkspaceScopedRequest,
    WorkspaceScopedResponse,
    WorkspaceScopedResponseBody,
    WorkspaceScopedResponseMetadata,
    WorkspaceScopedTaggableFilter,
)
from zenml.services.service_status import ServiceState
from zenml.services.service_type import ServiceType

if TYPE_CHECKING:
    pass

# ------------------ Request Model ------------------


class ServiceRequest(WorkspaceScopedRequest):
    """Request model for services."""

    name: str = Field(
        title="The name of the service.",
        max_length=STR_FIELD_MAX_LENGTH,
    )

    service_type: ServiceType = Field(
        title="The type of the service.",
    )

    service_source: Optional[str] = Field(
        title="The class of the service.",
    )

    admin_state: Optional[ServiceState] = Field(
        title="The admin state of the service.",
    )

    config: Dict[str, Any] = Field(
        title="The service config.",
    )

    labels: Optional[Dict[str, str]] = Field(
        default=None,
        title="The service labels.",
    )

    status: Optional[Dict[str, Any]] = Field(
        title="The status of the service.",
    )

    endpoint: Optional[Dict[str, Any]] = Field(
        default=None,
        title="The service endpoint.",
    )

    prediction_url: Optional[str] = Field(
        default=None,
        title="The service endpoint URL.",
    )

    health_check_url: Optional[str] = Field(
        default=None,
        title="The service health check URL.",
    )


# ------------------ Update Model ------------------


class ServiceUpdate(BaseModel):
    """Update model for stack components."""

    name: Optional[str] = Field(
        title="The name of the service.",
        max_length=STR_FIELD_MAX_LENGTH,
    )

    admin_state: Optional[ServiceState] = Field(
        title="The admin state of the service.",
    )

    service_source: Optional[str] = Field(
        title="The class of the service.",
    )

    config: Optional[Dict[str, Any]] = Field(
        title="The service config.",
    )

    status: Optional[Dict[str, Any]] = Field(
        title="The status of the service.",
    )

    endpoint: Optional[Dict[str, Any]] = Field(
        title="The service endpoint.",
    )

    prediction_url: Optional[str] = Field(
        title="The service endpoint URL.",
    )

    health_check_url: Optional[str] = Field(
        title="The service health check URL.",
    )
    labels: Optional[Dict[str, str]] = Field(
        default=None,
        title="The service labels.",
    )


# ------------------ Response Model ------------------


class ServiceResponseBody(WorkspaceScopedResponseBody):
    """Response body for services."""

    service_type: ServiceType = Field(
        title="The type of the service.",
    )
    labels: Optional[Dict[str, str]] = Field(
        default=None,
        title="The service labels.",
    )
    created: datetime = Field(
        title="The timestamp when this component was created."
    )
    updated: datetime = Field(
        title="The timestamp when this component was last updated.",
    )


class ServiceResponseMetadata(WorkspaceScopedResponseMetadata):
    """Response metadata for services."""

    service_source: Optional[str] = Field(
        title="The class of the service.",
    )
    admin_state: Optional[ServiceState] = Field(
        title="The admin state of the service.",
    )
    config: Dict[str, Any] = Field(
        title="The service config.",
    )
    status: Optional[Dict[str, Any]] = Field(
        title="The status of the service.",
    )
    endpoint: Optional[Dict[str, Any]] = Field(
        default=None,
        title="The service endpoint.",
    )
    prediction_url: Optional[str] = Field(
        default=None,
        title="The service endpoint URL.",
    )
    health_check_url: Optional[str] = Field(
        default=None,
        title="The service health check URL.",
    )


class ServiceResponse(
    WorkspaceScopedResponse[ServiceResponseBody, ServiceResponseMetadata]
):
    """Response model for services."""

    name: str = Field(
        title="The name of the service.",
        max_length=STR_FIELD_MAX_LENGTH,
    )

    def get_hydrated_version(self) -> "ServiceResponse":
        """Get the hydrated version of this artifact.

        Returns:
            an instance of the same entity with the metadata field attached.
        """
        from zenml.client import Client

        return Client().zen_store.get_service(self.id)

    # Body and metadata properties

    @property
    def service_type(self) -> ServiceType:
        """The `service_type` property.

        Returns:
            the value of the property.
        """
        return self.get_body().service_type

    @property
    def labels(self) -> Optional[Dict[str, str]]:
        """The `labels` property.

        Returns:
            the value of the property.
        """
        return self.get_body().labels

    @property
    def service_source(self) -> Optional[str]:
        """The `service_source` property.

        Returns:
            the value of the property.
        """
        return self.get_metadata().service_source

    @property
    def config(self) -> Dict[str, Any]:
        """The `config` property.

        Returns:
            the value of the property.
        """
        return self.get_metadata().config

    @property
    def status(self) -> Optional[Dict[str, Any]]:
        """The `status` property.

        Returns:
            the value of the property.
        """
        return self.get_metadata().status

    @property
    def endpoint(self) -> Optional[Dict[str, Any]]:
        """The `endpoint` property.

        Returns:
            the value of the property.
        """
        return self.get_metadata().endpoint

    @property
    def created(self) -> datetime:
        """The `created` property.

        Returns:
            the value of the property.
        """
        return self.get_body().created

    @property
    def updated(self) -> datetime:
        """The `updated` property.

        Returns:
            the value of the property.
        """
        return self.get_body().updated

    @property
    def admin_state(self) -> Optional[ServiceState]:
        """The `admin_state` property.

        Returns:
            the value of the property.
        """
        return self.get_metadata().admin_state

    @property
    def prediction_url(self) -> Optional[str]:
        """The `prediction_url` property.

        Returns:
            the value of the property.
        """
        return self.get_metadata().prediction_url

    @property
    def health_check_url(self) -> Optional[str]:
        """The `health_check_url` property.

        Returns:
            the value of the property.
        """
        return self.get_metadata().health_check_url


# ------------------ Filter Model ------------------


class ServiceFilter(WorkspaceScopedFilter):
    """Model to enable advanced filtering of services.

    The Service needs additional scoping. As such the `_scope_user` field
    can be set to the user that is doing the filtering. The
    `generate_filter()` method of the baseclass is overwritten to include the
    scoping.
    """

    name: Optional[str] = Field(
        description="Name of the service",
    )
    workspace_id: Optional[Union[UUID, str]] = Field(
        default=None, description="Workspace of the service"
    )
    user_id: Optional[Union[UUID, str]] = Field(
        default=None, description="User of the service"
    )
    type: Optional[str] = Field(
        default=None, description="Type of the service"
    )
    flavor: Optional[str] = Field(
        default=None, description="Flavor of the service"
    )
    run_name: Optional[Union[UUID, str]] = Field(
        default=None,
        description="Pipeline run id responsible for deploying the service",
    )
    pipeline_step_name: Optional[str] = Field(
        default=None,
        description="Pipeline step name responsible for deploying the service",
    )
    model_name: Optional[str] = Field(
        default=None, description="Model name linked to the service"
    )
    model_version: Optional[str] = Field(
        default=None, description="Model version linked to the service"
    )
    running: Optional[bool] = Field(
        default=None, description="Whether the service is running"
    )

    def set_type(self, type: str) -> None:
        """Set the type of the service.

        Args:
            type: The type of the service.

        Returns:
            The updated filter.
        """
        self.type = type

    def set_flavor(self, flavor: str) -> None:
        """Set the flavor of the service.

        Args:
            flavor: The flavor of the service.

        Returns:
            The updated filter.
        """
        self.flavor = flavor

    # Artifact name and type are not DB fields and need to be handled separately
    FILTER_EXCLUDE_FIELDS = [
        *WorkspaceScopedFilter.FILTER_EXCLUDE_FIELDS,
        "flavor",
        "type",
        "run_name",
        "pipeline_step_name",
        "model_name",
        "model_version",
        "running",
    ]
    CLI_EXCLUDE_FIELDS: ClassVar[List[str]] = [
        *WorkspaceScopedTaggableFilter.CLI_EXCLUDE_FIELDS,
        "workspace_id",
        "user_id",
        "flavor",
        "type",
        "run_name",
        "pipeline_step_name",
        "model_name",
        "model_version",
        "running",
    ]

    def generate_filter(
        self, table: Type["SQLModel"]
    ) -> Union["BinaryExpression[Any]", "BooleanClauseList[Any]"]:
        """Generate the filter for the query.

        Stack components can be scoped by type to narrow the search.

        Args:
            table: The Table that is being queried from.

        Returns:
            The filter expression for the query.
        """
        from sqlalchemy import and_

        base_filter = super().generate_filter(table)

        if self.type:
            type_filter = getattr(table, "type") == self.type
            base_filter = and_(base_filter, type_filter)

        if self.flavor:
            flavor_filter = getattr(table, "flavor") == self.flavor
            base_filter = and_(base_filter, flavor_filter)

        if self.run_name:
            run_name_filter = getattr(table, "run_name") == self.run_name
            base_filter = and_(base_filter, run_name_filter)

        if self.pipeline_step_name:
            pipeline_step_name_filter = (
                getattr(table, "pipeline_step_name") == self.pipeline_step_name
            )
            base_filter = and_(base_filter, pipeline_step_name_filter)

        if self.model_name:
            model_name_filter = getattr(table, "model_name") == self.model_name
            base_filter = and_(base_filter, model_name_filter)

        if self.model_version:
            model_version_filter = (
                getattr(table, "model_version") == self.model_version
            )
            base_filter = and_(base_filter, model_version_filter)

        return base_filter
