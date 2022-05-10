# Copyright 2019 Google LLC. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#  Copyright (c) ZenML GmbH 2021. All Rights Reserved.
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
"""The below code is copied from the TFX source repo with minor changes.
All credits go to the TFX team for the core implementation"""

import collections
import copy
import json
import sys
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    MutableMapping,
    Optional,
    Set,
    Type,
)

from kfp import compiler, dsl
from tfx.dsl.compiler import compiler as tfx_compiler
from tfx.dsl.components.base import base_node
from tfx.orchestration import data_types
from tfx.orchestration.config import pipeline_config
from tfx.orchestration.launcher import (
    base_component_launcher,
    in_process_component_launcher,
    kubernetes_component_launcher,
)
from tfx.orchestration.pipeline import Pipeline as TfxPipeline
from tfx.proto.orchestration.pipeline_pb2 import IntermediateDeploymentConfig
from tfx.proto.orchestration.pipeline_pb2 import Pipeline as Pb2Pipeline
from tfx.proto.orchestration.pipeline_pb2 import PipelineNode
from tfx.utils import telemetry_utils

from zenml.enums import MetadataContextTypes
from zenml.integrations.kubeflow.orchestrators.kubeflow_component import (
    KubeflowComponent,
)
from zenml.logger import get_logger
from zenml.orchestrators import context_utils
from zenml.orchestrators.utils import create_tfx_pipeline
from zenml.utils.source_utils import get_module_source_from_module

if TYPE_CHECKING:
    from zenml.pipelines.base_pipeline import BasePipeline
    from zenml.runtime_configuration import RuntimeConfiguration
    from zenml.stack import Stack

logger = get_logger(__name__)


def get_default_pod_labels() -> Dict[str, str]:
    """Returns the default pod label dict for Kubeflow."""
    # KFP default transformers add pod env:
    # https://github.com/kubeflow/pipelines/blob/0.1.32/sdk/python/kfp/compiler/_default_transformers.py
    result = {"add-pod-env": "true", telemetry_utils.LABEL_KFP_SDK_ENV: "tfx"}
    return result


class KubeflowDagRunnerConfig(pipeline_config.PipelineConfig):
    """Runtime configuration parameters specific to execution on Kubeflow."""

    def __init__(
        self,
        image: str,
        pipeline_operator_funcs: Optional[List[OpFunc]] = None,
        supported_launcher_classes: Optional[
            List[Type[base_component_launcher.BaseComponentLauncher]]
        ] = None,
        **kwargs: Any
    ):
        """Creates a KubeflowDagRunnerConfig object.
        The user can use pipeline_operator_funcs to apply modifications to
        ContainerOps used in the pipeline. For example, to ensure the pipeline
        steps mount a GCP secret, and a Persistent Volume, one can create config
        object like so:
          from kfp import gcp, onprem
          mount_secret_op = gcp.use_secret('my-secret-name)
          mount_volume_op = onprem.mount_pvc(
            "my-persistent-volume-claim",
            "my-volume-name",
            "/mnt/volume-mount-path")
          config = KubeflowDagRunnerConfig(
            pipeline_operator_funcs=[mount_secret_op, mount_volume_op]
          )
        Args:
          image: The docker image to use in the pipeline.
          pipeline_operator_funcs: A list of ContainerOp modifying functions
            that will be applied to every container step in the pipeline.
          supported_launcher_classes: A list of component launcher classes that
            are supported by the current pipeline. List sequence determines the
            order in which launchers are chosen for each component being run.
          **kwargs: keyword args for PipelineConfig.
        """
        supported_launcher_classes = supported_launcher_classes or [
            in_process_component_launcher.InProcessComponentLauncher,
            kubernetes_component_launcher.KubernetesComponentLauncher,
        ]
        super().__init__(
            supported_launcher_classes=supported_launcher_classes, **kwargs
        )
        self.pipeline_operator_funcs = (
            pipeline_operator_funcs or get_default_pipeline_operator_funcs()
        )
        self.image = image


