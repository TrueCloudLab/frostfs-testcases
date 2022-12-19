# DevEnv variables
export NEOFS_MORPH_DISABLE_CACHE=true
export DEVENV_PATH="${DEVENV_PATH:-${VIRTUAL_ENV}/../../neofs-dev-env}"
pushd $DEVENV_PATH > /dev/null
export `make env`
popd > /dev/null

export PYTHONPATH=${PYTHONPATH}:${VIRTUAL_ENV}/../robot/resources/lib/:${VIRTUAL_ENV}/../robot/resources/lib/python_keywords:${VIRTUAL_ENV}/../robot/resources/lib/robot:${VIRTUAL_ENV}/../robot/variables:${VIRTUAL_ENV}/../pytest_tests/helpers:${VIRTUAL_ENV}/../pytest_tests/steps:${VIRTUAL_ENV}/../pytest_tests/resources
