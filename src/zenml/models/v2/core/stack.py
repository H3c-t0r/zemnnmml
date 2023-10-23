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
"""Models representing stacks."""

import json
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Union
from uuid import UUID

from pydantic import Field

from zenml.constants import STR_FIELD_MAX_LENGTH
from zenml.enums import StackComponentType
from zenml.models.v2.base.scoped import (
    SharableResponseBody,
    SharableResponseMetadata,
    ShareableFilter,
    ShareableRequest,
    ShareableResponse,
)
from zenml.models.v2.base.utils import hydrated_property, update_model

if TYPE_CHECKING:
    from zenml.models.v2.core.component import ComponentResponse

# ------------------ Request Model ------------------


class StackRequest(ShareableRequest):
    """Request model for stacks."""

    name: str = Field(
        title="The name of the stack.", max_length=STR_FIELD_MAX_LENGTH
    )
    description: str = Field(
        default="",
        title="The description of the stack",
        max_length=STR_FIELD_MAX_LENGTH,
    )
    stack_spec_path: Optional[str] = Field(
        default=None,
        title="The path to the stack spec used for mlstacks deployments.",
    )
    components: Optional[Dict[StackComponentType, List[UUID]]] = Field(
        default=None,
        title="A mapping of stack component types to the actual"
        "instances of components of this type.",
    )

    @property
    def is_valid(self) -> bool:
        """Check if the stack is valid.

        Returns:
            True if the stack is valid, False otherwise.
        """
        if not self.components:
            return False
        return (
            StackComponentType.ARTIFACT_STORE in self.components
            and StackComponentType.ORCHESTRATOR in self.components
        )


# ------------------ Update Model ------------------


@update_model
class StackUpdate(StackRequest):
    """Update model for stacks."""


# ------------------ Response Model ------------------


class StackResponseBody(SharableResponseBody):
    """Response body for stacks."""


class StackResponseMetadata(SharableResponseMetadata):
    """Response metadata for stacks."""

    components: Dict[StackComponentType, List["ComponentResponse"]] = Field(
        title="A mapping of stack component types to the actual"
        "instances of components of this type."
    )
    description: Optional[str] = Field(
        default="",
        title="The description of the stack",
        max_length=STR_FIELD_MAX_LENGTH,
    )
    stack_spec_path: Optional[str] = Field(
        default=None,
        title="The path to the stack spec used for mlstacks deployments.",
    )


class StackResponse(ShareableResponse):
    """Response model for stacks."""

    name: str = Field(
        title="The name of the stack.", max_length=STR_FIELD_MAX_LENGTH
    )

    # Body and metadata pair
    body: "StackResponseBody"
    metadata: Optional["StackResponseMetadata"]

    def get_hydrated_version(self) -> "StackResponse":
        """Get the hydrated version of this stack."""
        from zenml.client import Client

        return Client().zen_store.get_stack(self.id)

    # Helper methods
    @property
    def is_valid(self) -> bool:
        """Check if the stack is valid.

        Returns:
            True if the stack is valid, False otherwise.
        """
        return (
            StackComponentType.ARTIFACT_STORE in self.components
            and StackComponentType.ORCHESTRATOR in self.components
        )

    def to_yaml(self) -> Dict[str, Any]:
        """Create yaml representation of the Stack Model.

        Returns:
            The yaml representation of the Stack Model.
        """
        component_data = {}
        for component_type, components_list in self.components.items():
            component = components_list[0]
            component_dict = json.loads(
                component.json(
                    include={"name", "type", "flavor", "configuration"}
                )
            )
            component_data[component_type.value] = component_dict

        # write zenml version and stack dict to YAML
        yaml_data = {
            "stack_name": self.name,
            "components": component_data,
        }

        return yaml_data

    # Analytics
    def get_analytics_metadata(self) -> Dict[str, Any]:
        """Add the stack components to the stack analytics metadata.

        Returns:
            Dict of analytics metadata.
        """
        metadata = super().get_analytics_metadata()
        metadata.update({ct: c[0].flavor for ct, c in self.components.items()})
        return metadata

    # Body and metadata properties
    @hydrated_property
    def description(self):
        """The `description` property."""
        return self.metadata.description

    @hydrated_property
    def stack_spec_path(self):
        """The `stack_spec_path` property."""
        return self.metadata.stack_spec_path

    @hydrated_property
    def components(self):
        """The `components` property."""
        return self.metadata.components


# ------------------ Filter Model ------------------


class StackFilter(ShareableFilter):
    """Model to enable advanced filtering of all StackModels.

    The Stack Model needs additional scoping. As such the `_scope_user` field
    can be set to the user that is doing the filtering. The
    `generate_filter()` method of the baseclass is overwritten to include the
    scoping.
    """

    # `component_id` refers to a relationship through a link-table
    #  rather than a field in the db, hence it needs to be handled
    #  explicitly
    FILTER_EXCLUDE_FIELDS: ClassVar[List[str]] = [
        *ShareableFilter.FILTER_EXCLUDE_FIELDS,
        "component_id",  # This is a relationship, not a field
    ]

    is_shared: Optional[Union[bool, str]] = Field(
        default=None, description="If the stack is shared or private"
    )
    name: Optional[str] = Field(
        default=None,
        description="Name of the stack",
    )
    description: Optional[str] = Field(
        default=None, description="Description of the stack"
    )
    workspace_id: Optional[Union[UUID, str]] = Field(
        default=None, description="Workspace of the stack"
    )
    user_id: Optional[Union[UUID, str]] = Field(
        default=None, description="User of the stack"
    )
    component_id: Optional[Union[UUID, str]] = Field(
        default=None, description="Component in the stack"
    )