class KubeflowDagRunner:
    """Kubeflow Pipelines runner. Constructs a pipeline definition YAML file
    based on the TFX logical pipeline.
    """

    def __init__(
        self,
        config: KubeflowDagRunnerConfig,
        output_path: str,
        pod_labels_to_attach: Optional[Dict[str, str]] = None,
    ):
        """Initializes KubeflowDagRunner for compiling a Kubeflow Pipeline.
        Args:
          config: A KubeflowDagRunnerConfig object to specify runtime
            configuration when running the pipeline under Kubeflow.
          output_path: Path where the pipeline definition file will be stored.
          pod_labels_to_attach: Optional set of pod labels to attach to GKE pod
            spun up for this pipeline. Default to the 3 labels:
            1. add-pod-env: true,
            2. pipeline SDK type,
            3. pipeline unique ID,
            where 2 and 3 are instrumentation of usage tracking.
        """
        self._config = config or pipeline_config.PipelineConfig()
        self._kubeflow_config = config
        self._output_path = output_path
        self._compiler = compiler.Compiler()
        self._tfx_compiler = tfx_compiler.Compiler()
        self._params: List[dsl.PipelineParam] = []
        self._params_by_component_id: Dict[
            str, List[data_types.RuntimeParameter]
        ] = collections.defaultdict(list)
        self._deduped_parameter_names: Set[str] = set()
        self._pod_labels_to_attach = (
            pod_labels_to_attach or get_default_pod_labels()
        )

    @property
    def config(self) -> pipeline_config.PipelineConfig:
        """The config property"""
        return self._config

    def _construct_pipeline_graph(
        self,
        pipeline: "BasePipeline",
        tfx_pipeline: TfxPipeline,
        stack: "Stack",
        runtime_configuration: "RuntimeConfiguration",
    ) -> None:
        """Constructs a Kubeflow Pipeline graph.
        Args:
          pipeline: ZenML pipeline instance.
          tfx_pipeline: The logical TFX pipeline to base the construction on.
          stack: The ZenML stack that the pipeline is running on
          runtime_configuration: The runtime configuration
        """
        component_to_kfp_op: Dict[base_node.BaseNode, dsl.ContainerOp] = {}
        tfx_ir: Pb2Pipeline = self._generate_tfx_ir(tfx_pipeline)

        for node in tfx_ir.nodes:
            pipeline_node: PipelineNode = node.pipeline_node

            # Add the stack as context to each pipeline node:
            context_utils.add_context_to_node(
                pipeline_node,
                type_=MetadataContextTypes.STACK.value,
                name=str(hash(json.dumps(stack.dict(), sort_keys=True))),
                properties=stack.dict(),
            )

            # Add all pydantic objects from runtime_configuration to the
            # context
            context_utils.add_runtime_configuration_to_node(
                pipeline_node, runtime_configuration
            )

            # Add pipeline requirements as a context
            requirements = " ".join(sorted(pipeline.requirements))
            context_utils.add_context_to_node(
                pipeline_node,
                type_=MetadataContextTypes.PIPELINE_REQUIREMENTS.value,
                name=str(hash(requirements)),
                properties={"pipeline_requirements": requirements},
            )

        # Assumption: There is a partial ordering of components in the list,
        # i.e. if component A depends on component B and C, then A appears
        # after B and C in the list.
        for component in tfx_pipeline.components:
            # Keep track of the set of upstream dsl.ContainerOps for this
            # component.
            depends_on = set()

            for upstream_component in component.upstream_nodes:
                depends_on.add(component_to_kfp_op[upstream_component])

            # remove the extra pipeline node information
            tfx_node_ir = self._dehydrate_tfx_ir(tfx_ir, component.id)

            main_module = get_module_source_from_module(sys.modules["__main__"])

            original_step_module, _ = component.component_type.rsplit(".", 1)

            if original_step_module == "__main__":
                step_module = main_module
            else:
                step_module = original_step_module

            kfp_component = KubeflowComponent(
                main_module=main_module,
                step_module=step_module,
                original_step_module=original_step_module,
                step_function_name=component.id,
                component=component,
                depends_on=depends_on,
                image=self._kubeflow_config.image,
                pod_labels_to_attach=self._pod_labels_to_attach,
                tfx_ir=tfx_node_ir,
                runtime_parameters=self._params_by_component_id[component.id],
            )

            for operator in self._kubeflow_config.pipeline_operator_funcs:
                kfp_component.container_op.apply(operator)

            component_to_kfp_op[component] = kfp_component.container_op

    def _del_unused_field(
        self, node_id: str, message_dict: MutableMapping[str, Any]
    ) -> None:
        """Remove fields that are not used by the pipeline."""
        for item in list(message_dict.keys()):
            if item != node_id:
                del message_dict[item]

    def _dehydrate_tfx_ir(
        self, original_pipeline: Pb2Pipeline, node_id: str
    ) -> Pb2Pipeline:
        """Dehydrate the TFX IR to remove unused fields."""
        pipeline = copy.deepcopy(original_pipeline)
        for node in pipeline.nodes:
            if (
                node.WhichOneof("node") == "pipeline_node"
                and node.pipeline_node.node_info.id == node_id
            ):
                del pipeline.nodes[:]
                pipeline.nodes.extend([node])
                break

        deployment_config = IntermediateDeploymentConfig()
        pipeline.deployment_config.Unpack(deployment_config)
        self._del_unused_field(node_id, deployment_config.executor_specs)
        self._del_unused_field(node_id, deployment_config.custom_driver_specs)
        self._del_unused_field(
            node_id, deployment_config.node_level_platform_configs
        )
        pipeline.deployment_config.Pack(deployment_config)
        return pipeline

    def _generate_tfx_ir(self, pipeline: TfxPipeline) -> Pb2Pipeline:
        """Generate the TFX IR from the logical TFX pipeline."""
        result = self._tfx_compiler.compile(pipeline)
        return result

    def run(
        self,
        pipeline: "BasePipeline",
        stack: "Stack",
        runtime_configuration: "RuntimeConfiguration",
    ) -> None:
        """Compiles and outputs a Kubeflow Pipeline YAML definition file.
        Args:
          pipeline: The logical TFX pipeline to use when building the Kubeflow
            pipeline.
          stack: The ZenML stack that the pipeline is running on.
          runtime_configuration: The runtime configuration.
        """
        tfx_pipeline = create_tfx_pipeline(pipeline, stack=stack)

        def _construct_pipeline() -> None:
            """Creates Kubeflow ContainerOps for each TFX component
            encountered in the pipeline definition."""
            self._construct_pipeline_graph(
                pipeline, tfx_pipeline, stack, runtime_configuration
            )

        # Create workflow spec and write out to package.
        self._compiler._create_and_write_workflow(
            # pylint: disable=protected-access
            pipeline_func=_construct_pipeline,
            pipeline_name=tfx_pipeline.pipeline_info.pipeline_name,
            params_list=self._params,
            package_path=self._output_path,
        )
        logger.info(
            "Finished writing kubeflow pipeline definition file '%s'.",
            self._output_path,
        )
