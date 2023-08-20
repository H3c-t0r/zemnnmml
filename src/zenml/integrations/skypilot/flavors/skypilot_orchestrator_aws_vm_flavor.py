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
"""Skypilot orchestrator AWS flavor."""

from typing import TYPE_CHECKING, Optional, Type

from zenml.integrations.skypilot import SKYPILOT_AWS_ORCHESTRATOR_FLAVOR
from zenml.integrations.skypilot.flavors.skypilot_orchestrator_base_vm_config import (
    SkypilotBaseOrchestratorConfig,
    SkypilotBaseOrchestratorSettings,
)
from zenml.logger import get_logger
from zenml.orchestrators import BaseOrchestratorConfig, BaseOrchestratorFlavor

if TYPE_CHECKING:
    from zenml.integrations.skypilot.orchestrators import (
        SkypilotAWSOrchestrator,
    )


logger = get_logger(__name__)


class SkypilotAWSOrchestratorSettings(SkypilotBaseOrchestratorSettings):
    """Skypilot orchestrator settings.

    Attributes:

    """


class SkypilotAWSOrchestratorConfig(  # type: ignore[misc] # https://github.com/pydantic/pydantic/issues/4173
    SkypilotBaseOrchestratorConfig, SkypilotAWSOrchestratorSettings
):
    """Skypilot orchestrator config."""

    @property
    def is_local(self) -> bool:
        """Checks if this stack component is running locally.

        This designation is used to determine if the stack component can be
        shared with other users or if it is only usable on the local host.

        Returns:
            True if this config is for a local component, False otherwise.
        """
        return False


class SkypilotAWSOrchestratorFlavor(BaseOrchestratorFlavor):
    """Flavor for the Skypilot orchestrator."""

    @property
    def name(self) -> str:
        """Name of the orchestrator flavor.

        Returns:
            Name of the orchestrator flavor.
        """
        return SKYPILOT_AWS_ORCHESTRATOR_FLAVOR

    @property
    def docs_url(self) -> Optional[str]:
        """A url to point at docs explaining this flavor.

        Returns:
            A flavor docs url.
        """
        return self.generate_default_docs_url()

    @property
    def sdk_docs_url(self) -> Optional[str]:
        """A url to point at SDK docs explaining this flavor.

        Returns:
            A flavor SDK docs url.
        """
        return self.generate_default_sdk_docs_url()

    @property
    def logo_url(self) -> str:
        """A url to represent the flavor in the dashboard.

        Returns:
            The flavor logo.
        """
        return "https://public-flavor-logos.s3.eu-central-1.amazonaws.com/container_registry/aws.png"

    @property
    def config_class(self) -> Type[BaseOrchestratorConfig]:
        """Config class for the base orchestrator flavor.

        Returns:
            The config class.
        """
        return SkypilotAWSOrchestratorConfig

    @property
    def implementation_class(self) -> Type["SkypilotAWSOrchestrator"]:
        """Implementation class for this flavor.

        Returns:
            Implementation class for this flavor.
        """
        return SkypilotAWSOrchestrator
