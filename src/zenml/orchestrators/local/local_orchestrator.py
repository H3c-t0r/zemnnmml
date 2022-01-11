# New License:
#  Copyright (c) ZenML GmbH 2021. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at:
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
#  or implied. See the License for the specific language governing
#  permissions and limitations under the License.

from typing import TYPE_CHECKING, Any

from zenml.enums import OrchestratorFlavor
from zenml.orchestrators import BaseOrchestrator
from zenml.orchestrators.local.local_dag_runner import LocalDagRunner
from zenml.orchestrators.utils import create_tfx_pipeline

if TYPE_CHECKING:
    from zenml.new_core import Stack
    from zenml.pipelines.base_pipeline import BasePipeline


class LocalOrchestrator(BaseOrchestrator):
    """Orchestrator responsible for running pipelines locally."""

    supports_local_execution = True
    supports_remote_execution = False

    @property
    def flavor(self) -> OrchestratorFlavor:
        return OrchestratorFlavor.LOCAL

    def run_pipeline(
        self, pipeline: "BasePipeline", stack: "Stack", run_name: str
    ) -> Any:
        """Runs a pipeline locally."""
        tfx_pipeline = create_tfx_pipeline(pipeline, stack=stack)
        LocalDagRunner().run(tfx_pipeline, run_name)
