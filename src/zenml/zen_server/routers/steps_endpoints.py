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

from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Security

from zenml.constants import (
    API,
    LOGS,
    STATUS,
    STEP_CONFIGURATION,
    STEPS,
    VERSION_1,
)
from zenml.enums import ExecutionStatus
from zenml.models import (
    Page,
    StepRunFilter,
    StepRunRequest,
    StepRunResponse,
    StepRunUpdate,
)
from zenml.utils.artifact_utils import (
    _load_artifact_store,
    _load_file_from_artifact_store,
)
from zenml.zen_server.auth import AuthContext, authorize
from zenml.zen_server.exceptions import error_response
from zenml.zen_server.utils import (
    handle_exceptions,
    make_dependable,
    zen_store,
)

router = APIRouter(
    prefix=API + VERSION_1 + STEPS,
    tags=["steps"],
    responses={401: error_response, 403: error_response},
)


@router.get(
    "",
    response_model=Page[StepRunResponse],
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def list_run_steps(
    step_run_filter_model: StepRunFilter = Depends(
        make_dependable(StepRunFilter)
    ),
    hydrate: bool = False,
    _: AuthContext = Security(authorize),
) -> Page[StepRunResponse]:
    """Get run steps according to query filters.

    Args:
        step_run_filter_model: Filter model used for pagination, sorting,
            filtering.
        hydrate: Flag deciding whether to hydrate the output model(s)
            by including metadata fields in the response.

    Returns:
        The run steps according to query filters.
    """
    return zen_store().list_run_steps(
        step_run_filter_model=step_run_filter_model, hydrate=hydrate
    )


@router.post(
    "",
    response_model=StepRunResponse,
    responses={401: error_response, 409: error_response, 422: error_response},
)
@handle_exceptions
def create_run_step(
    step: StepRunRequest,
    _: AuthContext = Security(authorize),
) -> StepRunResponse:
    """Create a run step.

    Args:
        step: The run step to create.

    Returns:
        The created run step.
    """
    return zen_store().create_run_step(step_run=step)


@router.get(
    "/{step_id}",
    response_model=StepRunResponse,
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def get_step(
    step_id: UUID,
    hydrate: bool = True,
    _: AuthContext = Security(authorize),
) -> StepRunResponse:
    """Get one specific step.

    Args:
        step_id: ID of the step to get.
        hydrate: Flag deciding whether to hydrate the output model(s)
            by including metadata fields in the response.

    Returns:
        The step.
    """
    return zen_store().get_run_step(step_id, hydrate=hydrate)


@router.put(
    "/{step_id}",
    response_model=StepRunResponse,
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def update_step(
    step_id: UUID,
    step_model: StepRunUpdate,
    _: AuthContext = Security(authorize),
) -> StepRunResponse:
    """Updates a step.

    Args:
        step_id: ID of the step.
        step_model: Step model to use for the update.

    Returns:
        The updated step model.
    """
    return zen_store().update_run_step(
        step_run_id=step_id, step_run_update=step_model
    )


@router.get(
    "/{step_id}" + STEP_CONFIGURATION,
    response_model=Dict[str, Any],
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def get_step_configuration(
    step_id: UUID,
    _: AuthContext = Security(authorize),
) -> Dict[str, Any]:
    """Get the configuration of a specific step.

    Args:
        step_id: ID of the step to get.

    Returns:
        The step configuration.
    """
    return zen_store().get_run_step(step_id).config.dict()


@router.get(
    "/{step_id}" + STATUS,
    response_model=ExecutionStatus,
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def get_step_status(
    step_id: UUID,
    _: AuthContext = Security(authorize),
) -> ExecutionStatus:
    """Get the status of a specific step.

    Args:
        step_id: ID of the step for which to get the status.

    Returns:
        The status of the step.
    """
    return zen_store().get_run_step(step_id).status


@router.get(
    "/{step_id}" + LOGS,
    response_model=str,
    responses={401: error_response, 404: error_response, 422: error_response},
)
@handle_exceptions
def get_step_logs(
    step_id: UUID,
    _: AuthContext = Security(authorize),
) -> str:
    """Get the logs of a specific step.

    Args:
        step_id: ID of the step for which to get the logs.

    Returns:
        The logs of the step.

    Raises:
        HTTPException: If no logs are available for this step.
    """
    store = zen_store()
    logs = store.get_run_step(step_id).logs
    if logs is None:
        raise HTTPException(
            status_code=404, detail="No logs available for this step"
        )
    artifact_store = _load_artifact_store(logs.artifact_store_id, store)
    return str(
        _load_file_from_artifact_store(
            logs.uri, artifact_store=artifact_store, mode="r"
        )
    )
