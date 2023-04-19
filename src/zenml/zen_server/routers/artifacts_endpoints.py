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

import base64
from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, Security

from zenml.constants import API, ARTIFACTS, VERSION_1, VISUALIZE
from zenml.enums import PermissionType, VisualizationType
from zenml.exceptions import DoesNotExistException
from zenml.models import (
    ArtifactFilterModel,
    ArtifactRequestModel,
    ArtifactResponseModel,
)
from zenml.models.page_model import Page
from zenml.models.visualization_models import (
    LoadedVisualizationModel,
)
from zenml.zen_server.auth import AuthContext, authorize
from zenml.zen_server.utils import (
    error_response,
    handle_exceptions,
    make_dependable,
    zen_store,
)

router = APIRouter(
    prefix=API + VERSION_1 + ARTIFACTS,
    tags=["artifacts"],
    responses={401: error_response},
)


@router.get(
    "",
    response_model=Page[ArtifactResponseModel],
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def list_artifacts(
    artifact_filter_model: ArtifactFilterModel = Depends(
        make_dependable(ArtifactFilterModel)
    ),
    _: AuthContext = Security(authorize, scopes=[PermissionType.READ]),
) -> Page[ArtifactResponseModel]:
    """Get artifacts according to query filters.

    Args:
        artifact_filter_model: Filter model used for pagination, sorting,
            filtering

    Returns:
        The artifacts according to query filters.
    """
    return zen_store().list_artifacts(
        artifact_filter_model=artifact_filter_model
    )


@router.post(
    "",
    response_model=ArtifactResponseModel,
    responses={401: error_response, 409: error_response, 422: error_response},
)
@handle_exceptions
def create_artifact(
    artifact: ArtifactRequestModel,
    _: AuthContext = Security(authorize, scopes=[PermissionType.WRITE]),
) -> ArtifactResponseModel:
    """Create a new artifact.

    Args:
        artifact: The artifact to create.

    Returns:
        The created artifact.
    """
    return zen_store().create_artifact(artifact)


@router.get(
    "/{artifact_id}",
    response_model=ArtifactResponseModel,
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def get_artifact(
    artifact_id: UUID,
    _: AuthContext = Security(authorize, scopes=[PermissionType.READ]),
) -> ArtifactResponseModel:
    """Get an artifact by ID.

    Args:
        artifact_id: The ID of the artifact to get.

    Returns:
        The artifact with the given ID.
    """
    return zen_store().get_artifact(artifact_id)


@router.delete(
    "/{artifact_id}",
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def delete_artifact(
    artifact_id: UUID,
    _: AuthContext = Security(authorize, scopes=[PermissionType.WRITE]),
) -> None:
    """Delete an artifact by ID.

    Args:
        artifact_id: The ID of the artifact to delete.
    """
    zen_store().delete_artifact(artifact_id)


@router.get(
    "/{artifact_id}" + VISUALIZE,
    response_model=LoadedVisualizationModel,
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def get_artifact_visualization(
    artifact_id: UUID,
    index: int = 0,
    _: AuthContext = Security(authorize, scopes=[PermissionType.READ]),
) -> LoadedVisualizationModel:
    """Get the visualization of an artifact.

    Args:
        artifact_id: ID of the artifact for which to get the visualization.
        index: Index of the visualization to get.

    Returns:
        The visualization of the artifact.

    Raises:
        DoesNotExistException: If the artifact has no visualizations.
    """
    from zenml.io.fileio import open

    artifact = zen_store().get_artifact(artifact_id)

    if not artifact.visualizations:
        raise DoesNotExistException(
            f"Artifact '{artifact_id}' has no visualizations."
        )

    unloaded_visualization = artifact.visualizations[index]
    uri = unloaded_visualization.uri
    type_ = unloaded_visualization.type
    value: Union[str, bytes]

    if type_ == VisualizationType.IMAGE:
        with open(uri, "rb") as image_file:
            value = base64.b64encode(image_file.read())
    else:
        with open(uri, "r") as text_file:
            value = text_file.read()

    return LoadedVisualizationModel(type=type_, value=value)
