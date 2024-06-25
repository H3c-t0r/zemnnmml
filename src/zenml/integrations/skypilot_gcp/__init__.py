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
"""Initialization of the Skypilot GCP integration for ZenML.

The Skypilot integration sub-module powers an alternative to the local
orchestrator for a remote orchestration of ZenML pipelines on VMs.
"""
import sys
from typing import List, Optional, Type

from zenml.integrations.constants import (
    SKYPILOT_GCP,
)
from zenml.integrations.integration import Integration
from zenml.stack import Flavor

SKYPILOT_GCP_ORCHESTRATOR_FLAVOR = "vm_gcp"


class SkypilotGCPIntegration(Integration):
    """Definition of Skypilot (GCP) Integration for ZenML."""

    NAME = SKYPILOT_GCP
    REQUIREMENTS = []
    APT_PACKAGES = ["openssh-client", "rsync"]

    @classmethod
    def get_requirements(cls, target_os: Optional[str] = None) -> List[str]:
        """Defines platform specific requirements for the integration.

        Args:
            target_os: The target operating system.

        Returns:
            A list of requirements.
        """
        requirements = []
        # TODO: simplify once skypilot supports 3.12
        if sys.version_info.minor != 12:
            requirements = ["skypilot[gcp]<=0.5.0"]

        return requirements

    @classmethod
    def flavors(cls) -> List[Type[Flavor]]:
        """Declare the stack component flavors for the Skypilot GCP integration.

        Returns:
            List of stack component flavors for this integration.
        """
        from zenml.integrations.skypilot_gcp.flavors import (
            SkypilotGCPOrchestratorFlavor,
        )

        return [SkypilotGCPOrchestratorFlavor]

SkypilotGCPIntegration.check_installation()
