import json
from dataclasses import dataclass

import allure
import pytest
import yaml
from cluster import Cluster
from common import NEOFS_CLI_EXEC, WALLET_CONFIG
from neofs_testlib.cli import NeofsCli
from neofs_testlib.hosting import Host, Hosting, ServiceConfig
from neofs_testlib.shell import Shell


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


@pytest.mark.sanity
@pytest.mark.shard
class TestControlShard:
    @staticmethod
    def get_shards_from_config(host: Host, service_config: ServiceConfig) -> list[Shard]:
        config_file = service_config.attributes["config_path"]
        config = yaml.safe_load(host.get_shell().exec(f"cat {config_file}").stdout)
        config["storage"]["shard"].pop("default")
        return [
            Shard(
                blobstor=[
                    Blobstor(path=blobstor["path"], path_type=blobstor["type"])
                    for blobstor in shard["blobstor"]
                ],
                metabase=shard["metabase"]["path"],
                writecache=shard["writecache"]["path"],
            )
            for shard in config["storage"]["shard"].values()
        ]

    @staticmethod
    def get_shards_from_cli(host: Host, service_config: ServiceConfig) -> list[Shard]:
        wallet_path = service_config.attributes["wallet_path"]
        wallet_password = service_config.attributes["wallet_password"]
        control_endpoint = service_config.attributes["control_endpoint"]

        cli = NeofsCli(host.get_shell(), NEOFS_CLI_EXEC, WALLET_CONFIG)
        result = cli.shards.list(
            endpoint=control_endpoint,
            wallet=wallet_path,
            wallet_password=wallet_password,
            json_mode=True,
        )
        return [
            Shard(
                blobstor=[
                    Blobstor(path=blobstor["path"], path_type=blobstor["type"])
                    for blobstor in shard["blobstor"]
                ],
                metabase=shard["metabase"],
                writecache=shard["writecache"],
            )
            for shard in json.loads(result.stdout.split(">", 1)[1])
        ]

    @allure.title("All shards are available")
    def test_control_shard(self, hosting: Hosting, client_shell: Shell, cluster: Cluster):
        for stroage_host in cluster.storage_nodes:
            shards_from_config = self.get_shards_from_config(
                hosting.get_host_by_service(stroage_host.name),
                hosting.get_service_config(stroage_host.name),
            )
            shards_from_cli = self.get_shards_from_cli(
                hosting.get_host_by_service(stroage_host.name),
                hosting.get_service_config(stroage_host.name),
            )
            assert set(shards_from_config) == set(shards_from_cli)
