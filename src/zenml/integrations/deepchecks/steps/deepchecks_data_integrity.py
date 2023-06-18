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
"""Implementation of the Deepchecks data integrity validation step."""

from typing import Any, Dict, Optional, Sequence, cast

import pandas as pd
from deepchecks.core.suite import SuiteResult

from zenml import step
from zenml.integrations.deepchecks.data_validators.deepchecks_data_validator import (
    DeepchecksDataValidator,
)
from zenml.integrations.deepchecks.validation_checks import (
    DeepchecksDataIntegrityCheck,
)


@step
def deepchecks_data_integrity_check_step(
    dataset: pd.DataFrame,
    check_list: Optional[Sequence[DeepchecksDataIntegrityCheck]] = None,
    dataset_kwargs: Optional[Dict[str, Any]] = None,
    check_kwargs: Optional[Dict[str, Any]] = None,
    run_kwargs: Optional[Dict[str, Any]] = None,
) -> SuiteResult:
    """Run data integrity checks on a pandas dataset using Deepchecks.

    Args:
        dataset: a Pandas DataFrame to validate
        check_list: Optional list of DeepchecksDataIntegrityCheck identifiers
            specifying the subset of Deepchecks data integrity checks to be
            performed. If not supplied, the entire set of data integrity checks
            will be performed.
        dataset_kwargs: Additional keyword arguments to be passed to the
            Deepchecks `tabular.Dataset` or `vision.VisionData` constructor.
        check_kwargs: Additional keyword arguments to be passed to the
            Deepchecks check object constructors. Arguments are grouped for
            each check and indexed using the full check class name or
            check enum value as dictionary keys.
        run_kwargs: Additional keyword arguments to be passed to the
            Deepchecks Suite `run` method.

    Returns:
        A Deepchecks suite result with the validation results.
    """
    data_validator = cast(
        DeepchecksDataValidator,
        DeepchecksDataValidator.get_active_data_validator(),
    )

    return data_validator.data_validation(
        dataset=dataset,
        check_list=cast(Optional[Sequence[str]], check_list),
        dataset_kwargs=dataset_kwargs or {},
        check_kwargs=check_kwargs or {},
        run_kwargs=run_kwargs or {},
    )
