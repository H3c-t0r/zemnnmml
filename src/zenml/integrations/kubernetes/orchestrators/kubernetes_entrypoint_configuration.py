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

from typing import TYPE_CHECKING, Any, List, Set

from zenml.entrypoints import StepEntrypointConfiguration

if TYPE_CHECKING:
    from zenml.steps import BaseStep

KUBERNETES_JOB_ID_OPTION = "kubernetes_job_id"


class KubernetesEntrypointConfiguration(StepEntrypointConfiguration):
    """Entrypoint configuration for running steps on Kubernertes."""

    @classmethod
    def get_custom_entrypoint_options(cls) -> Set[str]:
        """Kubernertes specific entrypoint options.

        The argument `KUBERNETES_JOB_ID_OPTION` allows to specify the job id of
        the Vertex AI Pipeline and get it in the execution of the step, via the
        `get_run_name`method.
        """
        return {KUBERNETES_JOB_ID_OPTION}

    @classmethod
    def get_custom_entrypoint_arguments(
        cls, step: BaseStep, *args: Any, **kwargs: Any
    ) -> List[str]:
        """Sets the value for the `KUBERNETES_JOB_ID_OPTION` argument."""
        return [
            f"--{KUBERNETES_JOB_ID_OPTION}",
            kwargs[KUBERNETES_JOB_ID_OPTION],
        ]

    def get_run_name(self, pipeline_name: str) -> str:
        """Returns the Kubernertes pipeline run name."""
        job_id: str = self.entrypoint_args[KUBERNETES_JOB_ID_OPTION]
        return job_id
