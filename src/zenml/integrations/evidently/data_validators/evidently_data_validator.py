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
"""Implementation of the Evidently data validator."""

from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

import evidently.metric_preset as metric_preset  # type: ignore
import evidently.metrics as metrics  # type: ignore
import evidently.test_preset as test_preset  # type: ignore
import evidently.tests as tests  # type: ignore
import pandas as pd
from evidently.dashboard import Dashboard  # type: ignore
from evidently.dashboard.tabs import (  # type: ignore
    CatTargetDriftTab,
    ClassificationPerformanceTab,
    DataDriftTab,
    DataQualityTab,
    NumTargetDriftTab,
    ProbClassificationPerformanceTab,
    RegressionPerformanceTab,
)
from evidently.dashboard.tabs.base_tab import Tab  # type: ignore
from evidently.metric_preset.metric_preset import MetricPreset
from evidently.metrics.base_metric import Metric, generate_column_metrics
from evidently.model_profile import Profile  # type: ignore
from evidently.model_profile.sections import (  # type: ignore
    CatTargetDriftProfileSection,
    ClassificationPerformanceProfileSection,
    DataDriftProfileSection,
    DataQualityProfileSection,
    NumTargetDriftProfileSection,
    ProbClassificationPerformanceProfileSection,
    RegressionPerformanceProfileSection,
)
from evidently.model_profile.sections.base_profile_section import (  # type: ignore
    ProfileSection,
)
from evidently.pipeline.column_mapping import ColumnMapping  # type: ignore
from evidently.report import Report  # type: ignore
from evidently.test_preset.test_preset import TestPreset
from evidently.test_suite import TestSuite  # type: ignore
from evidently.tests.base_test import Test, generate_column_tests
from evidently.utils.generators import BaseGenerator

from zenml.data_validators import BaseDataValidator, BaseDataValidatorFlavor
from zenml.integrations.evidently.flavors.evidently_data_validator_flavor import (
    EvidentlyDataValidatorFlavor,
)
from zenml.logger import get_logger
from zenml.utils.source_utils import load_source_path_class

logger = get_logger(__name__)


profile_mapper = {
    "datadrift": DataDriftProfileSection,
    "categoricaltargetdrift": CatTargetDriftProfileSection,
    "numericaltargetdrift": NumTargetDriftProfileSection,
    "dataquality": DataQualityProfileSection,
    "classificationmodelperformance": ClassificationPerformanceProfileSection,
    "regressionmodelperformance": RegressionPerformanceProfileSection,
    "probabilisticmodelperformance": ProbClassificationPerformanceProfileSection,
}

dashboard_mapper = {
    "dataquality": DataQualityTab,
    "datadrift": DataDriftTab,
    "categoricaltargetdrift": CatTargetDriftTab,
    "numericaltargetdrift": NumTargetDriftTab,
    "classificationmodelperformance": ClassificationPerformanceTab,
    "regressionmodelperformance": RegressionPerformanceTab,
    "probabilisticmodelperformance": ProbClassificationPerformanceTab,
}


def get_profile_sections_and_tabs(
    profile_list: Optional[Sequence[str]],
    verbose_level: int = 1,
) -> Tuple[List[ProfileSection], List[Tab]]:
    """Get the profile sections and dashboard tabs for a profile list.

    Args:
        profile_list: List of identifiers for Evidently profiles.
        verbose_level: Verbosity level for the rendered dashboard. Use
            0 for a brief dashboard, 1 for a detailed dashboard.

    Returns:
        A tuple of two lists of profile sections and tabs.

    Raises:
        ValueError: if the profile_section is not supported.
    """
    profile_list = profile_list or list(profile_mapper.keys())
    try:
        return (
            [profile_mapper[profile]() for profile in profile_list],
            [
                dashboard_mapper[profile](verbose_level=verbose_level)
                for profile in profile_list
            ],
        )
    except KeyError as e:
        nl = "\n"
        raise ValueError(
            f"Invalid profile sections: {profile_list} \n\n"
            f"Valid and supported options are: {nl}- "
            f'{f"{nl}- ".join(list(profile_mapper.keys()))}'
        ) from e


