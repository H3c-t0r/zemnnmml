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
"""Step decorator function."""

from types import FunctionType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Mapping,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
    overload,
)

from zenml.steps import BaseStep

if TYPE_CHECKING:
    from zenml.config.base_settings import SettingsOrDict
    from zenml.config.source import Source
    from zenml.materializers.base_materializer import BaseMaterializer

    MaterializerClassOrSource = Union[str, "Source", Type["BaseMaterializer"]]
    HookSpecification = Union[str, "Source", FunctionType]
    OutputMaterializersSpecification = Union[
        "MaterializerClassOrSource",
        Sequence["MaterializerClassOrSource"],
        Mapping[str, "MaterializerClassOrSource"],
        Mapping[str, Sequence["MaterializerClassOrSource"]],
    ]


F = TypeVar("F", bound=Callable[..., Any])


class _DecoratedStep(BaseStep):
    def __init__(self, entrypoint: F, **kwargs: Any) -> None:
        self.entrypoint = entrypoint
        super().__init__(**kwargs)

    @property
    def source_object(self) -> Any:
        """The source object of this step.

        Returns:
            The source object of this step.
        """
        return self.entrypoint

    def resolve(self) -> "Source":
        """Resolves the step.

        Returns:
            The step source.
        """
        from zenml.utils import source_utils

        return source_utils.resolve(self.entrypoint, skip_validation=True)


@overload
def step(_func: F) -> BaseStep:
    ...


@overload
def step(
    *,
    name: Optional[str] = None,
    enable_cache: Optional[bool] = None,
    enable_artifact_metadata: Optional[bool] = None,
    enable_artifact_visualization: Optional[bool] = None,
    experiment_tracker: Optional[str] = None,
    step_operator: Optional[str] = None,
    output_materializers: Optional["OutputMaterializersSpecification"] = None,
    settings: Optional[Dict[str, "SettingsOrDict"]] = None,
    extra: Optional[Dict[str, Any]] = None,
    on_failure: Optional["HookSpecification"] = None,
    on_success: Optional["HookSpecification"] = None,
) -> Callable[[F], BaseStep]:
    ...


def step(
    _func: Optional[F] = None,
    *,
    name: Optional[str] = None,
    enable_cache: Optional[bool] = None,
    enable_artifact_metadata: Optional[bool] = None,
    enable_artifact_visualization: Optional[bool] = None,
    experiment_tracker: Optional[str] = None,
    step_operator: Optional[str] = None,
    output_materializers: Optional["OutputMaterializersSpecification"] = None,
    settings: Optional[Dict[str, "SettingsOrDict"]] = None,
    extra: Optional[Dict[str, Any]] = None,
    on_failure: Optional["HookSpecification"] = None,
    on_success: Optional["HookSpecification"] = None,
) -> Union[BaseStep, Callable[[F], BaseStep]]:
    """Decorator to create a ZenML step.

    Args:
        _func: The decorated function.
        name: The name of the step. If left empty, the name of the decorated
            function will be used as a fallback.
        enable_cache: Specify whether caching is enabled for this step. If no
            value is passed, caching is enabled by default unless the step
            requires a `StepContext` (see
            `zenml.steps.step_context.StepContext` for more information).
        enable_artifact_metadata: Specify whether metadata is enabled for this
            step. If no value is passed, metadata is enabled by default.
        enable_artifact_visualization: Specify whether visualization is enabled
            for this step. If no value is passed, visualization is enabled by
            default.
        experiment_tracker: The experiment tracker to use for this step.
        step_operator: The step operator to use for this step.
        output_materializers: Output materializers for this step. If
            given as a dict, the keys must be a subset of the output names
            of this step. If a single value (type or string) is given, the
            materializer will be used for all outputs.
        settings: Settings for this step.
        extra: Extra configurations for this step.
        on_failure: Callback function in event of failure of the step. Can be
            a function with three possible parameters,
            `StepContext`, `BaseParameters`, and `BaseException`,
            or a source path to a function of the same specifications
            (e.g. `module.my_function`).
        on_success: Callback function in event of failure of the step. Can be
            a function with two possible parameters, `StepContext` and
            `BaseParameters, or a source path to a function of the same specifications
            (e.g. `module.my_function`).

    Returns:
        The step instance.
    """

    def inner_decorator(func: F) -> Type[BaseStep]:
        """Inner decorator function for the creation of a ZenML Step.

        Args:
            func: The entrypoint function for the step.

        Returns:
            The step instance.
        """
        step_instance = _DecoratedStep(
            entrypoint=func,
            name=name or func.__name__,
            enable_cache=enable_cache,
            enable_artifact_metadata=enable_artifact_metadata,
            enable_artifact_visualization=enable_artifact_visualization,
            experiment_tracker=experiment_tracker,
            step_operator=step_operator,
            output_materializers=output_materializers,
            settings=settings,
            extra=extra,
            on_failure=on_failure,
            on_success=on_success,
        )

        step_instance.__doc__ = func.__doc__
        return step_instance

    if _func is None:
        return inner_decorator
    else:
        return inner_decorator(_func)
