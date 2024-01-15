#!/usr/bin/env bash

set -e
set -x

# If only unittests are needed call
# test-coverage-xml.sh unit
# For only integration tests call
# test-coverage-xml.sh integration
# To store durations, add a fourth argument 'store-durations'
TEST_SRC="tests/"${1:-""}
TEST_ENVIRONMENT=${2:-"default"}
TEST_GROUP=${3:-"1"}
TEST_SPLITS=${4:-"1"}
STORE_DURATIONS=${5:-""}

export ZENML_DEBUG=1
export ZENML_ANALYTICS_OPT_IN=false
export EVIDENTLY_DISABLE_TELEMETRY=1

./zen-test environment provision $TEST_ENVIRONMENT

# The '-vv' flag enables pytest-clarity output when tests fail.
if [ -n "$1" ]; then
    if [ "$STORE_DURATIONS" == "store-durations" ]; then
        coverage run -m pytest $TEST_SRC --color=yes -vv --environment $TEST_ENVIRONMENT --no-provision --cleanup-docker --store-durations --durations-path=full_test_durations
    else
        coverage run -m pytest $TEST_SRC --color=yes -vv --durations-path=full_test_durations --splits=$TEST_SPLITS --group=$TEST_GROUP --environment $TEST_ENVIRONMENT --no-provision --cleanup-docker
    fi
else
    if [ "$STORE_DURATIONS" == "store-durations" ]; then
        coverage run -m pytest tests/unit --color=yes -vv --environment $TEST_ENVIRONMENT --no-provision --store-durations --durations-path=unit_test_durations
        coverage run -m pytest tests/integration --color=yes -vv --environment $TEST_ENVIRONMENT --no-provision --cleanup-docker --store-durations --durations-path=integration_test_durations
    else
        coverage run -m pytest tests/unit --color=yes -vv --durations-path=unit_test_durations --splits=$TEST_SPLITS --group=$TEST_GROUP --environment $TEST_ENVIRONMENT --no-provision
        coverage run -m pytest tests/integration --color=yes -vv integration_test_durations --splits=$TEST_SPLITS --group=$TEST_GROUP --environment $TEST_ENVIRONMENT --no-provision --cleanup-docker
    fi
fi

./zen-test environment cleanup $TEST_ENVIRONMENT

coverage combine
coverage report --show-missing
coverage xml