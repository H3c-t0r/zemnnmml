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
"""Base Step for ZenML."""

import collections
import inspect
import json
import random
from abc import abstractmethod
from collections import defaultdict
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Counter,
    Dict,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from pydantic import ValidationError
from tfx.dsl.component.experimental.decorators import _SimpleComponent
from tfx.types.channel import Channel

from zenml.artifacts.base_artifact import BaseArtifact
from zenml.artifacts.type_registry import type_registry
from zenml.config.constants import RESOURCE_CONFIGURATION_KEY
from zenml.config.step_configurations import (
    ArtifactConfiguration,
    PartialArtifactConfiguration,
    PartialStepConfiguration,
    StepConfiguration,
    StepConfigurationUpdate,
)
from zenml.exceptions import MissingStepParameterError, StepInterfaceError
from zenml.logger import get_logger
from zenml.materializers.base_materializer import BaseMaterializer
from zenml.materializers.default_materializer_registry import (
    default_materializer_registry,
)
from zenml.steps.base_step_config import BaseStepConfig
from zenml.steps.step_context import StepContext
from zenml.steps.utils import (
    INSTANCE_CONFIGURATION,
    INTERNAL_EXECUTION_PARAMETER_PREFIX,
    PARAM_CREATED_BY_FUNCTIONAL_API,
    PARAM_CUSTOM_STEP_OPERATOR,
    PARAM_ENABLE_CACHE,
    PARAM_EXPERIMENT_TRACKER,
    PARAM_EXTRA_OPTIONS,
    PARAM_OUTPUT_ARTIFACTS,
    PARAM_OUTPUT_MATERIALIZERS,
    PARAM_OUTPUT_TYPES,
    PARAM_PIPELINE_PARAMETER_NAME,
    PARAM_RESOURCE_CONFIGURATION,
    PARAM_RUNTIME_OPTIONS,
    PARAM_STEP_OPERATOR,
    create_component_class,
    parse_return_type_annotations,
    resolve_type_annotation,
)
from zenml.utils import (
    dict_utils,
    pydantic_utils,
    runtime_options_utils,
    source_utils,
)

logger = get_logger(__name__)
if TYPE_CHECKING:
    from zenml.config.base_runtime_options import RuntimeOptionsOrDict

    ArtifactClassOrStr = Union[str, Type["BaseArtifact"]]
    MaterializerClassOrStr = Union[str, Type["BaseMaterializer"]]


