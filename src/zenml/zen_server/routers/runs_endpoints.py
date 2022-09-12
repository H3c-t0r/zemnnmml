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
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from zenml.constants import (
    COMPONENT_SIDE_EFFECTS,
    GRAPH,
    RUNS,
    RUNTIME_CONFIGURATION,
    STEPS,
    VERSION_1,
)
from zenml.exceptions import NotAuthorizedError, ValidationError
from zenml.models.pipeline_models import PipelineRunModel, StepRunModel
from zenml.utils.uuid_utils import parse_optional_name_or_uuid
from zenml.zen_server.utils import (
    authorize,
    error_detail,
    error_response,
    zen_store,
)

router = APIRouter(
    prefix=VERSION_1 + RUNS,
    tags=["runs"],
    dependencies=[Depends(authorize)],
    responses={401: error_response},
)


@router.get(
    "/",
    response_model=List[PipelineRunModel],
    responses={401: error_response, 404: error_response, 422: error_response},
)
async def get_runs(
    project_name_or_id: Optional[str] = None,
    stack_id: Optional[str] = None,
    pipeline_id: Optional[str] = None,
) -> List[PipelineRunModel]:
    """Get pipeline runs according to query filters.

    Args:
        project_name_or_id: Name or ID of the project for which to filter runs.
        stack_id: ID of the stack for which to filter runs.
        pipeline_id: ID of the pipeline for which to filter runs.
        trigger_id: ID of the trigger for which to filter runs.

    Returns:
        The pipeline runs according to query filters.

    Raises:
        not_found: If the project, stack, pipeline, or trigger do not exist.
        401 error: when not authorized to login
        404 error: when trigger does not exist
        422 error: when unable to validate input
    """
    try:
        return zen_store.list_runs(
            project_name_or_id=parse_optional_name_or_uuid(project_name_or_id),
            stack_id=stack_id,
            pipeline_id=pipeline_id,
        )
    except NotAuthorizedError as error:
        raise HTTPException(status_code=401, detail=error_detail(error))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=error_detail(error))
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error_detail(error))


@router.get(
    "/{run_id}",
    response_model=PipelineRunModel,
    responses={401: error_response, 404: error_response, 422: error_response},
)
async def get_run(run_id: str) -> PipelineRunModel:
    """Get a specific pipeline run using its ID.

    Args:
        run_id: ID of the pipeline run to get.

    Returns:
        The pipeline run.

    Raises:
        not_found: If the pipeline run does not exist.
        401 error: when not authorized to login
        404 error: when trigger does not exist
        422 error: when unable to validate input
    """
    try:
        return zen_store.get_run(run_id=UUID(run_id))
    except NotAuthorizedError as error:
        raise HTTPException(status_code=401, detail=error_detail(error))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=error_detail(error))
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error_detail(error))


@router.put(
    "/{run_id}",
    response_model=PipelineRunModel,
    responses={401: error_response, 404: error_response, 422: error_response},
)
async def update_run(run_id: str, run: PipelineRunModel) -> PipelineRunModel:
    """Update the attributes on a specific pipeline run using its ID.

    Args:
        run_id: ID of the pipeline run to get.
        run: The pipeline run to use for the update.

    Returns:
        The updated pipeline run.

    Raises:
        401 error: when not authorized to login
        404 error: when trigger does not exist
        422 error: when unable to validate input
    """
    try:
        return zen_store.update_run(run_id=UUID(run_id), run=run)
    except NotAuthorizedError as error:
        raise HTTPException(status_code=401, detail=error_detail(error))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=error_detail(error))
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error_detail(error))


@router.delete(
    "/{run_id}",
    responses={401: error_response, 404: error_response, 422: error_response},
)
async def delete_run(run_id: str) -> None:
    """Delete a pipeline run using its ID.

    Args:
        run_id: ID of the pipeline run to get.

    Raises:
        401 error: when not authorized to login
        404 error: when trigger does not exist
        422 error: when unable to validate input
    """
    try:
        zen_store.delete_run(run_id=UUID(run_id))
    except NotAuthorizedError as error:
        raise HTTPException(status_code=401, detail=error_detail(error))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=error_detail(error))
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error_detail(error))


