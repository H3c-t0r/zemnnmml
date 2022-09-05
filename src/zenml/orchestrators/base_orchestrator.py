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

# The `run_step()` method of this file is a modified version of the local dag
# runner implementation of tfx
"""Base orchestrator class."""
import hashlib
import json
import os
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Optional, Sequence, Type

from google.protobuf import json_format
from tfx.dsl.compiler.constants import PIPELINE_RUN_ID_PARAMETER_NAME
from tfx.dsl.io.fileio import NotFoundError
from tfx.orchestration import metadata
from tfx.orchestration.local import runner_utils
from tfx.orchestration.portable import (
    data_types,
    launcher,
    outputs_utils,
    runtime_parameter_utils,
)
from tfx.orchestration.portable.base_executor_operator import (
    BaseExecutorOperator,
)
from tfx.orchestration.portable.python_executor_operator import (
    PythonExecutorOperator,
)
from tfx.proto.orchestration import executable_spec_pb2
from tfx.proto.orchestration.pipeline_pb2 import ContextSpec
from tfx.proto.orchestration.pipeline_pb2 import Pipeline as Pb2Pipeline
from tfx.proto.orchestration.pipeline_pb2 import PipelineNode

from zenml.artifacts.base_artifact import BaseArtifact
from zenml.constants import (
    MLMD_CONTEXT_PIPELINE_CONFIG_PROPERTY_NAME,
    MLMD_CONTEXT_STACK_PROPERTY_NAME,
    MLMD_CONTEXT_STEP_CONFIG_PROPERTY_NAME,
    ZENML_MLMD_CONTEXT_TYPE,
)
from zenml.enums import StackComponentType
from zenml.io import fileio
from zenml.logger import get_logger
from zenml.orchestrators.utils import get_cache_status
from zenml.repository import Repository
from zenml.stack import StackComponent
from zenml.utils import source_utils, string_utils

if TYPE_CHECKING:
    from zenml.config.pipeline_configurations import PipelineDeployment
    from zenml.config.step_configurations import Step, StepConfiguration
    from zenml.stack import Stack

logger = get_logger(__name__)


### TFX PATCH
# The following code patches a function in tfx which leads to an OSError on
# Windows.
def _patched_remove_stateful_working_dir(stateful_working_dir: str) -> None:
    """Deletes the stateful working directory if it exists.

    Args:
        stateful_working_dir: Stateful working directory to delete.
    """
    # The original implementation uses
    # `os.path.abspath(os.path.join(stateful_working_dir, os.pardir))` to
    # compute the parent directory that needs to be deleted. This however
    # doesn't work with our artifact store paths (e.g. s3://my-artifact-store)
    # which would get converted to something like this:
    # /path/to/current/working/directory/s3:/my-artifact-store. In order to
    # avoid that we use `os.path.dirname` instead as the stateful working dir
    # should already be an absolute path anyway.
    stateful_working_dir = os.path.dirname(stateful_working_dir)
    try:
        fileio.rmtree(stateful_working_dir)
    except NotFoundError:
        logger.debug(
            "Unable to find stateful working directory '%s'.",
            stateful_working_dir,
        )


assert hasattr(
    outputs_utils, "remove_stateful_working_dir"
), "Unable to find tfx function."
setattr(
    outputs_utils,
    "remove_stateful_working_dir",
    _patched_remove_stateful_working_dir,
)
### END OF TFX PATCH


