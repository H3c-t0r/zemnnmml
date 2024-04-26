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
"""Initialization of the langchain integration."""

from zenml.integrations.constants import LANGCHAIN
from zenml.integrations.integration import Integration

from zenml.logger import get_logger

logger = get_logger(__name__)


class LangchainIntegration(Integration):
    """Definition of langchain integration for ZenML."""

    NAME = LANGCHAIN
    REQUIREMENTS = ["langchain>=0.1.0", "langchain-openai"]

    @classmethod
    def activate(cls) -> None:
        """Activates the integration."""
        from zenml.integrations.langchain import materializers  # noqa


LangchainIntegration.check_installation()