class BaseStepMeta(type):
    """Metaclass for `BaseStep`.

    Checks whether everything passed in:
    * Has a matching materializer,
    * Is a subclass of the Config class,
    * Is typed correctly.
    """

    def __new__(
        mcs, name: str, bases: Tuple[Type[Any], ...], dct: Dict[str, Any]
    ) -> "BaseStepMeta":
        """Set up a new class with a qualified spec.

        Args:
            name: The name of the class.
            bases: The base classes of the class.
            dct: The attributes of the class.

        Returns:
            The new class.

        Raises:
            StepInterfaceError: When unable to create the step.
        """
        dct.setdefault(INSTANCE_CONFIGURATION, {})
        cls = cast(Type["BaseStep"], super().__new__(mcs, name, bases, dct))

        cls.INPUT_SIGNATURE = {}
        cls.OUTPUT_SIGNATURE = {}
        cls.CONFIG_PARAMETER_NAME = None
        cls.CONFIG_CLASS = None
        cls.CONTEXT_PARAMETER_NAME = None

        # Get the signature of the step function
        step_function_signature = inspect.getfullargspec(
            inspect.unwrap(cls.entrypoint)
        )

        if bases:
            # We're not creating the abstract `BaseStep` class
            # but a concrete implementation. Make sure the step function
            # signature does not contain variable *args or **kwargs
            variable_arguments = None
            if step_function_signature.varargs:
                variable_arguments = f"*{step_function_signature.varargs}"
            elif step_function_signature.varkw:
                variable_arguments = f"**{step_function_signature.varkw}"

            if variable_arguments:
                raise StepInterfaceError(
                    f"Unable to create step '{name}' with variable arguments "
                    f"'{variable_arguments}'. Please make sure your step "
                    f"functions are defined with a fixed amount of arguments."
                )

        step_function_args = (
            step_function_signature.args + step_function_signature.kwonlyargs
        )

        # Remove 'self' from the signature if it exists
        if step_function_args and step_function_args[0] == "self":
            step_function_args.pop(0)

        # Verify the input arguments of the step function
        for arg in step_function_args:
            arg_type = step_function_signature.annotations.get(arg, None)
            arg_type = resolve_type_annotation(arg_type)

            if not arg_type:
                raise StepInterfaceError(
                    f"Missing type annotation for argument '{arg}' when "
                    f"trying to create step '{name}'. Please make sure to "
                    f"include type annotations for all your step inputs "
                    f"and outputs."
                )

            if issubclass(arg_type, BaseStepConfig):
                # Raise an error if we already found a config in the signature
                if cls.CONFIG_CLASS is not None:
                    raise StepInterfaceError(
                        f"Found multiple configuration arguments "
                        f"('{cls.CONFIG_PARAMETER_NAME}' and '{arg}') when "
                        f"trying to create step '{name}'. Please make sure to "
                        f"only have one `BaseStepConfig` subclass as input "
                        f"argument for a step."
                    )
                cls.CONFIG_PARAMETER_NAME = arg
                cls.CONFIG_CLASS = arg_type

            elif issubclass(arg_type, StepContext):
                if cls.CONTEXT_PARAMETER_NAME is not None:
                    raise StepInterfaceError(
                        f"Found multiple context arguments "
                        f"('{cls.CONTEXT_PARAMETER_NAME}' and '{arg}') when "
                        f"trying to create step '{name}'. Please make sure to "
                        f"only have one `StepContext` as input "
                        f"argument for a step."
                    )
                cls.CONTEXT_PARAMETER_NAME = arg
            else:
                # Can't do any check for existing materializers right now
                # as they might get be defined later, so we simply store the
                # argument name and type for later use.
                cls.INPUT_SIGNATURE.update({arg: arg_type})

        # Parse the returns of the step function
        if "return" not in step_function_signature.annotations:
            raise StepInterfaceError(
                "Missing return type annotation when trying to create step "
                f"'{name}'. Please make sure to include type annotations for "
                "all your step inputs and outputs. If your step returns "
                "nothing, please annotate it with `-> None`."
            )
        cls.OUTPUT_SIGNATURE = parse_return_type_annotations(
            step_function_signature.annotations,
        )

        # Raise an exception if input and output names of a step overlap as
        # tfx requires them to be unique
        # TODO [ENG-155]: Can we prefix inputs and outputs to avoid this
        #  restriction?
        counter: Counter[str] = collections.Counter()
        counter.update(list(cls.INPUT_SIGNATURE))
        counter.update(list(cls.OUTPUT_SIGNATURE))
        if cls.CONFIG_CLASS:
            counter.update(list(cls.CONFIG_CLASS.__fields__.keys()))

        shared_keys = {k for k in counter.elements() if counter[k] > 1}
        if shared_keys:
            raise StepInterfaceError(
                f"The following keys are overlapping in the input, output and "
                f"config parameter names of step '{name}': {shared_keys}. "
                f"Please make sure that your input, output and config "
                f"parameter names are unique."
            )

        return cls


T = TypeVar("T", bound="BaseStep")


