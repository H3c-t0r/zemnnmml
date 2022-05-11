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
import inspect
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Optional,
    Type,
    TypeVar,
    Union,
    overload,
)

from zenml.exceptions import StepInterfaceError
from zenml.steps import BaseStep
from zenml.steps.utils import (
    INSTANCE_CONFIGURATION,
    OUTPUT_SPEC,
    PARAM_CREATED_BY_FUNCTIONAL_API,
    PARAM_CUSTOM_STEP_OPERATOR,
    PARAM_ENABLE_CACHE,
    STEP_INNER_FUNC_NAME,
)

if TYPE_CHECKING:
    from zenml.artifacts.base_artifact import BaseArtifact

F = TypeVar("F", bound=Callable[..., Any])


def _check_function_is_type_annotated(_func: F) -> None:
    """
    Check if given function has full type annotations.

    Args:
        _func: function to be checked.

    Raises:
        StepInterfaceError: raises an error if an annotation is missing.
    """
    func_name = _func.__name__
    argspec = inspect.getfullargspec(_func)

    # check if function has return type annotations
    annotations = argspec.annotations
    if "return" not in annotations:
        raise StepInterfaceError(
            f"All `@step` annotated functions must have type annotations. "
            f"Function '{func_name}' has no return type annotation."
        )

    # for all args (incl. *args, **kwargs), check type annotations exist
    args = argspec.args
    if argspec.varargs is not None:
        args.append(argspec.varargs)
    if argspec.varkw is not None:
        args.append(argspec.varkw)
    for arg in args:
        if arg in annotations:
            continue
        raise StepInterfaceError(
            f"All `@step` annotated functions must have type annotations. "
            f"Function '{func_name}' has no type annotation for arg '{arg}'."
        )


@overload
def step(_func: F) -> Type[BaseStep]:
    """Type annotations for step decorator in case of no arguments."""
    ...


@overload
def step(
    *,
    name: Optional[str] = None,
    enable_cache: bool = True,
    output_types: Optional[Dict[str, Type["BaseArtifact"]]] = None,
    custom_step_operator: Optional[str] = None,
) -> Callable[[F], Type[BaseStep]]:
    """Type annotations for step decorator in case of arguments."""
    ...


def step(
    _func: Optional[F] = None,
    *,
    name: Optional[str] = None,
    enable_cache: Optional[bool] = None,
    output_types: Optional[Dict[str, Type["BaseArtifact"]]] = None,
    custom_step_operator: Optional[str] = None,
) -> Union[Type[BaseStep], Callable[[F], Type[BaseStep]]]:
    """Outer decorator function for the creation of a ZenML step

    In order to be able to work with parameters such as `name`, it features a
    nested decorator structure.

    Args:
        _func: The decorated function.
        name: The name of the step. If left empty, the name of the decorated
            function will be used as a fallback.
        enable_cache: Specify whether caching is enabled for this step. If no
            value is passed, caching is enabled by default unless the step
            requires a `StepContext` (see
            :class:`zenml.steps.step_context.StepContext` for more information).
        output_types: A dictionary which sets different outputs to non-default
            artifact types
        custom_step_operator: Optional name of a
            `zenml.step_operators.BaseStepOperator` to use for this step.

    Returns:
        the inner decorator which creates the step class based on the
        ZenML BaseStep

    Raises:
        StepInterfaceError: raises an error if _func is not type annotated.
    """

    def inner_decorator(func: F) -> Type[BaseStep]:
        """Inner decorator function for the creation of a ZenML Step

        Args:
          func: types.FunctionType, this function will be used as the
            "process" method of the generated Step

        Returns:
            The class of a newly generated ZenML Step.

        Raises:
            StepInterfaceError: raises an error if _func is not type annotated.
        """
        _check_function_is_type_annotated(func)
        step_name = name or func.__name__
        output_spec = output_types or {}

        return type(  # noqa
            step_name,
            (BaseStep,),
            {
                STEP_INNER_FUNC_NAME: staticmethod(func),
                INSTANCE_CONFIGURATION: {
                    PARAM_ENABLE_CACHE: enable_cache,
                    PARAM_CREATED_BY_FUNCTIONAL_API: True,
                    PARAM_CUSTOM_STEP_OPERATOR: custom_step_operator,
                },
                OUTPUT_SPEC: output_spec,
                "__module__": func.__module__,
            },
        )

    if _func is None:
        return inner_decorator
    else:
        return inner_decorator(_func)
