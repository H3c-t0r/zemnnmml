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
"""Initialization of the Skypilot integration for ZenML.

The Skypilot integration sub-module powers an alternative to the local
orchestrator for a remote orchestration of ZenML pipelines.
You can enable it by registering the Skypilot orchestrator with
the CLI tool.
"""
from typing import List, Type

from zenml.integrations.constants import (
    SKYPILOT_AWS,
    SKYPILOT_GCP,
    SKYPILOT_AZURE,
)
from zenml.integrations.integration import Integration
from zenml.stack import Flavor

SKYPILOT_AWS_ORCHESTRATOR_FLAVOR = "vm_aws"
SKYPILOT_GCP_ORCHESTRATOR_FLAVOR = "vm_gcp"
SKYPILOT_AZURE_ORCHESTRATOR_FLAVOR = "vm_azure"


class SkypilotAWSIntegration(Integration):
    """Definition of Skypilot AWS Integration for ZenML."""

    NAME = SKYPILOT_AWS
    REQUIREMENTS = ["skypilot[aws]"]

    @classmethod
    def flavors(cls) -> List[Type[Flavor]]:
        """Declare the stack component flavors for the Skypilot AWS integration.

        Returns:
            List of stack component flavors for this integration.
        """
        from zenml.integrations.skypilot.flavors import (
            SkypilotAWSOrchestratorFlavor,
        )

        return [SkypilotAWSOrchestratorFlavor]


class SkypilotGCPIntegration(Integration):
    """Definition of Skypilot Integration for ZenML."""

    NAME = SKYPILOT_GCP
    REQUIREMENTS = ["skypilot[gcp]"]

    @classmethod
    def flavors(cls) -> List[Type[Flavor]]:
        """Declare the stack component flavors for the Skypilot GCP integration.

        Returns:
            List of stack component flavors for this integration.
        """
        from zenml.integrations.skypilot.flavors import (
            SkypilotGCPOrchestratorFlavor,
        )

        return [SkypilotGCPOrchestratorFlavor]


class SkypilotAzureIntegration(Integration):
    """Definition of Skypilot Integration for ZenML."""

    NAME = SKYPILOT_AZURE
    REQUIREMENTS = ["skypilot[azure]"]

    @classmethod
    def flavors(cls) -> List[Type[Flavor]]:
        """Declare the stack component flavors for the Skypilot Azure integration.

        Returns:
            List of stack component flavors for this integration.
        """
        from zenml.integrations.skypilot.flavors import (
            SkypilotAzureOrchestratorFlavor,
        )

        return [SkypilotAzureOrchestratorFlavor]


SkypilotAWSIntegration.check_installation()
SkypilotGCPIntegration.check_installation()
SkypilotAzureIntegration.check_installation()