class BaseStep(metaclass=BaseStepMeta):
    """Abstract base class for all ZenML steps.

    Attributes:
        name: The name of this step.
        pipeline_parameter_name: The name of the pipeline parameter for which
            this step was passed as an argument.
        enable_cache: A boolean indicating if caching is enabled for this step.
        custom_step_operator: Optional name of a custom step operator to use
            for this step.
        requires_context: A boolean indicating if this step requires a
            `StepContext` object during execution.
    """

    INPUT_SIGNATURE: ClassVar[Dict[str, Type[Any]]] = None  # type: ignore[assignment] # noqa
    OUTPUT_SIGNATURE: ClassVar[Dict[str, Type[Any]]] = None  # type: ignore[assignment] # noqa
    CONFIG_PARAMETER_NAME: ClassVar[Optional[str]] = None
    CONFIG_CLASS: ClassVar[Optional[Type[BaseStepConfig]]] = None
    CONTEXT_PARAMETER_NAME: ClassVar[Optional[str]] = None

    INSTANCE_CONFIGURATION: Dict[str, Any] = {}

    class _OutputArtifact(NamedTuple):
        """Internal step output artifact."""

        channel: Channel
        materializer_source: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes a step.

        Args:
            *args: Positional arguments passed to the step.
            **kwargs: Keyword arguments passed to the step.
        """
        name = self.__class__.__name__
        self.pipeline_parameter_name: Optional[str] = None
        self._component: Optional[_SimpleComponent] = None
        self._has_been_called = False
        self._upstream_steps: Set[str] = set()

        kwargs.update(self.INSTANCE_CONFIGURATION)

        # This value is only used in `BaseStep.__created_by_functional_api()`
        kwargs.pop(PARAM_CREATED_BY_FUNCTIONAL_API, None)

        requires_context = bool(self.CONTEXT_PARAMETER_NAME)
        enable_cache = kwargs.pop(PARAM_ENABLE_CACHE, None)
        if enable_cache is None:
            if requires_context:
                # Using the StepContext inside a step provides access to
                # external resources which might influence the step execution.
                # We therefore disable caching unless it is explicitly enabled
                enable_cache = False
                logger.debug(
                    "Step '%s': Step context required and caching not "
                    "explicitly enabled.",
                    name,
                )
            else:
                # Default to cache enabled if not explicitly set
                enable_cache = True

        logger.debug(
            "Step '%s': Caching %s.",
            name,
            "enabled" if enable_cache else "disabled",
        )

        self._configuration = PartialStepConfiguration(
            name=name,
            enable_cache=enable_cache,
        )
        self._apply_class_configuration(kwargs)
        self._verify_and_apply_init_config(*args, **kwargs)

    @abstractmethod
    def entrypoint(self, *args: Any, **kwargs: Any) -> Any:
        """Abstract method for core step logic.

        Args:
            *args: Positional arguments passed to the step.
            **kwargs: Keyword arguments passed to the step.

        Returns:
            The output of the step.
        """

    @classmethod
    def _created_by_functional_api(cls) -> bool:
        """Returns if the step class was created by the functional API.

        Returns:
            `True` if the class was created by the functional API,
            `False` otherwise.
        """
        return cls.INSTANCE_CONFIGURATION.get(
            PARAM_CREATED_BY_FUNCTIONAL_API, False
        )

    @property
    def upstream_steps(self) -> Set[str]:
        """Names of the upstream steps of this step.

        This property will only contain the full set of upstream steps once
        it's parent pipeline `connect(...)` method was called.

        Returns:
            Set of upstream step names.
        """
        return self._upstream_steps

    def after(self, step: "BaseStep") -> None:
        """Adds an upstream step to the this step.

        Calling this method makes sure this step only starts running once the
        given step has successfully finished executing.

        **Note**: This can only be called inside the pipeline connect function
        which is decorated with the `@pipeline` decorator. Any calls outside
        this function will be ignored.

        Example:
        The following pipeline will run its steps sequentially in the following
        order: step_2 -> step_1 -> step_3

        ```python
        @pipeline
        def example_pipeline(step_1, step_2, step_3):
            step_1.after(step_2)
            step_3(step_1(), step_2())
        ```

        Args:
            step: A step which should finish executing before this step is
                started.
        """
        self._upstream_steps.add(step.name)

    @property
    def _internal_execution_parameters(self) -> Dict[str, Any]:
        """Internal ZenML execution parameters for this step.

        Returns:
            A dictionary containing the ZenML internal execution parameters
        """
        parameters = {
            PARAM_PIPELINE_PARAMETER_NAME: self.pipeline_parameter_name,
        }

        if self.enable_cache:
            # Caching is enabled so we compute a hash of the step function code
            # and materializers to catch changes in the step behavior

            # If the step was defined using the functional api, only track
            # changes to the entrypoint function. Otherwise track changes to
            # the entire step class.
            source_object = (
                self.entrypoint
                if self._created_by_functional_api()
                else self.__class__
            )
            parameters["step_source"] = source_utils.get_hashed_source(
                source_object
            )

            for name, output in self.configuration.outputs.items():
                if output.materializer_source:
                    key = f"{name}_materializer_source"
                    materializer_class = source_utils.load_source_path_class(
                        output.materializer_source
                    )
                    parameters[key] = source_utils.get_hashed_source(
                        materializer_class
                    )
        else:
            # Add a random string to the execution properties to disable caching
            random_string = f"{random.getrandbits(128):032x}"
            parameters["disable_cache"] = random_string

        return {
            INTERNAL_EXECUTION_PARAMETER_PREFIX + key: value
            for key, value in parameters.items()
        }

    def _apply_class_configuration(self, options: Dict[str, Any]) -> None:
        """Applies the configurations specified on the step class.

        Args:
            options: Class configurations.

        Raises:
            RuntimeError: If multiple values are provided for the step operator,
                resource configuration or output artifacts of the step.
        """
        step_operator = options.pop(PARAM_STEP_OPERATOR, None)
        deprecated_step_operator = options.pop(PARAM_CUSTOM_STEP_OPERATOR, None)
        if deprecated_step_operator and step_operator:
            raise RuntimeError(
                "Step operator was specified twice using the "
                f"`{PARAM_CUSTOM_STEP_OPERATOR}` and `{PARAM_STEP_OPERATOR}` "
                "parameters of the @step decorator. Remove the value specified "
                f"using the `{PARAM_CUSTOM_STEP_OPERATOR}` parameter to solve "
                "this issue."
            )
        elif deprecated_step_operator:
            logger.warning(
                "Specifying the step operator using the `%s` parameter on the "
                "@step decorator is deprecated. Use the `%s` parameter "
                "instead: `@step(%s='<STEP_OPERATOR_NAME>')`",
                PARAM_CUSTOM_STEP_OPERATOR,
                PARAM_STEP_OPERATOR,
                PARAM_STEP_OPERATOR,
            )
            step_operator = deprecated_step_operator

        runtime_options = options.pop(PARAM_RUNTIME_OPTIONS, None) or {}

        resource_config = runtime_options.get(RESOURCE_CONFIGURATION_KEY, None)
        deprecated_resource_config = options.pop(
            PARAM_RESOURCE_CONFIGURATION, None
        )
        if deprecated_resource_config and resource_config:
            raise RuntimeError(
                "Resource configuration was specified twice using the "
                f"`{PARAM_RESOURCE_CONFIGURATION}` and "
                f"`{PARAM_RUNTIME_OPTIONS}` parameters of the @step decorator. "
                "Remove the value specified using the "
                f"`{PARAM_RESOURCE_CONFIGURATION}` parameter to solve this "
                "issue."
            )
        elif deprecated_resource_config:
            logger.warning(
                "Specifying the resource configuration using the `%s` "
                "parameter on the @step decorator is deprecated. Use the `%s` "
                "parameter instead: "
                "`@step(%s={'resources': ResourceConfiguration(...)})`",
                PARAM_RESOURCE_CONFIGURATION,
                PARAM_RUNTIME_OPTIONS,
                PARAM_RUNTIME_OPTIONS,
            )
            runtime_options[
                RESOURCE_CONFIGURATION_KEY
            ] = deprecated_resource_config

        output_materializers = options.pop(PARAM_OUTPUT_MATERIALIZERS, None)

        output_artifacts = options.pop(PARAM_OUTPUT_ARTIFACTS, None)
        deprecated_output_artifacts = options.pop(PARAM_OUTPUT_TYPES, None)

        if deprecated_output_artifacts and output_artifacts:
            raise RuntimeError(
                "Output artifacts were specified twice using the "
                f"`{PARAM_OUTPUT_TYPES}` and `{PARAM_OUTPUT_ARTIFACTS}` "
                "parameters of the @step decorator. Remove the value specified "
                f"using the `{PARAM_OUTPUT_TYPES}` parameter to solve this "
                "issue."
            )
        elif deprecated_output_artifacts:
            logger.warning(
                "Specifying the output artifacts using the `%s` parameter on "
                "the @step decorator is deprecated. Use the `%s` parameter "
                "instead: `@step(%s={...})`",
                PARAM_OUTPUT_TYPES,
                PARAM_OUTPUT_ARTIFACTS,
                PARAM_OUTPUT_ARTIFACTS,
            )
            output_artifacts = deprecated_output_artifacts

        extra = options.pop(PARAM_EXTRA_OPTIONS, None)
        experiment_tracker = options.pop(PARAM_EXPERIMENT_TRACKER, None)

        self.configure(
            experiment_tracker=experiment_tracker,
            step_operator=step_operator,
            output_artifacts=output_artifacts,
            output_materializers=output_materializers,
            runtime_options=runtime_options,
            extra=extra,
        )

    def _verify_and_apply_init_config(self, *args: Any, **kwargs: Any) -> None:
        """Verifies the initialization args and kwargs of this step.

        This method makes sure that there is only a config object passed at
        initialization and that it was passed using the correct name and
        type specified in the step declaration.
        If the correct config object was found, additionally saves the
        config parameters to `self.PARAM_SPEC`.

        Args:
            *args: The args passed to the init method of this step.
            **kwargs: The kwargs passed to the init method of this step.

        Raises:
            StepInterfaceError: If there are too many arguments or arguments
                with a wrong name/type.
        """
        maximum_arg_count = 1 if self.CONFIG_CLASS else 0
        arg_count = len(args) + len(kwargs)
        if arg_count > maximum_arg_count:
            raise StepInterfaceError(
                f"Too many arguments ({arg_count}, expected: "
                f"{maximum_arg_count}) passed when creating a "
                f"'{self.name}' step."
            )

        if self.CONFIG_PARAMETER_NAME and self.CONFIG_CLASS:
            if args:
                config = args[0]
            elif kwargs:
                key, config = kwargs.popitem()

                if key != self.CONFIG_PARAMETER_NAME:
                    raise StepInterfaceError(
                        f"Unknown keyword argument '{key}' when creating a "
                        f"'{self.name}' step, only expected a single "
                        f"argument with key '{self.CONFIG_PARAMETER_NAME}'."
                    )
            else:
                # This step requires configuration parameters but no config
                # object was passed as an argument. The parameters might be
                # set via default values in the config class or in a
                # configuration file, so we continue for now and verify
                # that all parameters are set before running the step
                return

            if not isinstance(config, self.CONFIG_CLASS):
                raise StepInterfaceError(
                    f"`{config}` object passed when creating a "
                    f"'{self.name}' step is not a "
                    f"`{self.CONFIG_CLASS.__name__}` instance."
                )

            self.configure(function_parameters=config)

    def _validate_input_artifacts(
        self, *artifacts: _OutputArtifact, **kw_artifacts: _OutputArtifact
    ) -> Dict[str, _OutputArtifact]:
        """Verifies and prepares the input artifacts for running this step.

        Args:
            *artifacts: Positional input artifacts passed to
                the __call__ method.
            **kw_artifacts: Keyword input artifacts passed to
                the __call__ method.

        Returns:
            Dictionary containing both the positional and keyword input
            artifacts.

        Raises:
            StepInterfaceError: If there are too many or too few artifacts.
        """
        input_artifact_keys = list(self.INPUT_SIGNATURE.keys())
        if len(artifacts) > len(input_artifact_keys):
            raise StepInterfaceError(
                f"Too many input artifacts for step '{self.name}'. "
                f"This step expects {len(input_artifact_keys)} artifact(s) "
                f"but got {len(artifacts) + len(kw_artifacts)}."
            )

        combined_artifacts = {}

        for i, artifact in enumerate(artifacts):
            if not isinstance(artifact, BaseStep._OutputArtifact):
                raise StepInterfaceError(
                    f"Wrong argument type (`{type(artifact)}`) for positional "
                    f"argument {i} of step '{self.name}'. Only outputs "
                    f"from previous steps can be used as arguments when "
                    f"connecting steps."
                )

            key = input_artifact_keys[i]
            combined_artifacts[key] = artifact

        for key, artifact in kw_artifacts.items():
            if key in combined_artifacts:
                # an artifact for this key was already set by
                # the positional input artifacts
                raise StepInterfaceError(
                    f"Unexpected keyword argument '{key}' for step "
                    f"'{self.name}'. An artifact for this key was "
                    f"already passed as a positional argument."
                )

            if not isinstance(artifact, BaseStep._OutputArtifact):
                raise StepInterfaceError(
                    f"Wrong argument type (`{type(artifact)}`) for argument "
                    f"'{key}' of step '{self.name}'. Only outputs from "
                    f"previous steps can be used as arguments when "
                    f"connecting steps."
                )

            combined_artifacts[key] = artifact

        # check if there are any missing or unexpected artifacts
        expected_artifacts = set(self.INPUT_SIGNATURE.keys())
        actual_artifacts = set(combined_artifacts.keys())
        missing_artifacts = expected_artifacts - actual_artifacts
        unexpected_artifacts = actual_artifacts - expected_artifacts

        if missing_artifacts:
            raise StepInterfaceError(
                f"Missing input artifact(s) for step "
                f"'{self.name}': {missing_artifacts}."
            )

        if unexpected_artifacts:
            raise StepInterfaceError(
                f"Unexpected input artifact(s) for step "
                f"'{self.name}': {unexpected_artifacts}. This step "
                f"only requires the following artifacts: {expected_artifacts}."
            )

        return combined_artifacts

    def __call__(
        self, *artifacts: _OutputArtifact, **kw_artifacts: _OutputArtifact
    ) -> Union[_OutputArtifact, List[_OutputArtifact]]:
        """Generates a component when called.

        Args:
            *artifacts: Positional input artifacts passed to
                the __call__ method.
            **kw_artifacts: Keyword input artifacts passed to
                the __call__ method.

        Returns:
            A single output artifact or a list of output artifacts.

        Raises:
            StepInterfaceError: If the step has already been called.
        """
        if self._has_been_called:
            raise StepInterfaceError(
                f"Step {self.name} has already been called. A ZenML step "
                f"instance can only be called once per pipeline run."
            )
        self._has_been_called = True

        # Prepare the input artifacts and spec
        input_artifacts = self._validate_input_artifacts(
            *artifacts, **kw_artifacts
        )
        input_channels = {
            name: artifact.channel for name, artifact in input_artifacts.items()
        }
        for input_ in input_artifacts.values():
            self._upstream_steps.add(input_.channel.producer_component_id)

        config = self._finalize_configuration(input_artifacts=input_artifacts)

        execution_parameters = {
            **self.configuration.function_parameters,
            **self._internal_execution_parameters,
        }

        # Convert execution parameter values to strings
        try:
            execution_parameters = {
                k: json.dumps(v) for k, v in execution_parameters.items()
            }
        except TypeError as e:
            raise StepInterfaceError(
                f"Failed to serialize execution parameters for step "
                f"'{self.name}'. Please make sure to only use "
                f"json serializable parameter values."
            ) from e

        component_class = create_component_class(step=self)
        self._component = component_class(
            **input_channels, **execution_parameters
        )

        # Resolve the returns in the right order.
        returns = []
        for key in self.OUTPUT_SIGNATURE:
            materializer_source = config.outputs[key].materializer_source
            output_artifact = BaseStep._OutputArtifact(
                channel=cast(Channel, self.component.outputs[key]),
                materializer_source=materializer_source,
            )
            returns.append(output_artifact)

        # If its one return we just return the one channel not as a list
        if len(returns) == 1:
            return returns[0]
        else:
            return returns

    @property
    def component(self) -> _SimpleComponent:
        """Returns a TFX component.

        Returns:
            A TFX component.

        Raises:
            StepInterfaceError: If you are trying to access the step component
                before creating it.
        """
        if not self._component:
            raise StepInterfaceError(
                "Trying to access the step component "
                "before creating it via calling the step."
            )
        return self._component

    def with_return_materializers(
        self: T,
        materializers: Union[
            Type[BaseMaterializer], Dict[str, Type[BaseMaterializer]]
        ],
    ) -> T:
        """DEPRECATED: Register materializers for step outputs.

        If a single materializer is passed, it will be used for all step
        outputs. Otherwise, the dictionary keys specify the output names
        for which the materializers will be used.

        Args:
            materializers: The materializers for the outputs of this step.

        Returns:
            The step that this method was called on.
        """
        logger.warning(
            "The `with_return_materializers(...)` method is deprecated. "
            "Use `step.configure(output_materializers=...)` instead."
        )

        self.configure(output_materializers=materializers)
        return self

    @property
    def name(self) -> str:
        """The name of the step.

        Returns:
            The name of the step.
        """
        return self.configuration.name

    @property
    def enable_cache(self) -> bool:
        """If caching is enabled for the step.

        Returns:
            If caching is enabled for the step.
        """
        return self.configuration.enable_cache

    @property
    def configuration(self) -> PartialStepConfiguration:
        """The configuration of the step.

        Returns:
            The configuration of the step.
        """
        return self._configuration

    def configure(
        self,
        enable_cache: Optional[bool] = None,
        experiment_tracker: Optional[str] = None,
        step_operator: Optional[str] = None,
        function_parameters: Optional[
            Union[BaseStepConfig, Dict[str, Any]]
        ] = None,
        output_materializers: Optional[
            Union[
                "MaterializerClassOrStr", Mapping[str, "MaterializerClassOrStr"]
            ]
        ] = None,
        output_artifacts: Optional[Mapping[str, "ArtifactClassOrStr"]] = None,
        runtime_options: Optional[Mapping[str, "RuntimeOptionsOrDict"]] = None,
        extra: Optional[Dict[str, Any]] = None,
        merge: bool = True,
    ) -> None:
        """Configures the step.

        Configuration merging example:
        * `merge==True`:
            step.configure(extra={"key1": 1})
            step.configure(extra={"key2": 2}, merge=True)
            step.configuration.extra # {"key1": 1, "key2": 2}
        * `merge==False`:
            step.configure(extra={"key1": 1})
            step.configure(extra={"key2": 2}, merge=False)
            step.configuration.extra # {"key2": 2}

        Args:
            enable_cache: If caching should be enabled for this step.
            experiment_tracker: The experiment tracker to use for this step.
            step_operator: The step operator to use for this step.
            function_parameters: Function parameters for this step
            output_materializers: Output materializers for this step. If
                given as a dict, the keys must be a subset of the outputs of
                this step. If a single value (type or string) is given, the
                materializer will be used for all outputs.
            output_artifacts: Output artifacts for this step.
            runtime_options: Runtime options for this step.
            extra: Extra configurations for this step.
            merge: If `True`, will merge the given dictionary configurations
                like `function_parameters` and `runtime_options` with existing
                configurations. If `False` the given configurations will
                overwrite all existing ones. See the general description of this
                method for an example.

        Raises:
            StepInterfaceError: If a materializer or artifact for a non-existent
                output name are configured.
        """

        def _resolve_if_necessary(value: Union[str, Type[Any]]) -> str:
            return (
                value
                if isinstance(value, str)
                else source_utils.resolve_class(value)
            )

        outputs: Dict[str, Dict[str, str]] = defaultdict(dict)
        allowed_output_names = set(self.OUTPUT_SIGNATURE)

        if output_materializers:
            if not isinstance(output_materializers, Mapping):
                # string of materializer class to be used for all outputs
                source = _resolve_if_necessary(output_materializers)
                output_materializers = {
                    output_name: source for output_name in allowed_output_names
                }

            for output_name, materializer in output_materializers.items():
                if output_name not in allowed_output_names:
                    raise StepInterfaceError(
                        f"Got unexpected materializers for non-existent "
                        f"output '{output_name}' in step '{self.name}'. "
                        f"Only materializers for the outputs "
                        f"{allowed_output_names} of this step can"
                        f" be registered."
                    )

                source = _resolve_if_necessary(materializer)
                outputs[output_name]["materializer_source"] = source

        if output_artifacts:
            for output_name, artifact in output_artifacts.items():
                if output_name not in allowed_output_names:
                    raise StepInterfaceError(
                        f"Got unexpected artifact for non-existent "
                        f"output '{output_name}' in step '{self.name}'. "
                        f"Only artifacts for the outputs "
                        f"{allowed_output_names} of this step can"
                        f" be registered."
                    )

                source = _resolve_if_necessary(artifact)
                outputs[output_name]["artifact_source"] = source

        values = dict_utils.remove_none_values(
            {
                "enable_cache": enable_cache,
                "experiment_tracker": experiment_tracker,
                "step_operator": step_operator,
                "function_parameters": function_parameters,
                "runtime_options": runtime_options,
                "outputs": outputs or None,
                "extra": extra,
            }
        )
        config = StepConfigurationUpdate(**values)
        self._apply_configuration(config, merge=merge)

    def _apply_configuration(
        self,
        config: StepConfigurationUpdate,
        merge: bool = True,
    ) -> None:
        """Applies an update to the step configuration.

        Args:
            config: The configuration update.
            merge: Whether to merge the updates with the existing configuration
                or not. See the `BaseStep.configure(...)` method for a detailed
                explanation.
        """
        self._validate_configuration(config)

        self._configuration = pydantic_utils.update_model(
            self._configuration, update=config, recursive=merge
        )

        logger.debug("Updated step configuration:")
        logger.debug(self._configuration)

    def _validate_configuration(self, config: StepConfigurationUpdate) -> None:
        """Validates a configuration update.

        Args:
            config: The configuration update to validate.
        """
        runtime_options_utils.validate_runtime_option_keys(
            list(config.runtime_options)
        )
        self._validate_function_parameters(
            parameters=config.function_parameters
        )
        self._validate_outputs(outputs=config.outputs)

    def _validate_function_parameters(self, parameters: Dict[str, Any]) -> None:
        """Validates step function parameters.

        Args:
            parameters: The parameters to validate.

        Raises:
            StepInterfaceError: If the step requires no function parameters or
                invalid function parameters were given.
        """
        if not parameters:
            # No parameters set (yet), defer validation to a later point
            return

        if not self.CONFIG_CLASS:
            raise StepInterfaceError(
                f"Function parameters configured for step {self.name} which "
                "does not accept any function parameters."
            )

        try:
            self.CONFIG_CLASS(**parameters)
        except ValidationError:
            raise StepInterfaceError("Failed to validate function parameters.")

    def _validate_inputs(
        self, inputs: Dict[str, ArtifactConfiguration]
    ) -> None:
        """Validates the step input configuration.

        Args:
            inputs: The configured step inputs.

        Raises:
            StepInterfaceError: If an input for a non-existent name is
                configured of an input artifact source does not resolve to a
                BaseArtifact subclass.
        """
        allowed_input_names = set(self.INPUT_SIGNATURE)
        for input_name, input_ in inputs.items():
            if input_name not in allowed_input_names:
                raise StepInterfaceError(
                    f"Got unexpected artifact for non-existent "
                    f"input '{input_name}' in step '{self.name}'. "
                    f"Only artifacts for the inputs "
                    f"{allowed_input_names} of this step can"
                    f" be registered."
                )

            if not source_utils.validate_source_class(
                input_.artifact_source, expected_class=BaseArtifact
            ):
                raise StepInterfaceError(
                    f"Artifact source `{input_.artifact_source}` "
                    f"for input '{input_name}' of step '{self.name}' "
                    "does not resolve to a `BaseArtifact` subclass."
                )

    def _validate_outputs(
        self, outputs: Dict[str, PartialArtifactConfiguration]
    ) -> None:
        """Validates the step output configuration.

        Args:
            outputs: The configured step outputs.

        Raises:
            StepInterfaceError: If an output for a non-existent name is
                configured of an output artifact/materializer source does not
                resolve to the correct class.
        """
        allowed_output_names = set(self.OUTPUT_SIGNATURE)
        for output_name, output in outputs.items():
            if output_name not in allowed_output_names:
                raise StepInterfaceError(
                    f"Found explicit artifact type for unrecognized output "
                    f"'{output_name}' in step '{self.name}'. Output "
                    f"artifact types can only be specified for the outputs "
                    f"of this step: {set(self.OUTPUT_SIGNATURE)}."
                )

            if output.materializer_source:
                if not source_utils.validate_source_class(
                    output.materializer_source, expected_class=BaseMaterializer
                ):
                    raise StepInterfaceError(
                        f"Materializer source `{output.materializer_source}` "
                        f"for output '{output_name}' of step '{self.name}' "
                        "does not resolve to a  `BaseMaterializer` subclass."
                    )

            if output.artifact_source:
                try:
                    artifact_class: Type[
                        BaseArtifact
                    ] = source_utils.load_and_validate_class(
                        output.artifact_source, expected_class=BaseArtifact
                    )
                except TypeError:
                    raise StepInterfaceError(
                        f"Artifact source `{output.artifact_source}` "
                        f"for output '{output_name}' of step '{self.name}' "
                        "does not point to a  `BaseArtifact` subclass."
                    )
                # TODO: Can we get rid of this check? Why do we limit artifact
                # types to registered materializers?
                output_type = self.OUTPUT_SIGNATURE[output_name]
                allowed_artifact_types = set(
                    type_registry.get_artifact_type(output_type)
                )

                if artifact_class not in allowed_artifact_types:
                    raise StepInterfaceError(
                        f"Artifact type `{artifact_class}` for output "
                        f"'{output_name}' of step '{self.name}' is not an "
                        f"allowed artifact type for the defined output type "
                        f"`{output_type}`. Allowed artifact types: "
                        f"{allowed_artifact_types}. If you want to extend the "
                        f"allowed artifact types, implement a custom "
                        f"`BaseMaterializer` subclass and set its "
                        f"`ASSOCIATED_ARTIFACT_TYPES` and `ASSOCIATED_TYPES` "
                        f"accordingly."
                    )

    def _finalize_configuration(
        self, input_artifacts: Dict[str, _OutputArtifact]
    ) -> StepConfiguration:
        """Finalizes the configuration after the step was called.

        Once the step was called, we know the outputs of previous steps
        and that no additional user configurations will be made. That means
        we can now collect the remaining artifact and materializer types
        as well as check for the completeness of the step function parameters.

        Args:
            input_artifacts: The input artifacts of this step.

        Returns:
            The finalized step configuration.

        Raises:
            StepInterfaceError: If an output does not have an explicit
                materializer assigned to it and there is no default
                materializer registered for the output type.
        """
        outputs: Dict[str, Dict[str, str]] = defaultdict(dict)

        for output_name, output_class in self.OUTPUT_SIGNATURE.items():
            output = self._configuration.outputs.get(
                output_name, PartialArtifactConfiguration()
            )

            if not output.artifact_source:
                artifact_class = type_registry.get_artifact_type(output_class)[
                    0
                ]
                outputs[output_name][
                    "artifact_source"
                ] = source_utils.resolve_class(artifact_class)

            if not output.materializer_source:
                if default_materializer_registry.is_registered(output_class):
                    materializer_class = default_materializer_registry[
                        output_class
                    ]
                else:
                    raise StepInterfaceError(
                        f"Unable to find materializer for output "
                        f"'{output_name}' of type `{output_class}` in step "
                        f"'{self.name}'. Please make sure to either "
                        f"explicitly set a materializer for step outputs "
                        f"using `step.with_return_materializers(...)` or "
                        f"registering a default materializer for specific "
                        f"types by subclassing `BaseMaterializer` and setting "
                        f"its `ASSOCIATED_TYPES` class variable.",
                        url="https://docs.zenml.io/developer-guide/advanced-usage/materializer",
                    )
                outputs[output_name][
                    "materializer_source"
                ] = source_utils.resolve_class(materializer_class)

        function_parameters = self._finalize_function_parameters()
        values = dict_utils.remove_none_values(
            {
                "outputs": outputs or None,
                "function_parameters": function_parameters,
            }
        )
        config = StepConfigurationUpdate(**values)
        self._apply_configuration(config)

        inputs = {}
        for input_name, artifact in input_artifacts.items():
            artifact_source = source_utils.resolve_class(artifact.channel.type)
            inputs[input_name] = ArtifactConfiguration(
                artifact_source=artifact_source,
                materializer_source=artifact.materializer_source,
            )
        self._validate_inputs(inputs)

        self._configuration = self._configuration.copy(
            update={"inputs": inputs}
        )

        complete_configuration = StepConfiguration.parse_obj(
            self._configuration
        )
        return complete_configuration

    def _finalize_function_parameters(self) -> Dict[str, Any]:
        """Verifies and prepares the config parameters for running this step.

        When the step requires config parameters, this method:
            - checks if config parameters were set via a config object or file
            - tries to set missing config parameters from default values of the
              config class

        Returns:
            Values for the previously unconfigured function parameters.

        Raises:
            MissingStepParameterError: If no value could be found for one or
                more config parameters.
        """
        if not self.CONFIG_CLASS:
            return {}

        # we need to store a value for all config keys inside the
        # metadata store to make sure caching works as expected
        missing_keys = []
        values = {}
        for name, field in self.CONFIG_CLASS.__fields__.items():
            if name in self.configuration.function_parameters:
                # a value for this parameter has been set already
                continue

            if field.required:
                # this field has no default value set and therefore needs
                # to be passed via an initialized config object
                missing_keys.append(name)
            else:
                # use default value from the pydantic config class
                values[name] = field.default

        if missing_keys:
            raise MissingStepParameterError(
                self.name, missing_keys, self.CONFIG_CLASS
            )

        return values