def get_metric_class_from_mapping(metric: str) -> Union[Metric, MetricPreset]:
    """Get the Evidently metric or metric preset class from a string.

    Args:
        metric: Name of the metric or metric preset.

    Returns:
        The Evidently metric or metric preset class.

    Raises:
        ValueError: If the metric or metric preset is not a valid Evidently metric or metric preset.
    """
    # metric_mapping = {
    #     "DataQualityPreset": metric_preset.DataQualityPreset,
    #     "DataDriftPreset": metric_preset.DataDriftPreset,
    #     "ClassificationPreset": metric_preset.ClassificationPreset,
    #     "RegressionPreset": metric_preset.RegressionPreset,
    #     "TargetDriftPreset": metric_preset.TargetDriftPreset,
    #     "TextOverviewPreset": metric_preset.TextOverviewPreset,
    #     "DatasetSummaryMetric": metrics.DatasetSummaryMetric,
    #     "DatasetMissingValuesMetric": metrics.DatasetMissingValuesMetric,
    #      ...
    # }
    try:
        # if metric contains preset in name, return an object of the class of same name from metric_preset
        if "Preset" in metric:
            return getattr(metric_preset, metric)
        # else return class of same name from metrics
        else:
            return getattr(metrics, metric)
    except AttributeError:
        raise ValueError(
            f"Metric or MetricPreset {metric} is not a "
            f"valid Evidently metric or metric preset."
        )


def get_test_class_from_mapping(test: str) -> Union[Test, TestPreset]:
    """Get the Evidently test or test preset class from a string.

    Args:
        test: Name of the test or test preset.

    Returns:
        The Evidently test or test preset class.

    Raises:
        ValueError: If the test or test preset is not a valid Evidently test or test preset.
    """
    try:
        if "Preset" in test:
            return getattr(test_preset, test)
        else:
            return getattr(tests, test)
    except AttributeError:
        raise ValueError(
            f"Test or TestPreset {test} is not a "
            f"valid Evidently test or test preset."
        )


def get_metrics(
    metric_list: List[Union[str, list, Dict[str, Any]]]
) -> List[Union[Metric, MetricPreset, BaseGenerator]]:
    """Get a list of Evidently metrics from a list of metric names and/or
    dictionaries.

    Args:
        metric_list: List of metric names and/or dictionaries.

    Returns:
        List of Evidently metrics.

    Raises:
        ValueError: If the metric type is not a valid Evidently metric type.
    """
    metrics = []
    for metric in metric_list:
        if isinstance(metric, str):
            metrics.append(get_metric_class_from_mapping(metric)())
        elif isinstance(metric, list):
            # get dict from second index of list and pass the values to the
            # constructor for the class at index 0
            metrics.append(
                get_metric_class_from_mapping(metric[0])(**metric[1])
            )
        elif isinstance(metric, dict):
            metrics.append(
                generate_column_metrics(
                    get_metric_class_from_mapping(metric["metric"]),
                    metric["columns"] if "columns" in metric else None,
                    metric["parameters"] if "parameters" in metric else None,
                )
            )
        else:
            raise ValueError(
                f"Invalid metric type: {type(metric)}. "
                f"Expected str or dict, got {type(metric)}."
            )
    return metrics


def get_tests(
    test_list: List[Union[str, list, Dict[str, Any]]]
) -> List[Union[Test, TestPreset, BaseGenerator]]:
    """Get a list of Evidently tests from a list of test names and/or
    dictionaries.

    Args:
        test_list: List of test names and/or dictionaries.

    Returns:
        List of Evidently tests.

    Raises:
        ValueError: If the test or test preset is not a valid Evidently test or test preset.
    """
    tests = []
    for test in test_list:
        if isinstance(test, str):
            tests.append(get_test_class_from_mapping(test)())
        elif isinstance(test, list):
            # get dict from second index of list and pass the values to the
            # constructor for the class at index 0
            tests.append(get_test_class_from_mapping(test[0])(**test[1]))
        elif isinstance(test, dict):
            tests.append(
                generate_column_tests(
                    get_test_class_from_mapping(test["test"]),
                    test["columns"],
                    test["parameters"] if "parameters" in test else None,
                )
            )
        else:
            raise ValueError(
                f"Invalid test type: {type(test)}. "
                f"Expected str or dict, got {type(test)}."
            )
    return tests


