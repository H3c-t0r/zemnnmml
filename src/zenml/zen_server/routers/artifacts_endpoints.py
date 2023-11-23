#  Copyright (c) ZenML GmbH 2022. All Rights Reserved.
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
"""Endpoint definitions for steps (and artifacts) of pipeline runs."""

from uuid import UUID

from fastapi import APIRouter, Depends, Security

from zenml.artifacts.utils import load_artifact_visualization
from zenml.constants import API, ARTIFACTS, VERSION_1, VISUALIZE
from zenml.models import (
    ArtifactFilter,
    ArtifactRequest,
    ArtifactResponse,
    LoadedVisualization,
    Page,
)
from zenml.models.v2.core.artifact import ArtifactUpdate
from zenml.zen_server.auth import AuthContext, authorize
from zenml.zen_server.exceptions import error_response
from zenml.zen_server.rbac.endpoint_utils import (
    verify_permissions_and_create_entity,
    verify_permissions_and_delete_entity,
    verify_permissions_and_get_entity,
    verify_permissions_and_list_entities,
)
from zenml.zen_server.rbac.models import ResourceType
from zenml.zen_server.utils import (
    handle_exceptions,
    make_dependable,
    zen_store,
)

router = APIRouter(
    prefix=API + VERSION_1 + ARTIFACTS,
    tags=["artifacts"],
    responses={401: error_response, 403: error_response},
)


@router.get(
    "",
    response_model=Page[ArtifactResponse],
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def list_artifacts(
    artifact_filter_model: ArtifactFilter = Depends(
        make_dependable(ArtifactFilter)
    ),
    hydrate: bool = False,
    _: AuthContext = Security(authorize),
) -> Page[ArtifactResponse]:
    """Get artifacts according to query filters.

    Args:
        artifact_filter_model: Filter model used for pagination, sorting,
            filtering.
        hydrate: Flag deciding whether to hydrate the output model(s)
            by including metadata fields in the response.

    Returns:
        The artifacts according to query filters.
    """
    return verify_permissions_and_list_entities(
        filter_model=artifact_filter_model,
        resource_type=ResourceType.ARTIFACT,
        list_method=zen_store().list_artifacts,
        hydrate=hydrate,
    )


@router.post(
    "",
    response_model=ArtifactResponse,
    responses={401: error_response, 409: error_response, 422: error_response},
)
@handle_exceptions
def create_artifact(
    artifact: ArtifactRequest,
    _: AuthContext = Security(authorize),
) -> ArtifactResponse:
    """Create a new artifact.

    Args:
        artifact: The artifact to create.

    Returns:
        The created artifact.
    """
    return verify_permissions_and_create_entity(
        request_model=artifact,
        resource_type=ResourceType.ARTIFACT,
        create_method=zen_store().create_artifact,
    )


@router.get(
    "/{artifact_id}",
    response_model=ArtifactResponse,
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def get_artifact(
    artifact_id: UUID,
    hydrate: bool = True,
    _: AuthContext = Security(authorize),
) -> ArtifactResponse:
    """Get an artifact by ID.

    Args:
        artifact_id: The ID of the artifact to get.
        hydrate: Flag deciding whether to hydrate the output model(s)
            by including metadata fields in the response.

    Returns:
        The artifact with the given ID.
    """
    return verify_permissions_and_get_entity(
        id=artifact_id, get_method=zen_store().get_artifact, hydrate=hydrate
    )


@router.put(
    "/{artifact_id}",
    response_model=ArtifactResponse,
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def update_artifact(
    artifact_id: UUID,
    artifact_update: ArtifactUpdate,
    _: AuthContext = Security(authorize, scopes=[PermissionType.WRITE]),
) -> ArtifactResponse:
    """Update an artifact by ID.

    Args:
        artifact_id: The ID of the artifact to update.
        artifact_update: The update to apply to the artifact.

    Returns:
        The updated artifact.
    """
    return zen_store().update_artifact(artifact_id, artifact_update)


@router.delete(
    "/{artifact_id}",
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def delete_artifact(
    artifact_id: UUID,
    _: AuthContext = Security(authorize),
) -> None:
    """Delete an artifact by ID.

    Args:
        artifact_id: The ID of the artifact to delete.
    """
    verify_permissions_and_delete_entity(
        id=artifact_id,
        get_method=zen_store().get_artifact,
        delete_method=zen_store().delete_artifact,
    )


@router.get(
    "/{artifact_id}" + VISUALIZE,
    response_model=LoadedVisualization,
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def get_artifact_visualization(
    artifact_id: UUID,
    index: int = 0,
    _: AuthContext = Security(authorize),
) -> LoadedVisualization:
    """Get the visualization of an artifact.

    Args:
        artifact_id: ID of the artifact for which to get the visualization.
        index: Index of the visualization to get (if there are multiple).

    Returns:
        The visualization of the artifact.
    """
    store = zen_store()
    artifact = verify_permissions_and_get_entity(
        id=artifact_id, get_method=store.get_artifact
    )
    return load_artifact_visualization(
        artifact=artifact, index=index, zen_store=store, encode_image=True
    )
