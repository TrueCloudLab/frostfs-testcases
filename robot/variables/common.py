import os

import yaml

CONTAINER_WAIT_INTERVAL = "1m"

SIMPLE_OBJECT_SIZE = os.getenv("SIMPLE_OBJECT_SIZE", "1000")
COMPLEX_OBJECT_CHUNKS_COUNT = os.getenv("COMPLEX_OBJECT_CHUNKS_COUNT", "3")
COMPLEX_OBJECT_TAIL_SIZE = os.getenv("COMPLEX_OBJECT_TAIL_SIZE", "1000")

MAINNET_BLOCK_TIME = os.getenv("MAINNET_BLOCK_TIME", "1s")
MAINNET_TIMEOUT = os.getenv("MAINNET_TIMEOUT", "1min")
MORPH_BLOCK_TIME = os.getenv("MORPH_BLOCK_TIME", "1s")
NEOFS_CONTRACT_CACHE_TIMEOUT = os.getenv("NEOFS_CONTRACT_CACHE_TIMEOUT", "30s")

# Time interval that allows a GC pass on storage node (this includes GC sleep interval
# of 1min plus 15 seconds for GC pass itself)
STORAGE_GC_TIME = os.getenv("STORAGE_GC_TIME", "75s")

GAS_HASH = os.getenv("GAS_HASH", "0xd2a4cff31913016155e38e474a2c06d08be276cf")

NEOFS_CONTRACT = os.getenv("NEOFS_IR_CONTRACTS_NEOFS")

ASSETS_DIR = os.getenv("ASSETS_DIR", "TemporaryDir")
DEVENV_PATH = os.getenv("DEVENV_PATH", os.path.join("..", "neofs-dev-env"))

# Password of wallet owned by user on behalf of whom we are running tests
WALLET_PASS = os.getenv("WALLET_PASS", "")

# Load node parameters
LOAD_NODES = os.getenv("LOAD_NODES", "").split(",")
LOAD_NODE_SSH_USER = os.getenv("LOAD_NODE_SSH_USER", "root")
LOAD_NODE_SSH_PRIVATE_KEY_PATH = os.getenv("LOAD_NODE_SSH_PRIVATE_KEY_PATH")
BACKGROUND_WRITERS_COUNT = os.getenv("BACKGROUND_WRITERS_COUNT", 10)
BACKGROUND_READERS_COUNT = os.getenv("BACKGROUND_READERS_COUNT", 10)
BACKGROUND_OBJ_SIZE = os.getenv("BACKGROUND_OBJ_SIZE", 1024)
BACKGROUND_LOAD_MAX_TIME = os.getenv("BACKGROUND_LOAD_MAX_TIME", 600)

# Paths to CLI executables on machine that runs tests
NEOGO_EXECUTABLE = os.getenv("NEOGO_EXECUTABLE", "neo-go")
NEOFS_CLI_EXEC = os.getenv("NEOFS_CLI_EXEC", "neofs-cli")
NEOFS_AUTHMATE_EXEC = os.getenv("NEOFS_AUTHMATE_EXEC", "neofs-authmate")
NEOFS_ADM_EXEC = os.getenv("NEOFS_ADM_EXEC", "neofs-adm")

# Config for neofs-adm utility. Optional if tests are running against devenv
NEOFS_ADM_CONFIG_PATH = os.getenv("NEOFS_ADM_CONFIG_PATH")

FREE_STORAGE = os.getenv("FREE_STORAGE", "false").lower() == "true"
BIN_VERSIONS_FILE = os.getenv("BIN_VERSIONS_FILE")

HOSTING_CONFIG_FILE = os.getenv("HOSTING_CONFIG_FILE", ".devenv.hosting.yaml")
STORAGE_NODE_SERVICE_NAME_REGEX = r"s\d\d"
HTTP_GATE_SERVICE_NAME_REGEX = r"http-gate\d\d"
S3_GATE_SERVICE_NAME_REGEX = r"s3-gate\d\d"

# Generate wallet configs
# TODO: we should move all info about wallet configs to fixtures
WALLET_CONFIG = os.path.join(os.getcwd(), "wallet_config.yml")
with open(WALLET_CONFIG, "w") as file:
    yaml.dump({"password": WALLET_PASS}, file)
