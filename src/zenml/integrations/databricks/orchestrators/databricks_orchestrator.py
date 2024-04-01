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
"""Implementation of the Databricks orchestrator."""

import os
import re
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, cast
from uuid import uuid4

from zenml.entrypoints.step_entrypoint_configuration import StepEntrypointConfiguration
from zenml.enums import StackComponentType
from zenml.environment import Environment
from zenml.integrations.databricks.flavors.databricks_orchestrator_flavor import (
    DatabricksOrchestratorConfig,
    DatabricksOrchestratorSettings,
)
from zenml.integrations.databricks.orchestrators.databricks_utils import DatabricksTask, generate_databricks_yaml
from zenml.io import fileio
from zenml.logger import get_logger
from zenml.orchestrators import (
    ContainerizedOrchestrator,
)
from zenml.orchestrators.utils import get_orchestrator_run_name
from zenml.stack import StackValidator
from zenml.utils.yaml_utils import write_yaml

if TYPE_CHECKING:
    from zenml.models import PipelineDeploymentResponse
    from zenml.stack import Stack


logger = get_logger(__name__)

ENV_ZENML_DATABRICKS_ORCHESTRATOR_RUN_ID = "ZENML_DATABRICKS_ORCHESTRATOR_RUN_ID"


class DatabricksOrchestrator(ContainerizedOrchestrator):
    """Base class for Orchestrator responsible for running pipelines remotely in a VM.

    This orchestrator does not support running on a schedule.
    """

    # The default instance type to use if none is specified in settings
    DEFAULT_INSTANCE_TYPE: Optional[str] = None

    @property
    def validator(self) -> Optional[StackValidator]:
        """Validates the stack.

        In the remote case, checks that the stack contains a container registry,
        image builder and only remote components.

        Returns:
            A `StackValidator` instance.
        """

        def _validate_remote_components(
            stack: "Stack",
        ) -> Tuple[bool, str]:
            for component in stack.components.values():
                if not component.config.is_local:
                    continue

                return False, (
                    f"The Skypilot orchestrator runs pipelines remotely, "
                    f"but the '{component.name}' {component.type.value} is "
                    "a local stack component and will not be available in "
                    "the Skypilot step.\nPlease ensure that you always "
                    "use non-local stack components with the Skypilot "
                    "orchestrator."
                )

            return True, ""

        return StackValidator(
            required_components={
                StackComponentType.CONTAINER_REGISTRY,
                StackComponentType.IMAGE_BUILDER,
            },
            custom_validation_function=_validate_remote_components,
        )

    def get_orchestrator_run_id(self) -> str:
        """Returns the active orchestrator run id.

        Raises:
            RuntimeError: If the environment variable specifying the run id
                is not set.

        Returns:
            The orchestrator run id.
        """
        try:
            return os.environ[ENV_ZENML_DATABRICKS_ORCHESTRATOR_RUN_ID]
        except KeyError:
            raise RuntimeError(
                "Unable to read run id from environment variable "
                f"{ENV_ZENML_DATABRICKS_ORCHESTRATOR_RUN_ID}."
            )

    @property
    def config(self) -> DatabricksOrchestratorConfig:
        """Returns the `DatabricksOrchestratorConfig` config.

        Returns:
            The configuration.
        """
        return cast(DatabricksOrchestratorConfig, self._config)

    @property
    def pipeline_directory(self) -> str:
        """Returns path to a directory in which the kubeflow pipeline files are stored.

        Returns:
            Path to the pipeline directory.
        """
        return os.path.join(self.root_directory, "pipelines")
    
    def setup_credentials(self) -> None:
        """Set up credentials for the orchestrator."""
        connector = self.get_connector()
        assert connector is not None
        connector.configure_local_client()

    @abstractmethod
    def prepare_environment_variable(self, set: bool = True) -> None:
        """Set up Environment variables that are required for the orchestrator.

        Args:
            set: Whether to set the environment variables or not.
        """

    def prepare_or_run_pipeline(
        self,
        deployment: "PipelineDeploymentResponse",
        stack: "Stack",
        environment: Dict[str, str],
    ) -> Any:
        """Creates a databricks yaml file.

        This functions as an intermediary representation of the pipeline which
        is then deployed to the kubeflow pipelines instance.

        How it works:
        -------------
        Before this method is called the `prepare_pipeline_deployment()`
        method builds a docker image that contains the code for the
        pipeline, all steps the context around these files.

        Based on this docker image a callable is created which builds
        container_ops for each step (`_construct_databricks_pipeline`).
        To do this the entrypoint of the docker image is configured to
        run the correct step within the docker image. The dependencies
        between these container_ops are then also configured onto each
        container_op by pointing at the downstream steps.

        This callable is then compiled into a databricks yaml file that is used as
        the intermediary representation of the kubeflow pipeline.

        This file, together with some metadata, runtime configurations is
        then uploaded into the kubeflow pipelines cluster for execution.

        Args:
            deployment: The pipeline deployment to prepare or run.
            stack: The stack the pipeline will run on.
            environment: Environment variables to set in the orchestration
                environment.

        Raises:
            RuntimeError: If trying to run a pipeline in a notebook
                environment.
        """
        # First check whether the code running in a notebook
        if Environment.in_notebook():
            raise RuntimeError(
                "The Kubeflow orchestrator cannot run pipelines in a notebook "
                "environment. The reason is that it is non-trivial to create "
                "a Docker image of a notebook. Please consider refactoring "
                "your notebook cells into separate scripts in a Python module "
                "and run the code outside of a notebook when using this "
                "orchestrator."
            )

        assert stack.container_registry

        # Create a callable for future compilation into a dsl.Pipeline.
        def _construct_databricks_pipeline() -> Dict[str, Any]:
            """Create a databrcks task for each step.

            This should contain the name of the step or task and configures the
            entrypoint of the task to run the step.

            Additionally, this gives each task information about its
            direct downstream steps.
            """
            tasks = []
            for step_name, step in deployment.step_configurations.items():
                image = self.get_image(
                    deployment=deployment, step_name=step_name
                )

                # The command will be needed to eventually call the python step
                # within the docker container
                command = StepEntrypointConfiguration.get_entrypoint_command()

                # The arguments are passed to configure the entrypoint of the
                # docker container when the step is called.
                arguments = (
                    StepEntrypointConfiguration.get_entrypoint_arguments(
                        step_name=step_name, deployment_id=deployment.id
                    )
                )
                breakpoint()
                task = self.convert_step_to_task(f"{deployment.id}_{step_name}", command, arguments)
                tasks.append(task)
                breakpoint()
                # Create a container_op - the kubeflow equivalent of a step. It
                # contains the name of the step, the name of the docker image,
                # the command to use to run the step entrypoint
                # (e.g. `python -m zenml.entrypoints.step_entrypoint`)
                # and the arguments to be passed along with the command. Find
                # out more about how these arguments are parsed and used
                # in the base entrypoint `run()` method.
                settings = cast(
                    DatabricksOrchestratorSettings, self.get_settings(step)
                )

                # Find the upstream container ops of the current step and
                # configure the current container op to run after them
            
            databricks_yaml = generate_databricks_yaml(
                pipeline_name=deployment.pipeline_configuration.name, tasks=tasks
            )
            breakpoint()
            return databricks_yaml

        orchestrator_run_name = get_orchestrator_run_name(
            pipeline_name=deployment.pipeline_configuration.name
        )

        # Get a filepath to use to save the finished yaml to
        fileio.makedirs(self.pipeline_directory)
        pipeline_file_path = os.path.join(
            self.pipeline_directory, f"{orchestrator_run_name}.yaml"
        )
        breakpoint()
        # write the argo pipeline yaml to a file
        write_yaml(file_path=pipeline_file_path, contents=_construct_databricks_pipeline())

        logger.info(
            "Writing Kubeflow workflow definition to `%s`.", pipeline_file_path
        )

        # using the databricks client uploads the pipeline to kubeflow pipelines and
        # runs it there
        breakpoint()
        self._upload_and_run_pipeline(
            deployment=deployment,
            pipeline_file_path=pipeline_file_path,
            run_name=orchestrator_run_name,
        )
        

    def sanitize_cluster_name(self, name: str) -> str:
        """Sanitize the value to be used in a cluster name.

        Args:
            name: Arbitrary input cluster name.

        Returns:
            Sanitized cluster name.
        """
        name = re.sub(
            r"[^a-z0-9-]", "-", name.lower()
        )  # replaces any character that is not a lowercase letter, digit, or hyphen with a hyphen
        name = re.sub(r"^[-]+", "", name)  # trim leading hyphens
        name = re.sub(r"[-]+$", "", name)  # trim trailing hyphens
        return name
    
    def convert_step_to_task(self, task_name: str, command: str, arguments: List[str]) -> DatabricksTask:
        return DatabricksTask(
            task_key=task_name,
            python_wheel_task={
                "entry_point": command,
                "package_name": "zenml",
                "parameters": arguments,
            },
            libraries=[
                {"whl": "../../dist/*.whl"},
                {
                    "pypi": {
                        "package": "zenml",
                    }
                },
            ],
        )
    

