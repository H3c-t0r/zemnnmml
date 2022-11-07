#  Copyright (c) ZenML GmbH 2022. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at:
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
#  or implied. See the License for the specific language governing
#  permissions and limitations under the License.
"""Implementation of the BentoML model deployer pipeline step."""
from typing import List, Optional, Type, cast

import bentoml
from bentoml._internal.bento import bento

from zenml.client import Client
from zenml.constants import DEFAULT_SERVICE_START_STOP_TIMEOUT
from zenml.environment import Environment
from zenml.integrations.bentoml.model_deployers.bentoml_model_deployer import (
    BentoMLModelDeployer,
)
from zenml.integrations.bentoml.services.bentoml_deployment import (
    BentoMLDeploymentConfig,
    BentoMLDeploymentService,
)
from zenml.logger import get_logger
from zenml.steps import (
    STEP_ENVIRONMENT_NAME,
    BaseParameters,
    BaseStep,
    StepEnvironment,
    step,
)

logger = get_logger(__name__)


class BentoMLDeployerParameters(BaseParameters):
    """Model deployer step parameters for BentoML.

    Attributes:
        model_name: the name of the model to deploy.
        port: the port to use for the prediction service.
        workers: number of workers to use for the prediction service
        backlog: the number of requests to queue up before rejecting requests.
        production: whether to deploy the service in production mode.
        working_dir: the working directory to use for the prediction service.
        host: the host to use for the prediction service.
        timeout: the number of seconds to wait for the service to start/stop.
    """

    model_name: str
    port: int
    workers: Optional[int] = None
    backlog: Optional[int] = None
    production: bool = False
    working_dir: Optional[str] = None
    host: Optional[str] = None
    timeout: int = DEFAULT_SERVICE_START_STOP_TIMEOUT * 2


@step(enable_cache=False)
def bentoml_model_deployer_step(
    deploy_decision: bool,
    bento: bento.Bento,
    params: BentoMLDeployerParameters,
) -> BentoMLDeploymentService:
    """Model deployer pipeline step for BentoML.

    This step deploys a given Bento to a local BentoML http prediction server.

    Args:
        deploy_decision: whether to deploy the model or not
        params: parameters for the deployer step
        bento: the bento artifact to deploy

    Raises:
        ValueError: if the zenml repo is not initialized

    Returns:
        BentoML deployment service
    """
    # get the path of the ZenML repo
    repo_path = Client.find_repository()
    if not repo_path:
        raise ValueError("No ZenML repository found.")

    # get the current active model deployer
    model_deployer = cast(
        BentoMLModelDeployer, BentoMLModelDeployer.get_active_model_deployer()
    )

    # get pipeline name, step name and run id
    step_env = cast(StepEnvironment, Environment()[STEP_ENVIRONMENT_NAME])
    pipeline_name = step_env.pipeline_name
    run_id = step_env.pipeline_run_id
    step_name = step_env.step_name

    # fetch existing services with same pipeline name, step name and model name
    existing_services = model_deployer.find_model_server(
        pipeline_name=pipeline_name,
        pipeline_step_name=step_name,
        model_name=params.model_name,
    )

    # Return the apis endpoint of the defined service to use in the predict.
    # This is a workaround to get the endpoints of the service defined as functions
    # from the user code in the BentoML service.
    def service_apis(bento_tag: str) -> List[str]:
        service = bentoml.load(bento_tag)
        apis = service.apis
        apis_paths = list(apis.keys())
        return apis_paths

    # create a config for the new model service
    predictor_cfg = BentoMLDeploymentConfig(
        model_name=params.model_name,
        bento=str(bento.tag),
        model_uri=bento.info.labels.get("model_uri"),
        bento_uri=bento.info.labels.get("bento_uri"),
        apis=service_apis(str(bento.tag)),
        workers=params.workers,
        working_dir=params.working_dir or str(repo_path),
        port=params.port,
        pipeline_name=pipeline_name,
        pipeline_run_id=run_id,
        pipeline_step_name=step_name,
    )

    # Creating a new service with inactive state and status by default
    service = BentoMLDeploymentService(predictor_cfg)
    if existing_services:
        service = cast(BentoMLDeploymentService, existing_services[0])

    if not deploy_decision and existing_services:
        logger.info(
            f"Skipping model deployment because the model quality does not "
            f"meet the criteria. Reusing last model server deployed by step "
            f"'{step_name}' and pipeline '{pipeline_name}' for model "
            f"'{params.model_name}'..."
        )
        if not service.is_running:
            service.start(timeout=params.timeout)
        return service

    # create a new model deployment and replace an old one if it exists
    new_service = cast(
        BentoMLDeploymentService,
        model_deployer.deploy_model(
            replace=True,
            config=predictor_cfg,
            timeout=params.timeout,
        ),
    )

    logger.info(
        f"BentoML deployment service started and reachable at:\n"
        f"    {new_service.prediction_url}\n"
    )

    return new_service


def bentoml_deployer_step(
    enable_cache: bool = True,
    name: Optional[str] = None,
) -> Type[BaseStep]:
    """Creates a pipeline step to deploy a given ML model with a local BentoML prediction server.

    The returned step can be used in a pipeline to implement continuous
    deployment for an BentoML model.

    Args:
        enable_cache: Specify whether caching is enabled for this step. If no
            value is passed, caching is enabled by default
        name: Name of the step.

    Returns:
        an BentoML model deployer pipeline step
    """
    logger.warning(
        "The `bentoml_deployer_step` function is deprecated. Please "
        "use the built-in `bentoml_model_deployer_step` step instead."
    )
    return bentoml_model_deployer_step
