import os

# Load node parameters
LOAD_NODES = os.getenv("LOAD_NODES", "").split(",")
LOAD_NODE_SSH_USER = os.getenv("LOAD_NODE_SSH_USER", "root")
LOAD_NODE_SSH_PRIVATE_KEY_PATH = os.getenv("LOAD_NODE_SSH_PRIVATE_KEY_PATH")
BACKGROUND_WRITERS_COUNT = os.getenv("BACKGROUND_WRITERS_COUNT", 10)
BACKGROUND_READERS_COUNT = os.getenv("BACKGROUND_READERS_COUNT", 10)
BACKGROUND_OBJ_SIZE = os.getenv("BACKGROUND_OBJ_SIZE", 1024)
BACKGROUND_LOAD_MAX_TIME = os.getenv("BACKGROUND_LOAD_MAX_TIME", 600)

# Load run parameters

OBJ_SIZE = os.getenv("OBJ_SIZE", "1000").split(",")
CONTAINERS_COUNT = os.getenv("CONTAINERS_COUNT", "1").split(",")
OUT_FILE = os.getenv("OUT_FILE", "1mb_200.json").split(",")
OBJ_COUNT = os.getenv("OBJ_COUNT", "4").split(",")
WRITERS = os.getenv("WRITERS", "200").split(",")
READERS = os.getenv("READER", "0").split(",")
DELETERS = os.getenv("DELETERS", "0").split(",")
LOAD_TIME = os.getenv("LOAD_TIME", "200").split(",")
LOAD_TYPE = os.getenv("LOAD_TYPE", "grpc").split(",")
LOAD_NODES_COUNT = os.getenv("LOAD_NODES_COUNT", "1").split(",")
STORAGE_NODE_COUNT = os.getenv("STORAGE_NODE_COUNT", "4").split(",")
CONTAINER_PLACEMENT_POLICY = os.getenv(
    "STORAGE_NODE_COUNT", "REP 1 IN X CBF 1 SELECT 1  FROM * AS X"
)