class EvidentlyDataValidator(BaseDataValidator):
    """Evidently data validator stack component."""

    NAME: ClassVar[str] = "Evidently"
    FLAVOR: ClassVar[
        Type[BaseDataValidatorFlavor]
    ] = EvidentlyDataValidatorFlavor

    @classmethod
    def _unpack_options(
        cls, option_list: Sequence[Tuple[str, Dict[str, Any]]]
    ) -> Sequence[Any]:
        """Unpack Evidently options.

        Implements de-serialization for [Evidently options](https://docs.evidentlyai.com/user-guide/customization)
        that can be passed as constructor arguments when creating Profile and
        Dashboard objects. The convention used is that each item in the list
        consists of two elements:

        * a string containing the full class path of a `dataclass` based
        class with Evidently options
        * a dictionary with kwargs used as parameters for the option instance

        For example,

        ```python
            options = [
                (
                    "evidently.options.ColorOptions",{
                        "primary_color": "#5a86ad",
                        "fill_color": "#fff4f2",
                        "zero_line_color": "#016795",
                        "current_data_color": "#c292a1",
                        "reference_data_color": "#017b92",
                    }
                ),
            ]
        ```

        This is the same as saying:

        ```python
        from evidently.options import ColorOptions

        color_scheme = ColorOptions()
        color_scheme.primary_color = "#5a86ad"
        color_scheme.fill_color = "#fff4f2"
        color_scheme.zero_line_color = "#016795"
        color_scheme.current_data_color = "#c292a1"
        color_scheme.reference_data_color = "#017b92"
        ```

        Args:
            option_list: list of packed Evidently options

        Returns:
            A list of unpacked Evidently options

        Raises:
            ValueError: if one of the passed Evidently class paths cannot be
                resolved to an actual class.
        """
        options = []
        for option_clspath, option_args in option_list:
            try:
                option_cls = load_source_path_class(option_clspath)
            except AttributeError:
                raise ValueError(
                    f"Could not map the `{option_clspath}` Evidently option "
                    f"class path to a valid class."
                )
            option = option_cls(**option_args)
            options.append(option)

        return options

    def data_profiling(
        self,
        dataset: pd.DataFrame,
        comparison_dataset: Optional[pd.DataFrame] = None,
        metric_list: List[Union[str, list, Dict[str, Any]]] = None,
        column_mapping: Optional[ColumnMapping] = None,
        report_options: Sequence[Tuple[str, Dict[str, Any]]] = [],
        **kwargs: Any,
    ) -> Report:
        """Analyze a dataset and generate a data report with Evidently.

        The method takes in an optional list of Evidently options to be passed
        to the report constructor (`report_options`). Each element in the list must be
        composed of two items: the first is a full class path of an Evidently
        option `dataclass`, the second is a dictionary of kwargs with the actual
        option parameters, e.g.:

        ```python
        options = [
            (
                "evidently.options.ColorOptions",{
                    "primary_color": "#5a86ad",
                    "fill_color": "#fff4f2",
                    "zero_line_color": "#016795",
                    "current_data_color": "#c292a1",
                    "reference_data_color": "#017b92",
                }
            ),
        ]
        ```

        Args:
            dataset: Target dataset to be profiled.
            comparison_dataset: Optional dataset to be used for data profiles
                that require a baseline for comparison (e.g data drift profiles).
            metric_list: Optional list identifying the categories of Evidently
                data profiles to be generated.
            column_mapping: Properties of the DataFrame columns used
            report_options: List of Evidently options to be passed to the
                report constructor.
            **kwargs: Extra keyword arguments (unused).

        Returns:
            The Evidently Report as JSON object and as HTML.
        """
        metrics = get_metrics(metric_list)
        unpacked_report_options = self._unpack_options(report_options)

        report = Report(metrics=metrics, options=unpacked_report_options)
        report.run(
            reference_data=dataset,
            current_data=comparison_dataset,
            column_mapping=column_mapping,
        )

        return report

    def data_validation(
        self,
        dataset: Any,
        comparison_dataset: Optional[Any] = None,
        check_list: List[Union[str, list, Dict[str, Any]]] = None,
        test_options: Sequence[Tuple[str, Dict[str, Any]]] = [],
        column_mapping: Optional[ColumnMapping] = None,
        **kwargs: Any,
    ) -> TestSuite:
        """Validate a dataset with Evidently.

        Args:
            dataset: Target dataset to be validated.
            comparison_dataset: Optional dataset to be used for data validation
                that require a baseline for comparison (e.g data drift
                validation).
            check_list: Optional list identifying the categories of Evidently
                data validation checks to be generated.
            test_options: List of Evidently options to be passed to the
                test suite constructor.
            column_mapping: Properties of the DataFrame columns used
            **kwargs: Extra keyword arguments (unused).

        Returns:
            The Evidently Test Suite as JSON object and as HTML.
        """
        tests = get_tests(check_list)
        unpacked_test_options = self._unpack_options(test_options)

        test_suite = TestSuite(tests=tests, options=unpacked_test_options)
        test_suite.run(
            reference_data=dataset,
            current_data=comparison_dataset,
            column_mapping=column_mapping,
        )

        return test_suite

    def data_profiling_legacy(
        self,
        dataset: pd.DataFrame,
        comparison_dataset: Optional[pd.DataFrame] = None,
        profile_list: Optional[Sequence[str]] = None,
        column_mapping: Optional[ColumnMapping] = None,
        verbose_level: int = 1,
        profile_options: Sequence[Tuple[str, Dict[str, Any]]] = [],
        dashboard_options: Sequence[Tuple[str, Dict[str, Any]]] = [],
        **kwargs: Any,
    ) -> Tuple[Profile, Dashboard]:
        """Analyze a dataset and generate a data profile with Evidently.

        The method takes in an optional list of Evidently options to be passed
        to the profile constructor (`profile_options`) and the dashboard
        constructor (`dashboard_options`). Each element in the list must be
        composed of two items: the first is a full class path of an Evidently
        option `dataclass`, the second is a dictionary of kwargs with the actual
        option parameters.

        Args:
            dataset: Target dataset to be profiled.
            comparison_dataset: Optional dataset to be used for data profiles
                that require a baseline for comparison (e.g data drift profiles).
            profile_list: Optional list identifying the categories of Evidently
                data profiles to be generated.
            column_mapping: Properties of the DataFrame columns used
            verbose_level: Level of verbosity for the Evidently dashboards. Use
                0 for a brief dashboard, 1 for a detailed dashboard.
            profile_options: Optional list of options to pass to the
                profile constructor.
            dashboard_options: Optional list of options to pass to the
                dashboard constructor.
            **kwargs: Extra keyword arguments (unused).

        Returns:
            The Evidently Profile and Dashboard objects corresponding to the set
            of generated profiles.
        """
        sections, tabs = get_profile_sections_and_tabs(
            profile_list, verbose_level
        )
        unpacked_profile_options = self._unpack_options(profile_options)
        unpacked_dashboard_options = self._unpack_options(dashboard_options)

        dashboard = Dashboard(tabs=tabs, options=unpacked_dashboard_options)
        dashboard.calculate(
            reference_data=dataset,
            current_data=comparison_dataset,
            column_mapping=column_mapping,
        )
        profile = Profile(sections=sections, options=unpacked_profile_options)
        profile.calculate(
            reference_data=dataset,
            current_data=comparison_dataset,
            column_mapping=column_mapping,
        )
        return profile, dashboard
