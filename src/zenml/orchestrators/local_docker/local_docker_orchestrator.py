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
"""Implementation of the ZenML local Docker orchestrator."""

import os
import sys
from typing import TYPE_CHECKING, Any, ClassVar, Dict

from zenml.constants import ORCHESTRATOR_DOCKER_IMAGE_KEY
from zenml.entrypoints import StepEntrypointConfiguration
from zenml.logger import get_logger
from zenml.orchestrators import BaseOrchestrator
from zenml.stack import Stack
from zenml.utils.pipeline_docker_image_builder import PipelineDockerImageBuilder

if TYPE_CHECKING:
    from zenml.config.pipeline_configurations import PipelineDeployment

logger = get_logger(__name__)


class LocalDockerOrchestrator(BaseOrchestrator, PipelineDockerImageBuilder):
    """Orchestrator responsible for running pipelines locally using Docker.

    This orchestrator does not allow for concurrent execution of steps and also
    does not support running on a schedule.
    """

    FLAVOR: ClassVar[str] = "local_docker"

    def prepare_pipeline_deployment(
        self,
        pipeline: "PipelineDeployment",
        stack: "Stack",
    ) -> None:
        """Build a Docker image and (maybe) push it to the container registry.

        Args:
            pipeline: Representation of the pipeline to run.
            stack: Stack on which the pipeline will run.
        """
        if stack.container_registry:
            repo_digest = self.build_and_push_docker_image(
                run_config=pipeline, stack=stack
            )
            pipeline.add_extra(ORCHESTRATOR_DOCKER_IMAGE_KEY, repo_digest)
        else:
            # If there is no container registry, we only build the image
            target_image_name = self.get_target_image_name(deployment=pipeline)
            self.build_docker_image(
                target_image_name=target_image_name,
                run_config=pipeline,
                stack=stack,
            )
            pipeline.add_extra(ORCHESTRATOR_DOCKER_IMAGE_KEY, target_image_name)

    @staticmethod
    def _get_volumes(stack: "Stack") -> Dict[str, Dict[str, str]]:
        """Get mount volumes for all necessary local stack components.

        Args:
            stack: The stack on which the pipeline is running.

        Returns:
            List of volumes to mount.
        """
        volumes = {}

        # Add a volume for all local paths of stack components
        for stack_comp in stack.components.values():
            local_path = stack_comp.local_path
            if not local_path:
                continue

            volumes[local_path] = {"bind": local_path, "mode": "rw"}

        return volumes

    def prepare_or_run_pipeline(
        self,
        pipeline: "PipelineDeployment",
        stack: "Stack",
    ) -> Any:
        """Sequentially runs all pipeline steps in local Docker containers.

        Args:
            pipeline: Representation of the pipeline to run.
            stack: The stack the pipeline will run on.
        """
        if pipeline.schedule:
            logger.warning(
                "Local Docker Orchestrator currently does not support the"
                "use of schedules. The `schedule` will be ignored "
                "and the pipeline will be run immediately."
            )

        from docker.client import DockerClient

        docker_client = DockerClient.from_env()
        image_name = pipeline.pipeline.extra[ORCHESTRATOR_DOCKER_IMAGE_KEY]
        entrypoint = StepEntrypointConfiguration.get_entrypoint_command()

        # Run each step
        for step_name, step in pipeline.steps.items():
            if self.requires_resources_in_orchestration_environment(step):
                logger.warning(
                    "Specifying step resources is not supported for the local "
                    "Docker orchestrator, ignoring resource configuration for "
                    "step %s.",
                    step.config.name,
                )

            arguments = StepEntrypointConfiguration.get_entrypoint_arguments(
                step_name=step_name
            )
            volumes = self._get_volumes(stack=stack)
            user = None
            if sys.platform != "win32":
                user = os.getuid()
            logger.info("Running step `%s` in Docker:", step_name)
            logs = docker_client.containers.run(
                image=image_name,
                entrypoint=entrypoint,
                command=arguments,
                user=user,
                volumes=volumes,
                stream=True,
            )

            for line in logs:
                logger.info(line.strip().decode())
