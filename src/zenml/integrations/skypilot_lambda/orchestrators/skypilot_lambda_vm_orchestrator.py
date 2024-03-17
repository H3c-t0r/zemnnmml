#  Copyright (c) ZenML GmbH 2024. All Rights Reserved.
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
"""Implementation of the a Skypilot based Lambda VM orchestrator."""

import os
from typing import TYPE_CHECKING, Optional, Type, cast

import sky

from zenml.integrations.skypilot.orchestrators.skypilot_base_vm_orchestrator import (
    SkypilotBaseOrchestrator,
)
from zenml.integrations.skypilot_lambda.flavors.skypilot_orchestrator_lambda_vm_flavor import (
    SkypilotLambdaOrchestratorConfig,
    SkypilotLambdaOrchestratorSettings,
)
from zenml.logger import get_logger

if TYPE_CHECKING:
    from zenml.config.base_settings import BaseSettings

logger = get_logger(__name__)

ENV_LAMBDA_API_KEY = "LAMBDA_API_KEY"


class SkypilotLambdaOrchestrator(SkypilotBaseOrchestrator):
    """Orchestrator responsible for running pipelines remotely in a VM on Lambda.

    This orchestrator does not support running on a schedule.
    """

    DEFAULT_INSTANCE_TYPE: str = "NVIDIA A100 80GB PCIe"

    @property
    def cloud(self) -> sky.clouds.Cloud:
        """The type of sky cloud to use.

        Returns:
            A `sky.clouds.Cloud` instance.
        """
        return sky.clouds.Lambda()

    @property
    def config(self) -> SkypilotLambdaOrchestratorConfig:
        """Returns the `SkypilotLambdaOrchestratorConfig` config.

        Returns:
            The configuration.
        """
        return cast(SkypilotLambdaOrchestratorConfig, self._config)

    @property
    def settings_class(self) -> Optional[Type["BaseSettings"]]:
        """Settings class for the Skypilot orchestrator.

        Returns:
            The settings class.
        """
        return SkypilotLambdaOrchestratorSettings

    def prepare_environment_variable(self, set: bool = True) -> None:
        """Set up Environment variables that are required for the orchestrator.

        Args:
            set: Whether to set the environment variables or not.

        Raises:
            ValueError: If no service connector is found.
        """
        if not self.config.api_key:
            raise ValueError("No token found in the orchestrator config.")
        if set:
            os.environ[ENV_LAMBDA_API_KEY] = self.config.api_key
        else:
            os.environ.pop(ENV_LAMBDA_API_KEY, None)
