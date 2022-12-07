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
"""Implementation of the SageMaker orchestrator."""

from typing import TYPE_CHECKING, Any, cast

import sagemaker

from zenml.constants import ORCHESTRATOR_DOCKER_IMAGE_KEY
from zenml.entrypoints import StepEntrypointConfiguration
from zenml.integrations.aws.flavors.sagemaker_orchestrator_flavor import (
    SagemakerOrchestratorConfig,
)
from zenml.orchestrators.base_orchestrator import BaseOrchestrator
from zenml.utils.pipeline_docker_image_builder import PipelineDockerImageBuilder

if TYPE_CHECKING:
    from zenml.config.pipeline_deployment import PipelineDeployment
    from zenml.stack import Stack


class SagemakerOrchestrator(BaseOrchestrator):
    """Orchestrator responsible for running pipelines on Sagemaker."""

    @property
    def config(self) -> SagemakerOrchestratorConfig:
        """Returns the `SagemakerOrchestratorConfig` config.

        Returns:
            The configuration.
        """
        return cast(SagemakerOrchestratorConfig, self._config)

    def get_orchestrator_run_id(self) -> str:
        """Returns the run id of the active orchestrator run.

        Important: This needs to be a unique ID and return the same value for
        all steps of a pipeline run.

        Returns:
            The orchestrator run id.
        """
        return "sagemaker"

    def prepare_pipeline_deployment(
        self, deployment: "PipelineDeployment", stack: "Stack"
    ) -> None:
        """Build a Docker image and push it to the container registry.

        Args:
            deployment: The pipeline deployment configuration.
            stack: The stack on which the pipeline will be deployed.
        """
        docker_image_builder = PipelineDockerImageBuilder()
        repo_digest = docker_image_builder.build_and_push_docker_image(
            deployment=deployment, stack=stack
        )
        deployment.add_extra(ORCHESTRATOR_DOCKER_IMAGE_KEY, repo_digest)

    def prepare_or_run_pipeline(
        self, deployment: "PipelineDeployment", stack: "Stack"
    ) -> Any:
        """Prepares or runs a pipeline on Sagemaker.

        Args:
            deployment: The deployment to prepare or run.
            stack: The stack to run on.

        Returns:
            The result of the pipeline run.
        """
        # session = sagemaker.Session(default_bucket=self.config.bucket)
        # for step in deployment.steps.values():
        #     self.run_step(
        #         step=step,
        #     )
        sagemaker_steps = []
        for step_name, step in deployment.steps.items():
            command = StepEntrypointConfiguration.get_entrypoint_command()
            arguments = {
                StepEntrypointConfiguration.get_entrypoint_arguments(
                    step_name=step_name
                )
            }
            breakpoint()
            sagemaker_step = sagemaker.processing.ProcessingStep(
                name=step_name,
                processor=sagemaker.processing.Processor(
                    image_uri=deployment.extra[ORCHESTRATOR_DOCKER_IMAGE_KEY],
                    role=self.config.role,
                    instance_count=1,
                    instance_type="ml.m5.xlarge",
                ),
                job_arguments=arguments,
                command=command,
            )
            sagemaker_steps.append(sagemaker_step)

        pipeline = sagemaker.Pipeline()
        pipeline.start()
