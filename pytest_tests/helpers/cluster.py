import random
import re
from dataclasses import dataclass
from typing import Any

import data_formatters
from neofs_testlib.blockchain import RPCClient
from neofs_testlib.hosting import Host, Hosting
from neofs_testlib.hosting.config import ServiceConfig
from test_control import wait_for_success


@dataclass
class NodeBase:
    """
    Represents a node of some underlying service
    """

    id: str
    name: str
    host: Host

    def __init__(self, id, name, host) -> None:
        self.id = id
        self.name = name
        self.host = host
        self.construct()

    def construct(self):
        pass

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        return id(self.name)

    def __str__(self):
        return self.label

    def __repr__(self) -> str:
        return self.label

    @property
    def label(self) -> str:
        return self.name

    @wait_for_success(60, 1)
    def start_service(self):
        self.host.start_service(self.name)

    @wait_for_success(60, 1)
    def stop_service(self):
        self.host.stop_service(self.name)

    def get_wallet_password(self) -> str:
        return self._get_attribute(_ConfigAttributes.WALLET_PASSWORD)

    def get_wallet_path(self) -> str:
        return self._get_attribute(
            _ConfigAttributes.LOCAL_WALLET_PATH,
            _ConfigAttributes.WALLET_PATH,
        )

    def get_wallet_config_path(self):
        return self._get_attribute(
            _ConfigAttributes.LOCAL_WALLET_CONFIG,
            _ConfigAttributes.WALLET_CONFIG,
        )

    def get_wallet_public_key(self):
        storage_wallet_path = self.get_wallet_path()
        storage_wallet_pass = self.get_wallet_password()
        return data_formatters.get_wallet_public_key(storage_wallet_path, storage_wallet_pass)

    def _get_attribute(self, attribute_name: str, default_attribute_name: str = None) -> list[str]:
        config = self.host.get_service_config(self.name)
        if default_attribute_name:
            return config.attributes.get(
                attribute_name, config.attributes.get(default_attribute_name)
            )
        else:
            return config.attributes.get(attribute_name)

    def _get_service_config(self) -> ServiceConfig:
        return self.host.get_service_config(self.name)


class InnerRingNode(NodeBase):
    """
    Class represents inner ring node in a cluster

    Inner ring node is not always the same as physical host (or physical node, if you will):
        It can be service running in a container or on physical host
    For testing perspective, it's not relevant how it is actually running,
        since neofs network will still treat it as "node"
    """

    pass


class S3Gate(NodeBase):
    """
    Class represents S3 gateway in a cluster
    """

    def get_endpoint(self) -> str:
        return self._get_attribute(_ConfigAttributes.ENDPOINT)

    @property
    def label(self) -> str:
        return f"{self.name}: {self.get_endpoint()}"


class HTTPGate(NodeBase):
    """
    Class represents HTTP gateway in a cluster
    """

    def get_endpoint(self) -> str:
        return self._get_attribute(_ConfigAttributes.ENDPOINT)

    @property
    def label(self) -> str:
        return f"{self.name}: {self.get_endpoint()}"


class MorphChain(NodeBase):
    """
    Class represents side-chain aka morph-chain consensus node in a cluster

    Consensus node is not always the same as physical host (or physical node, if you will):
        It can be service running in a container or on physical host
    For testing perspective, it's not relevant how it is actually running,
        since neofs network will still treat it as "node"
    """

    rpc_client: RPCClient = None

    def construct(self):
        self.rpc_client = RPCClient(self.get_endpoint())

    def get_endpoint(self) -> str:
        return self._get_attribute(_ConfigAttributes.ENDPOINT)

    @property
    def label(self) -> str:
        return f"{self.name}: {self.get_endpoint()}"


class MainChain(NodeBase):
    """
    Class represents main-chain consensus node in a cluster

    Consensus node is not always the same as physical host:
        It can be service running in a container or on physical host (or physical node, if you will):
    For testing perspective, it's not relevant how it is actually running,
        since neofs network will still treat it as "node"
    """

    rpc_client: RPCClient = None

    def construct(self):
        self.rpc_client = RPCClient(self.get_endpoint())

    def get_endpoint(self) -> str:
        return self._get_attribute(_ConfigAttributes.ENDPOINT)

    @property
    def label(self) -> str:
        return f"{self.name}: {self.get_endpoint()}"