class BaseOrchestrator(StackComponent, ABC):
    """Base class for all orchestrators.

    In order to implement an orchestrator you will need to subclass from this
    class.

    How it works:
    -------------
    The `run()` method is the entrypoint that is executed when the
    pipeline's run method is called within the user code
    (`pipeline_instance.run()`).

    This method will take the ZenML Pipeline instance and prepare it for
    eventual execution. To do this the following steps are taken:

    * The underlying protobuf pipeline is created.

    * Within the `_configure_node_context()` method the pipeline
    requirements, stack and runtime configuration is added to the step
    context

    * The `_get_sorted_steps()` method then generates a sorted list of
    steps which will later be used to directly execute these steps in order,
    or to easily build a dag

    * After these initial steps comes the most crucial one. Within the
    `prepare_or_run_pipeline()` method each orchestrator will have its own
    implementation that dictates the pipeline orchestration. In the simplest
    case this method will iterate through all steps and execute them one by
    one. In other cases this method will build and deploy an intermediate
    representation of the pipeline (e.g an airflow dag or a kubeflow
    pipelines yaml) to be executed within the orchestrators environment.

    Building your own:
    ------------------
    In order to build your own orchestrator, all you need to do is subclass
    from this class and implement your own `prepare_or_run_pipeline()`
    method. Overwriting other methods is NOT recommended but possible.
    See the docstring of the `prepare_or_run_pipeline()` method to find out
    details of what needs to be implemented within it.
    """

    # Class Configuration
    TYPE: ClassVar[StackComponentType] = StackComponentType.ORCHESTRATOR
    _active_run_config: Optional["PipelineDeployment"] = None
    _active_pb2_pipeline: Optional[Pb2Pipeline] = None

    @abstractmethod
    def prepare_or_run_pipeline(
        self,
        pipeline: "PipelineDeployment",
        stack: "Stack",
    ) -> Any:
        """This method needs to be implemented by the respective orchestrator.

        Depending on the type of orchestrator you'll have to perform slightly
        different operations.

        Simple Case:
        ------------
        The Steps are run directly from within the same environment in which
        the orchestrator code is executed. In this case you will need to
        deal with implementation-specific runtime configurations (like the
        schedule) and then iterate through each step and finally call
        `self.run_step()` to execute each step.

        Advanced Case:
        --------------
        Most orchestrators will not run the steps directly. Instead, they
        build some intermediate representation of the pipeline that is then
        used to create and run the pipeline and its steps on the target
        environment. For such orchestrators this method will have to build
        this representation and either deploy it directly or return it.

        Regardless of the implementation details, the orchestrator will need
        to a way to trigger each step in the target environment. For this
        the `run_step()` method should be used.

        In case the orchestrator is using docker containers for orchestration
        of each step, the `zenml.entrypoints.step_entrypoint` module can be
        used as a generalized entrypoint that sets up all the necessary
        prerequisites, parses input parameters and finally executes the step
        using the `run_step()`method.

        Args:
            pipeline: Representation of the pipeline to run.
            stack: The stack the pipeline will run on.

        Returns:
            The optional return value from this method will be returned by the
            `pipeline_instance.run()` call when someone is running a pipeline.
        """

    def _prepare_run(self, pipeline_run: "PipelineDeployment") -> None:
        """Prepares a run.

        Args:
            pipeline_run: The run to prepare.
        """
        self._active_run_config = pipeline_run

        pb2_pipeline = Pb2Pipeline()
        pb2_pipeline_json = string_utils.b64_decode(
            self._active_run_config.proto_pipeline
        )
        json_format.Parse(pb2_pipeline_json, pb2_pipeline)
        self._active_pb2_pipeline = pb2_pipeline

    def _cleanup_run(self) -> None:
        """Cleans up the active run."""
        self._active_run_config = None
        self._active_pb2_pipeline = None

    def run(self, pipeline_run: "PipelineDeployment", stack: "Stack") -> Any:
        """Runs a pipeline on a stack.

        Args:
            pipeline_run: The pipeline to run.
            stack: The stack on which to run the pipeline.

        Returns:
            Orchestrator-specific return value.
        """
        self._prepare_run(pipeline_run=pipeline_run)

        result = self.prepare_or_run_pipeline(
            pipeline=pipeline_run, stack=stack
        )

        self._cleanup_run()

        return result

    @staticmethod
    def _ensure_artifact_classes_loaded(
        step_configuration: "StepConfiguration",
    ) -> None:
        """Ensures that all artifact classes for a step are loaded.

        Args:
            step_configuration: A step configuration.
        """
        artifact_class_sources = set(
            input_.artifact_source
            for input_ in step_configuration.inputs.values()
        ) | set(
            output.artifact_source
            for output in step_configuration.outputs.values()
        )

        for source in artifact_class_sources:
            # Tfx depends on these classes being loaded so it can detect the
            # correct artifact class
            source_utils.validate_source_class(
                source, expected_class=BaseArtifact
            )

    def run_step(
        self, step: "Step", run_name: Optional[str] = None
    ) -> Optional[data_types.ExecutionInfo]:
        """This sets up a component launcher and executes the given step.

        Args:
            step: The step to be executed
            run_name: The unique run name

        Returns:
            The execution info of the step.
        """
        assert self._active_run_config
        assert self._active_pb2_pipeline

        self._ensure_artifact_classes_loaded(step.config)

        step_name = step.config.name
        pb2_pipeline = self._active_pb2_pipeline

        run_name = run_name or self._active_run_config.run_name
        # Substitute the runtime parameter to be a concrete run_id, it is
        # important for this to be unique for each run.
        runtime_parameter_utils.substitute_runtime_parameter(
            pb2_pipeline,
            {PIPELINE_RUN_ID_PARAMETER_NAME: run_name},
        )

        # Extract the deployment_configs and use it to access the executor and
        # custom driver spec
        deployment_config = runner_utils.extract_local_deployment_config(
            pb2_pipeline
        )
        executor_spec = runner_utils.extract_executor_spec(
            deployment_config, step_name
        )
        custom_driver_spec = runner_utils.extract_custom_driver_spec(
            deployment_config, step_name
        )

        # At this point the active metadata store is queried for the
        # metadata_connection
        stack = Repository().active_stack
        metadata_connection = metadata.Metadata(
            stack.metadata_store.get_tfx_metadata_config()
        )
        executor_operator = self._get_executor_operator(
            step_operator=step.config.step_operator
        )
        custom_executor_operators = {
            executable_spec_pb2.PythonClassExecutableSpec: executor_operator
        }

        # The protobuf node for the current step is loaded here.
        pipeline_node = self._get_node_with_step_name(step_name)

        self._add_mlmd_contexts(
            pipeline_node=pipeline_node,
            deployment=self._active_run_config,
            stack=stack,
        )

        component_launcher = launcher.Launcher(
            pipeline_node=pipeline_node,
            mlmd_connection=metadata_connection,
            pipeline_info=pb2_pipeline.pipeline_info,
            pipeline_runtime_spec=pb2_pipeline.runtime_spec,
            executor_spec=executor_spec,
            custom_driver_spec=custom_driver_spec,
            custom_executor_operators=custom_executor_operators,
        )

        # If a step operator is used, the current environment will not be the
        # one executing the step function code and therefore we don't need to
        # run any preparation
        if step.config.step_operator:
            execution_info = self._execute_step(component_launcher)
        else:
            stack.prepare_step_run(step=step)
            try:
                execution_info = self._execute_step(component_launcher)
            finally:
                stack.cleanup_step_run(step=step)

        return execution_info

    @staticmethod
    def _execute_step(
        tfx_launcher: launcher.Launcher,
    ) -> Optional[data_types.ExecutionInfo]:
        """Executes a tfx component.

        Args:
            tfx_launcher: A tfx launcher to execute the component.

        Returns:
            Optional execution info returned by the launcher.
        """
        pipeline_step_name = tfx_launcher._pipeline_node.node_info.id
        start_time = time.time()
        logger.info(f"Step `{pipeline_step_name}` has started.")
        execution_info = tfx_launcher.launch()
        if execution_info and get_cache_status(execution_info):
            logger.info(f"Using cached version of `{pipeline_step_name}`.")

        run_duration = time.time() - start_time
        logger.info(
            f"Step `{pipeline_step_name}` has finished in "
            f"{string_utils.get_human_readable_time(run_duration)}."
        )
        return execution_info

    @staticmethod
    def _get_executor_operator(
        step_operator: Optional[str],
    ) -> Type[BaseExecutorOperator]:
        """Gets the TFX executor operator for the given step operator.

        Args:
            step_operator: The optional step operator used to run a step.

        Returns:
            The executor operator for the given step operator.
        """
        if step_operator:
            from zenml.step_operators.step_executor_operator import (
                StepExecutorOperator,
            )

            return StepExecutorOperator
        else:
            return PythonExecutorOperator

    @staticmethod
    def _add_pipeline_node_context(
        pipeline_node: PipelineNode,
        type_: str,
        name: str,
        properties: Dict[str, str],
    ) -> None:
        """Adds a new context to a TFX protobuf pipeline node.

        Args:
            pipeline_node: A tfx protobuf pipeline node
            type_: The type name for the context to be added
            name: Unique key for the context
            properties: dictionary of strings as properties of the context
        """
        context: ContextSpec = pipeline_node.contexts.contexts.add()
        context.type.name = type_
        context.name.field_value.string_value = name
        for key, value in properties.items():
            c_property = context.properties[key]
            c_property.field_value.string_value = value

    def _add_mlmd_contexts(
        self,
        pipeline_node: PipelineNode,
        deployment: "PipelineDeployment",
        stack: "Stack",
    ) -> None:
        """Adds context to each pipeline node of a pb2_pipeline.

        This attaches important contexts to the nodes; namely
        pipeline.docker_configuration, stack information and the runtime
        configuration.

        Args:
            pipeline_node: The pipeline node to which the contexts should be
                added.
            deployment: The pipeline deployment to store in the contexts.
            stack: The stack the pipeline will run on.
        """
        stack_json = json.dumps(stack.dict(), sort_keys=True)
        pipeline_config = deployment.json(
            exclude={"run_name", "proto_pipeline", "steps"}, sort_keys=True
        )

        context_properties = {
            MLMD_CONTEXT_STACK_PROPERTY_NAME: stack_json,
            MLMD_CONTEXT_PIPELINE_CONFIG_PROPERTY_NAME: pipeline_config,
        }

        step = self._get_step_for_node(
            pipeline_node, steps=list(deployment.steps.values())
        )

        step_context_properties = context_properties.copy()
        step_context_properties[
            MLMD_CONTEXT_STEP_CONFIG_PROPERTY_NAME
        ] = step.json(sort_keys=True)

        properties_json = json.dumps(step_context_properties, sort_keys=True)
        context_name = hashlib.md5(properties_json.encode()).hexdigest()

        self._add_pipeline_node_context(
            pipeline_node,
            type_=ZENML_MLMD_CONTEXT_TYPE,
            name=context_name,
            properties=step_context_properties,
        )

    @staticmethod
    def _get_step_for_node(
        node: PipelineNode, steps: Sequence["Step"]
    ) -> "Step":
        """Gets the ZenML step for a pipeline node.

        Args:
            node: The node for which to get the step.
            steps: Sequence of steps.

        Raises:
            RuntimeError: If no step for the node was found.

        Returns:
            The step for the given node.
        """
        step_name = node.node_info.id
        try:
            return next(step for step in steps if step.config.name == step_name)
        except StopIteration:
            raise RuntimeError(f"Unable to find step with name '{step_name}'.")

    @staticmethod
    def requires_resources_in_orchestration_environment(
        step: "Step",
    ) -> bool:
        """Checks if the orchestrator should run this step on special resources.

        Args:
            step: The step that will be checked.

        Returns:
            True if the step requires special resources in the orchestration
            environment, False otherwise.
        """
        # If the step requires custom resources and doesn't run with a step
        # operator, it would need these requirements in the orchestrator
        # environment
        if step.config.step_operator:
            return False

        return not step.config.resource_configuration.empty

    def _get_node_with_step_name(self, step_name: str) -> PipelineNode:
        """Given the name of a step, return the node with that name from the pb2_pipeline.

        Args:
            step_name: Name of the step

        Returns:
            PipelineNode instance

        Raises:
            KeyError: If the step name is not found in the pipeline.
        """
        assert self._active_pb2_pipeline

        for node in self._active_pb2_pipeline.nodes:
            if (
                node.WhichOneof("node") == "pipeline_node"
                and node.pipeline_node.node_info.id == step_name
            ):
                return node.pipeline_node

        raise KeyError(
            f"Step {step_name} not found in Pipeline "
            f"{self._active_pb2_pipeline.pipeline_info.id}"
        )
