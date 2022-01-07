#!/usr/bin/env bash

set -Eeo pipefail

pre_run () {
  zenml integration install airflow
  zenml integration install sklearn
  zenml integration install tensorflow
}

pre_run_forced () {
  zenml integration install airflow -f
  zenml integration install sklearn -f
  zenml integration install tensorflow -f
}