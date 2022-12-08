import json
import pathlib
import re
from dataclasses import dataclass
from io import StringIO

import allure
import pytest
import yaml
from cluster import Cluster, StorageNode
from common import WALLET_CONFIG
from configobj import ConfigObj
from neofs_testlib.cli import NeofsCli

SHARD_PREFIX = "NEOFS_STORAGE_SHARD_"
BLOBSTOR_PREFIX = "_BLOBSTOR_"


@dataclass
class Blobstor:
    path: str
    path_type: str

    def __eq__(self, other) -> bool:
        if not isinstance(other, self.__class__):
            raise RuntimeError(f"Only two {self.__class__.__name__} instances can be compared")
        return self.path == other.path and self.path_type == other.path_type

    def __hash__(self):
        return hash((self.path, self.path_type))

    @staticmethod
    def from_config_object(section: ConfigObj, shard_id: str, blobstor_id: str):
        var_prefix = f"{SHARD_PREFIX}{shard_id}{BLOBSTOR_PREFIX}{blobstor_id}"
        return Blobstor(section.get(f"{var_prefix}_PATH"), section.get(f"{var_prefix}_TYPE"))


@dataclass
class Shard:
    blobstor: list[Blobstor]
    metabase: str
    writecache: str

    def __eq__(self, other) -> bool:
        if not isinstance(other, self.__class__):
            raise RuntimeError(f"Only two {self.__class__.__name__} instances can be compared")
        return (
            set(self.blobstor) == set(other.blobstor)
            and self.metabase == other.metabase
            and self.writecache == other.writecache
        )

    def __hash__(self):
        return hash((self.metabase, self.writecache))

    @staticmethod
    def _get_blobstor_count_from_section(config_object: ConfigObj, shard_id: int):
        pattern = f"{SHARD_PREFIX}{shard_id}{BLOBSTOR_PREFIX}"
        blobstors = {key[: len(pattern) + 2] for key in config_object.keys() if pattern in key}
        return len(blobstors)

    @staticmethod
    def from_config_object(config_object: ConfigObj, shard_id: int):
        var_prefix = f"{SHARD_PREFIX}{shard_id}"

        blobstor_count = Shard._get_blobstor_count_from_section(config_object, shard_id)
        blobstors = [
            Blobstor.from_config_object(config_object, shard_id, blobstor_id)
            for blobstor_id in range(blobstor_count)
        ]

        write_cache_enabled = config_object.as_bool(f"{var_prefix}_WRITECACHE_ENABLED")

        return Shard(
            blobstors,
            config_object.get(f"{var_prefix}_METABASE_PATH"),
            config_object.get(f"{var_prefix}_WRITECACHE_PATH") if write_cache_enabled else "",
        )

    @staticmethod
    def from_object(shard):
        metabase = shard["metabase"]["path"] if "path" in shard["metabase"] else shard["metabase"]
        writecache = (
            shard["writecache"]["path"] if "path" in shard["writecache"] else shard["writecache"]
        )

        return Shard(
            blobstor=[
                Blobstor(path=blobstor["path"], path_type=blobstor["type"])
                for blobstor in shard["blobstor"]
            ],
            metabase=metabase,
            writecache=writecache,
        )


def shards_from_yaml(contents: str) -> list[Shard]:
    config = yaml.safe_load(contents)
    config["storage"]["shard"].pop("default")

    return [Shard.from_object(shard) for shard in config["storage"]["shard"].values()]


def shards_from_env(contents: str) -> list[Shard]:
    configObj = ConfigObj(StringIO(contents))

    pattern = f"{SHARD_PREFIX}\d*"
    num_shards = len(set(re.findall(pattern, contents)))

    return [Shard.from_config_object(configObj, shard_id) for shard_id in range(num_shards)]


@pytest.mark.sanity
@pytest.mark.shard
class TestControlShard:
    @staticmethod
    def get_shards_from_config(node: StorageNode) -> list[Shard]:
        config_file = node.get_remote_config_path()
        file_type = pathlib.Path(config_file).suffix
        contents = node.host.get_shell().exec(f"cat {config_file}").stdout

        parser_method = {
            ".env": shards_from_env,
            ".yaml": shards_from_yaml,
            ".yml": shards_from_yaml,
        }

        shards = parser_method[file_type](contents)
        return shards

    @staticmethod
    def get_shards_from_cli(node: StorageNode) -> list[Shard]:
        wallet_path = node.get_remote_wallet_path()
        wallet_password = node.get_wallet_password()
        control_endpoint = node.get_control_endpoint()

        cli_config = node.host.get_cli_config("neofs-cli")

        cli = NeofsCli(node.host.get_shell(), cli_config.exec_path, WALLET_CONFIG)
        result = cli.shards.list(
            endpoint=control_endpoint,
            wallet=wallet_path,
            wallet_password=wallet_password,
            json_mode=True,
        )
        return [Shard.from_object(shard) for shard in json.loads(result.stdout.split(">", 1)[1])]

    @allure.title("All shards are available")
    def test_control_shard(self, cluster: Cluster):
        for storage_node in cluster.storage_nodes:
            shards_from_config = self.get_shards_from_config(storage_node)
            shards_from_cli = self.get_shards_from_cli(storage_node)
            assert set(shards_from_config) == set(shards_from_cli)
