#!/usr/bin/env bash

set -e
set -x

# If only unittests are needed call
# test-coverage-xml.sh unit
# For only integration tests call
# test-coverage-xml.sh integration
TEST_SRC="tests/"${1:-""}
TEST_ENVIRONMENT=${2:-"default"}

export ZENML_DEBUG=1
export ZENML_ANALYTICS_OPT_IN=false
export EVIDENTLY_DISABLE_TELEMETRY=1

./zen-test environment provision $TEST_ENVIRONMENT

# The '-vv' flag enables pytest-clarity output when tests fail.
# Reruns a failing test 3 times with a 5 second delay.
# Shows errors instantly in logs when test fails.
if [ -n "$1" ]; then
    coverage run -m pytest $TEST_SRC --color=yes -vv --environment $TEST_ENVIRONMENT --no-provision --cleanup-docker --reruns 3 --reruns-delay 5 --instafail
else
    coverage run -m pytest tests/unit --color=yes -vv --environment $TEST_ENVIRONMENT --no-provision --reruns 5 --reruns-delay 5 --instafail
    coverage run -m pytest tests/integration --color=yes -vv --environment $TEST_ENVIRONMENT --no-provision --cleanup-docker --reruns 3 --reruns-delay 5 --instafail
fi

./zen-test environment cleanup $TEST_ENVIRONMENT

coverage combine
coverage report --show-missing
coverage xml
