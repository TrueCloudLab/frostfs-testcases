# DevEnv variables
export NEOFS_MORPH_DISABLE_CACHE=true
export DEVENV_PATH="${DEVENV_PATH:-${VIRTUAL_ENV}/../../frostfs-dev-env}"
pushd $DEVENV_PATH > /dev/null
export `make env`
popd > /dev/null