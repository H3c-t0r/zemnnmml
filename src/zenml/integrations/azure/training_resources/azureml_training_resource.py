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

from typing import TYPE_CHECKING, Any, List, Optional

from azureml.core import (
    ComputeTarget,
    Environment,
    Experiment,
    ScriptRunConfig,
    Workspace,
)
from azureml.core.authentication import (
    AbstractAuthentication,
    ServicePrincipalAuthentication,
)
from azureml.core.conda_dependencies import CondaDependencies

from zenml.enums import StackComponentType, TrainingResourceFlavor
from zenml.environment import Environment as ZenMLEnvironment
from zenml.repository import Repository
from zenml.stack.stack_component_class_registry import (
    register_stack_component_class,
)
from zenml.training_resources import BaseTrainingResource

if TYPE_CHECKING:
    pass


@register_stack_component_class(
    component_type=StackComponentType.TRAINING_RESOURCE,
    component_flavor=TrainingResourceFlavor.AZUREML,
)
class AzureMLTrainingResource(BaseTrainingResource):
    """Training resource to run a step on AzureML."""

    supports_local_execution = True
    supports_remote_execution = True
    subscription_id: str
    resource_group: str
    workspace_name: str
    compute_target_name: str
    environment_name: str

    # Service principal authentication https://docs.microsoft.com/en-us/azure/machine-learning/how-to-setup-authentication#configure-a-service-principal
    tenant_id: Optional[str] = None
    service_principal_id: Optional[str] = None
    service_principal_password: Optional[str] = None

    @property
    def flavor(self) -> TrainingResourceFlavor:
        """The training resource flavor."""
        return TrainingResourceFlavor.AZUREML

    def _get_authentication(self) -> Optional[AbstractAuthentication]:
        if (
            self.tenant_id
            and self.service_principal_id
            and self.service_principal_password
        ):
            return ServicePrincipalAuthentication(
                tenant_id=self.tenant_id,
                service_principal_id=self.service_principal_id,
                service_principal_password=self.service_principal_password,
            )
        return None

    def launch(
        self,
        pipeline_name: str,
        run_name: str,
        entrypoint_command: List[str],
        requirements: List[str],
    ) -> Any:
        """Launches a step on the training resource."""
        workspace = Workspace.get(
            subscription_id=self.subscription_id,
            resource_group=self.resource_group,
            name=self.workspace_name,
            auth=self._get_authentication(),
        )

        requirements.append(
            "git+https://github.com/zenml-io/zenml.git@wip/azureml"
        )
        environment = Environment.get(
            workspace=workspace, name=self.environment_name
        )

        if environment.python.conda_dependencies:
            for requirement in requirements:
                environment.python.conda_dependencies.add_pip_package(
                    requirement
                )
        else:
            environment.python.conda_dependencies = CondaDependencies.create(
                pip_packages=requirements,
                python_version=ZenMLEnvironment.python_version(),
            )

        environment.environment_variables = {
            "AZURE_STORAGE_ACCOUNT_KEY": "",
            "AZURE_STORAGE_ACCOUNT_NAME": "",
            "ENV_ZENML_PREVENT_PIPELINE_EXECUTION": "True",
        }

        experiment = Experiment(workspace=workspace, name=pipeline_name)
        compute_target = ComputeTarget(
            workspace=workspace, name=self.compute_target_name
        )

        run_config = ScriptRunConfig(
            source_directory=str(Repository().root),
            compute_target=compute_target,
            environment=environment,
            command=entrypoint_command,
        )

        run = experiment.submit(config=run_config)
        run.display_name = run_name
        run.wait_for_completion(show_output=True)
