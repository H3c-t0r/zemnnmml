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
"""Endpoint definitions for models."""

from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, Security

from zenml.constants import (
    API,
    MODEL_VERSIONS,
    MODELS,
    VERSION_1,
)
from zenml.models import (
    ModelFilterModel,
    ModelResponseModel,
    ModelUpdateModel,
    ModelVersionFilterModel,
    ModelVersionResponseModel,
    Page,
)
from zenml.zen_server.auth import AuthContext, authorize
from zenml.zen_server.exceptions import error_response
from zenml.zen_server.rbac.endpoint_utils import (
    verify_permissions_and_delete_entity,
    verify_permissions_and_get_entity,
    verify_permissions_and_list_entities,
    verify_permissions_and_update_entity,
)
from zenml.zen_server.rbac.models import ResourceType
from zenml.zen_server.rbac.utils import (
    dehydrate_page,
    get_allowed_resource_ids,
)
from zenml.zen_server.utils import (
    handle_exceptions,
    make_dependable,
    zen_store,
)

#########
# Models
#########

router = APIRouter(
    prefix=API + VERSION_1 + MODELS,
    tags=["models"],
    responses={401: error_response, 403: error_response},
)


@router.get(
    "",
    response_model=Page[ModelResponseModel],
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def list_models(
    model_filter_model: ModelFilterModel = Depends(
        make_dependable(ModelFilterModel)
    ),
    _: AuthContext = Security(authorize),
) -> Page[ModelResponseModel]:
    """Get models according to query filters.

    Args:
        model_filter_model: Filter model used for pagination, sorting,
            filtering


    Returns:
        The models according to query filters.
    """
    return verify_permissions_and_list_entities(
        filter_model=model_filter_model,
        resource_type=ResourceType.MODEL,
        list_method=zen_store().list_models,
    )


@router.get(
    "/{model_name_or_id}",
    response_model=ModelResponseModel,
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def get_model(
    model_name_or_id: Union[str, UUID],
    _: AuthContext = Security(authorize),
) -> ModelResponseModel:
    """Get a model by name or ID.

    Args:
        model_name_or_id: The name or ID of the model to get.

    Returns:
        The model with the given name or ID.
    """
    return verify_permissions_and_get_entity(
        id=model_name_or_id, get_method=zen_store().get_model
    )


@router.put(
    "/{model_id}",
    response_model=ModelResponseModel,
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def update_model(
    model_id: UUID,
    model_update: ModelUpdateModel,
    _: AuthContext = Security(authorize),
) -> ModelResponseModel:
    """Updates a model.

    Args:
        model_id: Name of the stack.
        model_update: Stack to use for the update.

    Returns:
        The updated model.
    """
    return verify_permissions_and_update_entity(
        id=model_id,
        update_model=model_update,
        get_method=zen_store().get_model,
        update_method=zen_store().update_model,
    )


@router.delete(
    "/{model_name_or_id}",
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def delete_model(
    model_name_or_id: Union[str, UUID],
    _: AuthContext = Security(authorize),
) -> None:
    """Delete a model by name or ID.

    Args:
        model_name_or_id: The name or ID of the model to delete.
    """
    verify_permissions_and_delete_entity(
        id=model_name_or_id,
        get_method=zen_store().get_model,
        delete_method=zen_store().delete_model,
    )


#################
# Model Versions
#################


@router.get(
    "/{model_name_or_id}" + MODEL_VERSIONS,
    response_model=Page[ModelVersionResponseModel],
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def list_model_versions(
    model_name_or_id: Union[str, UUID],
    model_version_filter_model: ModelVersionFilterModel = Depends(
        make_dependable(ModelVersionFilterModel)
    ),
    auth_context: AuthContext = Security(authorize),
) -> Page[ModelVersionResponseModel]:
    """Get model versions according to query filters.

    This endpoint serves the purpose of allowing scoped filtering by model_id.

    Args:
        model_name_or_id: The name or ID of the model to list in.
        model_version_filter_model: Filter model used for pagination, sorting,
            filtering

    Returns:
        The model versions according to query filters.
    """
    allowed_model_ids = get_allowed_resource_ids(
        resource_type=ResourceType.MODEL
    )
    model_version_filter_model.set_rbac_allowed_model_ids_and_user(
        allowed_model_ids=allowed_model_ids, user_id=auth_context.user.id
    )

    model_versions = zen_store().list_model_versions(
        model_name_or_id=model_name_or_id,
        model_version_filter_model=model_version_filter_model,
    )
    return dehydrate_page(model_versions)
