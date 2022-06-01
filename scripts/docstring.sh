#!/usr/bin/env bash
set -e
set -x

DOCSTRING_SRC=${1:-"src/zenml/alerter src/zenml/artifact_stores src/zenml/artifacts src/zenml/config src/zenml/io src/zenml/model_deployers"}

export ZENML_DEBUG=1
export ZENML_ANALYTICS_OPT_IN=false
interrogate $DOCSTRING_SRC -c pyproject.toml --color
pydocstyle $DOCSTRING_SRC -e --count --convention=google
darglint -v 2 $DOCSTRING_SRC
