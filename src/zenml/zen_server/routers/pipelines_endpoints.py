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
"""Endpoint definitions for pipelines."""
from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from zenml.constants import PIPELINES, RUNS, VERSION_1
from zenml.exceptions import NotAuthorizedError, ValidationError
from zenml.models import PipelineRunModel
from zenml.models.pipeline_models import PipelineModel
from zenml.utils.uuid_utils import parse_name_or_uuid
from zenml.zen_server.utils import (
    authorize,
    conflict,
    error_detail,
    error_response,
    not_found,
    zen_store,
)

router = APIRouter(
    prefix=VERSION_1,
    tags=["pipelines"],
    dependencies=[Depends(authorize)],
    responses={401: error_response},
)


@router.get(
    PIPELINES,
    response_model=List[PipelineModel],
    responses={401: error_response, 404: error_response, 422: error_response},
)
async def get_pipelines(project_name_or_id: str) -> List[PipelineModel]:
    """Gets a list of pipelines.

    Args:
        project_name_or_id: Name or ID of the project to get pipelines for.

    Returns:
        List of pipeline objects.

    Raises:
        conflict: when not authorized to login
        not_found: when user does not exist
        validation error: when unable to validate credentials
    """
    try:
        return zen_store.list_pipelines(
            project_name_or_id=parse_name_or_uuid(project_name_or_id)
        )
    except KeyError as e:
        raise not_found(e) from e
    # except NotAuthorizedError as error:
    #     raise conflict(error) from error
    # except KeyError as error:
    #     raise not_found(error) from error
    # except ValidationError as error:
    #     raise HTTPException(status_code=422, detail=error_detail(error))


@router.get(
    PIPELINES + "/{pipeline_id}",
    response_model=PipelineModel,
    responses={401: error_response, 404: error_response, 422: error_response},
)
async def get_pipeline(pipeline_id: str) -> PipelineModel:
    """Gets a specific pipeline using its unique id.

    Args:
        pipeline_id: ID of the pipeline to get.

    Returns:
        A specific pipeline object.

    Raises:
        conflict: when not authorized to login
        not_found: when user does not exist
        validation error: when unable to validate credentials
    """
    try:
        return zen_store.get_pipeline(pipeline_id=UUID(pipeline_id))
    except NotAuthorizedError as error:
        raise conflict(error) from error
    except KeyError as error:
        raise not_found(error) from error
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error_detail(error))


@router.put(
    PIPELINES + "/{pipeline_id}",
    response_model=PipelineModel,
    responses={401: error_response, 404: error_response, 422: error_response},
)
async def update_pipeline(
    pipeline_id: str, updated_pipeline: PipelineModel
) -> PipelineModel:
    """Updates the attribute on a specific pipeline using its unique id.

    Args:
        pipeline_id: ID of the pipeline to get.
        updated_pipeline: the schema to use to update your pipeline.

    Returns:
        The updated pipeline object.

    Raises:
        not_found: when pipeline does not exist
        conflict: when not authorized to login
        not_found: when user does not exist
        validation error: when unable to validate credentials
    """
    try:
        return zen_store.update_pipeline(
            pipeline_id=UUID(pipeline_id), pipeline=updated_pipeline
        )
    except NotAuthorizedError as error:
        raise conflict(error) from error
    except KeyError as error:
        raise not_found(error) from error
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error_detail(error))


@router.delete(
    PIPELINES + "/{pipeline_id}",
    responses={401: error_response, 404: error_response, 422: error_response},
)
async def delete_pipeline(pipeline_id: str) -> None:
    """Deletes a specific pipeline.

    Args:
        pipeline_id: ID of the pipeline to get.

    Raises:
        conflict: when not authorized to login
        not_found: when user does not exist
        validation error: when unable to validate credentials
    """
    try:
        zen_store.delete_pipeline(pipeline_id=UUID(pipeline_id))
    except NotAuthorizedError as error:
        raise conflict(error) from error
    except KeyError as error:
        raise not_found(error) from error
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error_detail(error))


@router.get(
    PIPELINES + "/{pipeline_id}" + RUNS,
    response_model=List[Dict],
    responses={401: error_response, 404: error_response, 422: error_response},
)
async def get_pipeline_runs(pipeline_id: str) -> List[PipelineRunModel]:
    """Gets a list of runs for a specific pipeline.

    Args:
        pipeline_id: ID of the pipeline to get.

    Returns:
        List of triggers.

    Raises:
        conflict: when not authorized to login
        not_found: when user does not exist
        validation error: when unable to validate credentials
    """
    try:
        return zen_store.list_runs(pipeline_id=UUID(pipeline_id))
    except NotAuthorizedError as error:
        raise conflict(error) from error
    except KeyError as error:
        raise not_found(error) from error
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error_detail(error))


@router.post(
    PIPELINES + "/{pipeline_id}" + RUNS,
    responses={401: error_response, 409: error_response, 422: error_response},
)
async def create_pipeline_run(
    pipeline_id: str, pipeline_run: PipelineRunModel
) -> PipelineRunModel:
    """Create a run for a pipeline.

    This endpoint is not meant to be used explicitly once ZenML follows the
    centralized paradigm where runs are authored by the ZenServer and not on the
    user's machine.

    Args:
        pipeline_id: ID of the pipeline.
        pipeline_run: The pipeline run to create.

    Raises:
        conflict: when not authorized to login
        conflict: when user does not exist
        validation error: when unable to validate credentials
    """
    try:
        return zen_store.create_run(pipeline_run=pipeline_run)
    except NotAuthorizedError as error:
        raise conflict(error) from error
    except KeyError as error:
        raise conflict(error) from error
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error_detail(error))


# @router.get(
#     PIPELINES + "/{pipeline_id}" + PIPELINE_CONFIGURATION,
#     response_model=Dict[Any, Any],
#     responses={401: error_response, 404: error_response, 422: error_response},
# )
# async def get_pipeline_configuration(pipeline_id: str) -> Dict[Any, Any]:
#     """Get the pipeline configuration for a given pipeline.
#
#     Args:
#         pipeline_id: ID of the pipeline.
#
#     Raises:
#         401 error: when not authorized to login
#         404 error: when trigger does not exist
#         422 error: when unable to validate input
#     """
#     try:
#         zen_store.get_pipeline_configuration(pipeline_id=pipeline_id)
#     except NotAuthorizedError as error:
#         raise HTTPException(status_code=401, detail=error_detail(error))
#     except KeyError as error:
#         raise HTTPException(status_code=404, detail=error_detail(error))
#     except ValidationError as error:
#         raise HTTPException(status_code=422, detail=error_detail(error))
