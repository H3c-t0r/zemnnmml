#!/bin/bash

DB="mariadb"
DB_STARTUP_DELAY=30 # Time in seconds to wait for the database container to start

function run_tests_for_version() {
    set -e  # Exit immediately if a command exits with a non-zero status
    local VERSION=$1
    local PRE_TEMPLATE_VERSIONS=("0.40.0" "0.40.3" "0.41.0")

    echo "===== Testing version $VERSION ====="

    # Check if VERSION is in VALID_VERSIONS
    if printf '%s\n' "${PRE_TEMPLATE_VERSIONS[@]}" | grep -q "^$VERSION$"; then
        copier copy -l --trust -r release/0.43.0 https://github.com/zenml-io/template-starter.git test_starter
    else
        mkdir test_starter
        zenml init --template starter --path test_starter --template-with-defaults
        cd test_starter
    fi

    cd test_starter

    export ZENML_ANALYTICS_OPT_IN=false
    export ZENML_DEBUG=true

    echo "===== Installing sklearn integration ====="
    zenml integration install sklearn -y

    echo "===== Running starter template pipeline ====="
    python3 run.py
    # Add additional CLI tests here
    zenml version

    # Confirm DB works and is accessible
    zenml pipeline runs list

    cd ..
    rm -rf test_starter template-starter
    echo "===== Finished testing version $VERSION ====="
}

echo "===== Testing MariaDB ====="
# run a mariadb instance in docker
docker run --name mariadb -d -p 3306:3306 -e MYSQL_ROOT_PASSWORD=password mariadb:10.6
# mariadb takes a while to start up
sleep $DB_STARTUP_DELAY

# List of versions to test
VERSIONS=("0.54.0")

# Start completely fresh
rm -rf ~/.config/zenml

for VERSION in "${VERSIONS[@]}"
do
    set -e  # Exit immediately if a command exits with a non-zero status
    # Create a new virtual environment
    python3 -m venv ".venv-$VERSION"
    source ".venv-$VERSION/bin/activate"

    # Install the specific version
    pip3 install -U pip setuptools wheel
    pip3 install "zenml[templates,server]==$VERSION"

    zenml connect --url mysql://127.0.0.1/zenml --username root --password password

    # Run the tests for this version
    run_tests_for_version $VERSION

    zenml disconnect
    sleep 5

    deactivate
done


# Test the most recent migration with MySQL
set -e
python3 -m venv ".venv-current-branch"
source ".venv-current-branch/bin/activate"

pip3 install -U pip setuptools wheel
pip3 install -e ".[templates,server]"
pip3 install importlib_metadata

zenml connect --url mysql://127.0.0.1/zenml --username root --password password

run_tests_for_version current_branch_mysql

zenml disconnect
docker rm -f mariadb

deactivate