@router.get(
    "/{run_id}" + GRAPH,
    response_model=str,  # TODO: Use file type / image type
    responses={401: error_response, 404: error_response, 422: error_response},
)
async def get_run_dag(run_id: str) -> str:  # TODO: use file type / image type
    """Get the DAG for a given pipeline run.

    Args:
        run_id: ID of the pipeline run to use to get the DAG.

    Returns:
        The DAG for a given pipeline run.

    Raises:
        401 error: when not authorized to login
        404 error: when trigger does not exist
        422 error: when unable to validate input
    """
    try:
        image_object_path = zen_store.get_run_dag(
            run_id=UUID(run_id)
        )  # TODO: ZenStore should return a path
        return FileResponse(image_object_path)
    except NotAuthorizedError as error:
        raise HTTPException(status_code=401, detail=error_detail(error))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=error_detail(error))
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error_detail(error))


@router.get(
    "/{run_id}" + STEPS,
    response_model=Dict[str, StepRunModel],
    responses={401: error_response, 404: error_response, 422: error_response},
)
async def get_run_steps(run_id: str) -> Dict[str, StepRunModel]:
    """Get all steps for a given pipeline run.

    Args:
        run_id: ID of the pipeline run to use to get the DAG.

    Returns:
        The steps for a given pipeline run.

    Raises:
        401 error: when not authorized to login
        404 error: when trigger does not exist
        422 error: when unable to validate input
    """
    try:
        run = zen_store.get_run(run_id)
        return zen_store.list_run_steps(run.mlmd_id)
    except NotAuthorizedError as error:
        raise HTTPException(status_code=401, detail=error_detail(error))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=error_detail(error))
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error_detail(error))


# TODO: Figure out what exactly gets returned from this
@router.get(
    "/{run_id}" + RUNTIME_CONFIGURATION,
    response_model=Dict,
    responses={401: error_response, 404: error_response, 422: error_response},
)
async def get_run_runtime_configuration(run_id: str) -> Dict:
    """Get the runtime configuration for a given pipeline run.

    Args:
        run_id: ID of the pipeline run to use to get the runtime configuration.

    Returns:
        The runtime configuration for a given pipeline run.

    Raises:
        401 error: when not authorized to login
        404 error: when trigger does not exist
        422 error: when unable to validate input
    """
    try:
        return zen_store.get_run_runtime_configuration(run_id=UUID(run_id))
    except NotAuthorizedError as error:
        raise HTTPException(status_code=401, detail=error_detail(error))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=error_detail(error))
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error_detail(error))


@router.get(
    "/{run_id}" + COMPONENT_SIDE_EFFECTS,
    response_model=Dict,
    responses={401: error_response, 404: error_response, 422: error_response},
)
async def get_run_component_side_effects(
    run_id: str, component_id: str, component_type: str
) -> Dict:
    """Get the component side-effects for a given pipeline run.

    Args:
        run_id: ID of the pipeline run to use to get the component side-effects.
        component_id: ID of the component to use to get the component
            side-effects.
        component_type: Type of the component to use to get the component
            side-effects.

    Returns:
        The component side-effects for a given pipeline run.

    Raises:
        401 error: when not authorized to login
        404 error: when trigger does not exist
        422 error: when unable to validate input
    """
    try:
        return zen_store.get_run_component_side_effects(
            run_id=UUID(run_id),
            component_id=component_id,
            component_type=component_type,
        )
    except NotAuthorizedError as error:
        raise HTTPException(status_code=401, detail=error_detail(error))
    except KeyError as error:
        raise HTTPException(status_code=404, detail=error_detail(error))
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error_detail(error))
