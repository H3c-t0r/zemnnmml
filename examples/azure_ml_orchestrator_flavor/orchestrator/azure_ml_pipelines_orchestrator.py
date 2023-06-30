#  Copyright (c) ZenML GmbH 2022. All Rights Reserved.
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
"""Implementation of the AzureMLPipelines orchestrator."""
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Type, cast
from zenml.entrypoints import StepEntrypointConfiguration
from zenml.utils.source_utils import get_source_root
import webbrowser
from azure.ai.ml import MLClient, command, dsl
from azure.ai.ml.entities import Environment
from azure.identity import AzureCliCredential
from zenml.utils.pipeline_docker_image_builder import (
    DOCKER_IMAGE_ZENML_CONFIG_DIR,
    PipelineDockerImageBuilder,
)
from orchestrator.azure_ml_pipelines_orchestrator_flavor import (
    AzureMLPipelinesOrchestratorConfig,
    AzureMLPipelinesOrchestratorSettings,
)
from zenml.io import fileio
from zenml.logger import get_logger
from zenml.orchestrators import ContainerizedOrchestrator
from zenml.orchestrators.utils import get_orchestrator_run_name
from zenml.stack import StackValidator
from zenml.utils import io_utils

if TYPE_CHECKING:
    from zenml.config.base_settings import BaseSettings
    from zenml.models.pipeline_deployment_models import (
        PipelineDeploymentResponseModel,
    )
    from zenml.stack import Stack
    from zenml.steps import ResourceSettings


logger = get_logger(__name__)

ENV_ZENML_AZUREML_RUN_ID = "ENV_ZENML_AZUREML_RUN_ID"


