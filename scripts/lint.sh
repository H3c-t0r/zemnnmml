#!/usr/bin/env bash
set -e
set -x

SRC=${1:-"src/zenml tests examples"}
SRC_NO_TESTS=${1:-"src/zenml"}

# separate env variable while incrementally completing the docstring task.
# add modules to this list as/when they are completed.
# When we're done we can remove this and just use `SRC_NO_TESTS`.
DOCSTRING_SRC=${1:-"src/zenml/alerter src/zenml/artifact_stores src/zenml/artifacts src/zenml/config src/zenml/io src/zenml/model_deployers src/zenml/cli src/zenml/entrypoints src/zenml/experiment_trackers src/zenml/orchestrators src/zenml/pipelines src/zenml/post_execution src/zenml/secret src/zenml/secrets_managers src/zenml/services src/zenml/stack src/zenml/step_operators src/zenml/steps src/zenml/utils src/zenml/visualizers src/zenml/zen_server src/zenml/zen_service src/zenml/zen_store"}

export ZENML_DEBUG=1
export ZENML_ANALYTICS_OPT_IN=false
flake8 $SRC
autoflake --remove-all-unused-imports --recursive --remove-unused-variables --in-place $SRC --exclude=__init__.py --check
isort $SRC scripts --check-only
black $SRC  --check

# check for docstrings
interrogate $SRC_NO_TESTS -c pyproject.toml
pydocstyle $DOCSTRING_SRC -e --count --convention=google
darglint -v 2 $DOCSTRING_SRC

# check type annotations
mypy $SRC_NO_TESTS