class StorageNode(NodeBase):
    """
    Class represents storage node in a storage cluster

    Storage node is not always the same as physical host:
        It can be service running in a container or on physical host (or physical node, if you will):
    For testing perspective, it's not relevant how it is actually running,
        since neofs network will still treat it as "node"
    """

    def get_rpc_endpoint(self) -> str:
        return self._get_attribute(_ConfigAttributes.RPC_ENDPOINT)

    def get_control_endpoint(self) -> str:
        return self._get_attribute(_ConfigAttributes.CONTROL_ENDPOINT)

    def get_un_locode(self):
        return self._get_attribute(_ConfigAttributes.UN_LOCODE)

    @property
    def label(self) -> str:
        return f"{self.name}: {self.get_rpc_endpoint()}"


class Cluster:
    """
    This class represents a Cluster object for the whole storage based on provided hosting
    """

    default_rpc_endpoint: str
    default_s3_gate_endpoint: str
    default_http_gate_endpoint: str

    def __init__(self, hosting: Hosting) -> None:
        self._hosting = hosting
        self.default_rpc_endpoint = self.storage_nodes[0].get_rpc_endpoint()
        self.default_s3_gate_endpoint = self.s3gates[0].get_endpoint()
        self.default_http_gate_endpoint = self.http_gates[0].get_endpoint()

    @property
    def hosts(self) -> list[Host]:
        """
        Returns list of Hosts
        """
        return self._hosting.hosts

    @property
    def hosting(self) -> Hosting:
        return self._hosting

    @property
    def storage_nodes(self) -> list[StorageNode]:
        """
        Returns list of Storage Nodes (not physical nodes)
        """
        return self._get_nodes(_ServicesNames.STORAGE)

    @property
    def s3gates(self) -> list[S3Gate]:
        """
        Returns list of S3 gates
        """
        return self._get_nodes(_ServicesNames.S3_GATE)

    @property
    def http_gates(self) -> list[S3Gate]:
        """
        Returns list of HTTP gates
        """
        return self._get_nodes(_ServicesNames.HTTP_GATE)

    @property
    def morph_chain_nodes(self) -> list[MorphChain]:
        """
        Returns list of morph-chain consensus nodes (not physical nodes)
        """
        return self._get_nodes(_ServicesNames.MORPH_CHAIN)

    @property
    def main_chain_nodes(self) -> list[MainChain]:
        """
        Returns list of main-chain consensus nodes (not physical nodes)
        """
        return self._get_nodes(_ServicesNames.MAIN_CHAIN)

    @property
    def ir_nodes(self) -> list[InnerRingNode]:
        """
        Returns list of inner-ring nodes (not physical nodes)
        """
        return self._get_nodes(_ServicesNames.INNER_RING)

    def _get_nodes(self, service_name) -> list[StorageNode]:
        configs = self.hosting.find_service_configs(f"{service_name}\d*$")

        class_mapping: dict[str, Any] = {
            _ServicesNames.STORAGE: StorageNode,
            _ServicesNames.INNER_RING: InnerRingNode,
            _ServicesNames.MORPH_CHAIN: MorphChain,
            _ServicesNames.S3_GATE: S3Gate,
            _ServicesNames.HTTP_GATE: HTTPGate,
            _ServicesNames.MAIN_CHAIN: MainChain,
        }

        cls = class_mapping.get(service_name)
        return [
            cls(
                self._get_id(config.name),
                config.name,
                self.hosting.get_host_by_service(config.name),
            )
            for config in configs
        ]

    def _get_id(self, node_name) -> str:
        pattern = "\d*$"

        matches = re.search(pattern, node_name)
        if matches:
            return int(matches.group())

    def get_random_storage_rpc_endpoint(self) -> str:
        return random.choice(self.get_storage_rpc_endpoints())

    def get_storage_rpc_endpoints(self) -> list[str]:
        nodes = self.storage_nodes
        return [node.get_rpc_endpoint() for node in nodes]

    def get_morph_endpoints(self) -> list[str]:
        nodes = self.morph_chain_nodes
        return [node.get_endpoint() for node in nodes]


class _ServicesNames:
    STORAGE = "s"
    S3_GATE = "s3-gate"
    HTTP_GATE = "http-gate"
    MORPH_CHAIN = "morph-chain"
    INNER_RING = "ir"
    MAIN_CHAIN = "main-chain"


class _ConfigAttributes:
    WALLET_PASSWORD = "wallet_password"
    WALLET_PATH = "wallet_path"
    WALLET_CONFIG = "wallet_config"
    LOCAL_WALLET_PATH = "local_wallet_path"
    LOCAL_WALLET_CONFIG = "local_config_path"
    RPC_ENDPOINT = "rpc_endpoint"
    ENDPOINT = "endpoint"
    CONTROL_ENDPOINT = "control_endpoint"
    UN_LOCODE = "un_locode"