class AzureMLPipelinesOrchestrator(ContainerizedOrchestrator):
    """Orchestrator responsible for running pipelines using AzureMLPipelines."""

    @property
    def config(self) -> AzureMLPipelinesOrchestratorConfig:
        """Returns the `AzureMLPipelinesOrchestratorConfig` config.

        Returns:
            The configuration.
        """
        return cast(AzureMLPipelinesOrchestratorConfig, self._config)

    @property
    def settings_class(self) -> Optional[Type["BaseSettings"]]:
        """Settings class for the AzureMLPipelines orchestrator.

        Returns:
            The settings class.
        """
        return AzureMLPipelinesOrchestratorSettings

    def get_orchestrator_run_id(self) -> str:
        """Returns the run id of the active orchestrator run.

        Important: This needs to be a unique ID and return the same value for
        all steps of a pipeline run.

        Returns:
            The orchestrator run id.

        Raises:
            RuntimeError: If the run id cannot be read from the environment.
        """
        try:
            return os.environ[ENV_ZENML_AZUREML_RUN_ID]
        except KeyError:
            raise RuntimeError(
                "Unable to read run id from environment variable "
                f"{ENV_ZENML_AZUREML_RUN_ID}."
            )
    #TODO: add validator func

    # @property
    # def validator(self) -> Optional[StackValidator]:
    #     """Ensures a stack with only remote components and a container registry.
    #
    #     Returns:
    #         A `StackValidator` instance.
    #     """
    #
    #     def _validate(stack: "Stack") -> Tuple[bool, str]:
    #         container_registry = stack.container_registry
    #
    #         # should not happen, because the stack validation takes care of
    #         # this, but just in case
    #         assert container_registry is not None
    #
    #         kubernetes_context = self.config.kubernetes_context
    #         connector = self.get_connector()
    #         msg = f"'{self.name}' AzureMLPipelines orchestrator error: "
    #
    #         if not connector:
    #             if not kubernetes_context:
    #                 return False, (
    #                     f"{msg}you must either link this stack component to a "
    #                     "Kubernetes service connector (see the 'zenml "
    #                     "orchestrator connect' CLI command) or explicitly set "
    #                     "the `kubernetes_context` attribute to the name of the "
    #                     "Kubernetes config context pointing to the cluster "
    #                     "where you would like to run pipelines."
    #                 )
    #
    #             contexts, active_context = self.get_kubernetes_contexts()
    #
    #             if kubernetes_context not in contexts:
    #                 return False, (
    #                     f"{msg}could not find a Kubernetes context named "
    #                     f"'{kubernetes_context}' in the local "
    #                     "Kubernetes configuration. Please make sure that the "
    #                     "Kubernetes cluster is running and that the kubeconfig "
    #                     "file is configured correctly. To list all configured "
    #                     "contexts, run:\n\n"
    #                     "  `kubectl config get-contexts`\n"
    #                 )
    #             if kubernetes_context != active_context:
    #                 logger.warning(
    #                     f"{msg}the Kubernetes context '{kubernetes_context}' "
    #                     f"configured for the AzureMLPipelines orchestrator is not "
    #                     f"the same as the active context in the local "
    #                     f"Kubernetes configuration. If this is not deliberate,"
    #                     f" you should update the orchestrator's "
    #                     f"`kubernetes_context` field by running:\n\n"
    #                     f"  `zenml orchestrator update {self.name} "
    #                     f"--kubernetes_context={active_context}`\n"
    #                     f"To list all configured contexts, run:\n\n"
    #                     f"  `kubectl config get-contexts`\n"
    #                     f"To set the active context to be the same as the one "
    #                     f"configured in the AzureMLPipelines orchestrator and "
    #                     f"silence this warning, run:\n\n"
    #                     f"  `kubectl config use-context "
    #                     f"{kubernetes_context}`\n"
    #                 )
    #
    #         silence_local_validations_msg = (
    #             f"To silence this warning, set the "
    #             f"`skip_local_validations` attribute to True in the "
    #             f"orchestrator configuration by running:\n\n"
    #             f"  'zenml orchestrator update {self.name} "
    #             f"--skip_local_validations=True'\n"
    #         )
    #
    #         if (
    #             not self.config.skip_local_validations
    #             and not self.config.is_local
    #         ):
    #             # if the orchestrator is not running in a local k3d cluster,
    #             # we cannot have any other local components in our stack,
    #             # because we cannot mount the local path into the container.
    #             # This may result in problems when running the pipeline, because
    #             # the local components will not be available inside the
    #             # AzureMLPipelines containers.
    #
    #             # go through all stack components and identify those that
    #             # advertise a local path where they persist information that
    #             # they need to be available when running pipelines.
    #             for stack_comp in stack.components.values():
    #                 local_path = stack_comp.local_path
    #                 if not local_path:
    #                     continue
    #                 return False, (
    #                     f"{msg}the AzureMLPipelines orchestrator is configured to run "
    #                     f"pipelines in a remote Kubernetes cluster, but the "
    #                     f"'{stack_comp.name}' {stack_comp.type.value} is a "
    #                     f"local stack component and will not be available in "
    #                     f"the AzureMLPipelines pipeline step.\n"
    #                     f"Please ensure that you always use non-local "
    #                     f"stack components with a remote AzureMLPipelines orchestrator, "
    #                     f"otherwise you may run into pipeline execution "
    #                     f"problems. You should use a flavor of "
    #                     f"{stack_comp.type.value} other than "
    #                     f"'{stack_comp.flavor}'.\n"
    #                     + silence_local_validations_msg
    #                 )
    #
    #             # if the orchestrator is remote, the container registry must
    #             # also be remote.
    #             if container_registry.config.is_local:
    #                 return False, (
    #                     f"{msg}the AzureMLPipelines orchestrator is configured to run "
    #                     f"pipelines in a remote Kubernetes cluster, but the "
    #                     f"'{container_registry.name}' container registry URI "
    #                     f"'{container_registry.config.uri}' "
    #                     f"points to a local container registry. Please ensure "
    #                     f"that you always use non-local stack components with "
    #                     f"a remote AzureMLPipelines orchestrator, otherwise you will "
    #                     f"run into problems. You should use a flavor of "
    #                     f"container registry other than "
    #                     f"'{container_registry.flavor}'.\n"
    #                     + silence_local_validations_msg
    #                 )
    #
    #         return True, ""
    #
    #     return StackValidator(
    #         required_components={
    #             StackComponentType.CONTAINER_REGISTRY,
    #             StackComponentType.IMAGE_BUILDER,
    #         },
    #         custom_validation_function=_validate,
    #     )


    # def prepare_pipeline_deployment(
    #     self, deployment: "PipelineDeployment", stack: "Stack"
    # ) -> None:
    #     """Build a Docker image and push it to the container registry.
    #
    #     Args:
    #         deployment: The pipeline deployment configuration.
    #         stack: The stack on which the pipeline will be deployed.
    #     """
    #     docker_image_builder = PipelineDockerImageBuilder()
    #     repo_digest = docker_image_builder.build_docker_image(
    #         deployment=deployment, stack=stack
    #     )
    #     #repo_digest = "zenmlazuretest.azurecr.io/zenml@sha256:972ffa104683ace512f76216d234650d9ab02e94c38e33adeedcd11a2e8d64d3"
    #     #deployment.add_extra(ORCHESTRATOR_DOCKER_IMAGE_KEY, repo_digest)

    # def _prepare_environment(
    #     self,
    #     workspace: Workspace,
    #     docker_settings: "DockerSettings",
    #     run_name: str,
    #     environment_variables: Dict[str, str],
    #     environment_name: Optional[str] = None,
    # ) -> Environment:
    #     """Prepares the environment in which Azure will run all jobs.
    #
    #     Args:
    #         workspace: The AzureML Workspace that has configuration
    #             for a storage account, container registry among other
    #             things.
    #         docker_settings: The Docker settings for this step.
    #         run_name: The name of the pipeline run that can be used
    #             for naming environments and runs.
    #         environment_variables: Environment variables to set in the
    #             environment.
    #         environment_name: Optional name of an existing environment to use.
    #
    #     Returns:
    #         The AzureML Environment object.
    #     """
    #     docker_image_builder = PipelineDockerImageBuilder()
    #     requirements_files = docker_image_builder.gather_requirements_files(
    #         docker_settings=docker_settings,
    #         stack=Client().active_stack,
    #         log=False,
    #     )
    #     requirements = list(
    #         itertools.chain.from_iterable(
    #             r[1].split("\n") for r in requirements_files
    #         )
    #     )
    #     requirements.append(f"zenml=={zenml.__version__}")
    #     logger.info(
    #         "Using requirements for AzureML step operator environment: %s",
    #         requirements,
    #     )
    #     if environment_name:
    #         environment = Environment.get(
    #             workspace=workspace, name=environment_name
    #         )
    #         if not environment.python.conda_dependencies:
    #             environment.python.conda_dependencies = (
    #                 CondaDependencies.create(
    #                     python_version=ZenMLEnvironment.python_version()
    #                 )
    #             )
    #
    #         for requirement in requirements:
    #             environment.python.conda_dependencies.add_pip_package(
    #                 requirement
    #             )
    #     else:
    #         environment = Environment(name=f"zenml-{run_name}")
    #         environment.python.conda_dependencies = CondaDependencies.create(
    #             pip_packages=requirements,
    #             python_version=ZenMLEnvironment.python_version(),
    #         )
    #
    #         if docker_settings.parent_image:
    #             # replace the default azure base image
    #             environment.docker.base_image = docker_settings.parent_image
    #
    #     # set credentials to access azure storage
    #     for key in [
    #         "AZURE_STORAGE_ACCOUNT_KEY",
    #         "AZURE_STORAGE_ACCOUNT_NAME",
    #         "AZURE_STORAGE_CONNECTION_STRING",
    #         "AZURE_STORAGE_SAS_TOKEN",
    #     ]:
    #         value = os.getenv(key)
    #         if value:
    #             environment_variables[key] = value
    #
    #     environment_variables[
    #         ENV_ZENML_CONFIG_PATH
    #     ] = f"./{DOCKER_IMAGE_ZENML_CONFIG_DIR}"
    #     environment_variables.update(docker_settings.environment)
    #     environment.environment_variables = environment_variables
    #     return environment

    def prepare_or_run_pipeline(
            self, deployment: "PipelineDeployment", stack: "Stack"
    ) -> None:
        """Prepares or runs a pipeline on AzureML.

        Args    :
            deployment: The deployment to prepare or run.
            stack: The stack to run on.
        """
        if deployment.schedule:
            logger.warning(
                "The AzureML Orchestrator currently does not support the "
                "use of schedules. The `schedule` will be ignored "
                "and the pipeline will be run immediately."
            )

        credential = AzureCliCredential()
        ml_client = MLClient.from_config(credential=credential)
        # get the compute target to use to run our pipeline
        # can be single node or cluster
        cpu_compute_target = "cpu-cluster"
        # cpu_cluster = ml_client.compute.get(cpu_compute_target)

        # get/create the environment that will be used to run each step of the pipeline
        # each step can have its own environment, or they can all use the same one
        # Here you specify your dependencies etc.
        # This can be a Docker image.
        custom_env_name = "zenml-test-env"
        source_directory = get_source_root()
        orchestrator_run_name = get_orchestrator_run_name(
            pipeline_name=deployment.pipeline.name
        ).replace("_", "-")
        docker_image_builder = PipelineDockerImageBuilder()
        image_name_or_digest,_,_ = docker_image_builder.build_docker_image(docker_settings=deployment.pipeline_configuration.docker_settings,
                                                        tag="azureml",stack=stack)
        pipeline_job_env = Environment(
            name=custom_env_name,
            image=image_name_or_digest,
        )
        # pipeline_job_env = ml_client.environments.create_or_update(
        #     pipeline_job_env
        # )
        # pipeline_job_env = ml_client.environments.get(
        #     custom_env_name, version="9"
        # )

        steps = []
        for step_name, _ in deployment.steps.items():
            container_command = (
                StepEntrypointConfiguration.get_entrypoint_command()
            )
            arguments = StepEntrypointConfiguration.get_entrypoint_arguments(
                step_name=step_name
            )
            entrypoint = container_command + arguments

            job = command(
                environment=pipeline_job_env,
                compute=cpu_compute_target,
                command=" ".join(entrypoint),
                experiment_name=orchestrator_run_name,
                display_name=orchestrator_run_name,
                code=source_directory,
            )
            steps.append(job)

        @dsl.pipeline(
            compute=cpu_compute_target,
        )
        def test_pipeline():
            steps[0]()

        pipeline = test_pipeline()

        pipeline_job = ml_client.jobs.create_or_update(
            pipeline,
            experiment_name="manual_test",
        )
        # open the pipeline in web browser
        webbrowser.open(pipeline_job.studio_url)

    @property
    def root_directory(self) -> str:
        """Returns path to the root directory for all files concerning this orchestrator.

        Returns:
            Path to the root directory.
        """
        return os.path.join(
            io_utils.get_global_config_directory(),
            "azuremlpipelines",
            str(self.id),
        )

    @property
    def pipeline_directory(self) -> str:
        """Path to a directory in which the AzureMLPipelines pipeline files are stored.

        Returns:
            Path to the pipeline directory.
        """
        return os.path.join(self.root_directory, "pipelines")

    @property
    def _pid_file_path(self) -> str:
        """Returns path to the daemon PID file.

        Returns:
            Path to the daemon PID file.
        """
        return os.path.join(self.root_directory, "azuremlpipelines_daemon.pid")

    @property
    def log_file(self) -> str:
        """Path of the daemon log file.

        Returns:
            Path of the daemon log file.
        """
        return os.path.join(self.root_directory, "azuremlpipelines_daemon.log")
