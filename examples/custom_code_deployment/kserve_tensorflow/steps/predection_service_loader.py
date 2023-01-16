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
from typing import cast

from zenml.integrations.kserve.model_deployers import KServeModelDeployer
from zenml.integrations.kserve.services import KServeDeploymentService
from zenml.steps import BaseParameters, step


class PredectionServiceLoaderStepParameters(BaseParameters):
    """Prediction Service loader parameters.

    Attrs:
        pipeline_name: name of the pipeline that deployed the model.
        step_name: the name of the step that deployed the model.
        model_name: the name of the model that was deployed.
    """

    pipeline_name: str
    step_name: str
    model_name: str


@step(enable_cache=False)
def kserve_prediction_service_loader(
    params: PredectionServiceLoaderStepParameters,
) -> KServeDeploymentService:
    """Get the KServe prediction service started by the deployment pipeline."""
    model_deployer = KServeModelDeployer.get_active_model_deployer()

    services = model_deployer.find_model_server(
        pipeline_name=params.pipeline_name,
        pipeline_step_name=params.step_name,
        model_name=params.model_name,
    )
    if not services:
        raise RuntimeError(
            f"No KServe prediction server deployed by the "
            f"'{params.step_name}' step in the '{params.pipeline_name}' "
            f"pipeline for the '{params.model_name}' model is currently "
            f"running."
        )

    if not services[0].is_running:
        raise RuntimeError(
            f"The KServe prediction server last deployed by the "
            f"'{params.step_name}' step in the '{params.pipeline_name}' "
            f"pipeline for the '{params.model_name}' model is not currently "
            f"running."
        )

    return cast(KServeDeploymentService, services[0])
