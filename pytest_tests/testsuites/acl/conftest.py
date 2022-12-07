import os
import uuid
from dataclasses import dataclass
from typing import Optional

import allure
import pytest
from cluster import Cluster
from common import WALLET_CONFIG, WALLET_PASS
from file_helper import generate_file
from neofs_testlib.shell import Shell
from neofs_testlib.utils.wallet import init_wallet
from python_keywords.acl import EACLRole
from python_keywords.container import create_container
from python_keywords.neofs_verbs import put_object_to_random_node
from wellknown_acl import PUBLIC_ACL

OBJECT_COUNT = 5


@dataclass
class Wallet:
    wallet_path: Optional[str] = None
    config_path: Optional[str] = None


@dataclass
class Wallets:
    wallets: dict[EACLRole, list[Wallet]]

    def get_wallet(self, role: EACLRole = EACLRole.USER) -> Wallet:
        return self.wallets[role][0]

    def get_wallets_list(self, role: EACLRole = EACLRole.USER) -> list[Wallet]:
        return self.wallets[role]


@pytest.fixture(scope="module")
def wallets(default_wallet, temp_directory, cluster: Cluster) -> Wallets:
    other_wallets_paths = [
        os.path.join(temp_directory, f"{str(uuid.uuid4())}.json") for _ in range(2)
    ]
    for other_wallet_path in other_wallets_paths:
        init_wallet(other_wallet_path, WALLET_PASS)

    ir_node = cluster.ir_nodes[0]
    storage_node = cluster.storage_nodes[0]

    ir_wallet_path = ir_node.get_wallet_path()
    ir_wallet_config = ir_node.get_wallet_config_path()

    storage_wallet_path = storage_node.get_wallet_path()
    storage_wallet_config = storage_node.get_wallet_config_path()

    yield Wallets(
        wallets={
            EACLRole.USER: [Wallet(wallet_path=default_wallet, config_path=WALLET_CONFIG)],
            EACLRole.OTHERS: [
                Wallet(wallet_path=other_wallet_path, config_path=WALLET_CONFIG)
                for other_wallet_path in other_wallets_paths
            ],
            EACLRole.SYSTEM: [
                Wallet(wallet_path=ir_wallet_path, config_path=ir_wallet_config),
                Wallet(wallet_path=storage_wallet_path, config_path=storage_wallet_config),
            ],
        }
    )


@pytest.fixture(scope="module")
def file_path(simple_object_size):
    yield generate_file(simple_object_size)


@pytest.fixture(scope="function")
def eacl_container_with_objects(
    wallets: Wallets, client_shell: Shell, cluster: Cluster, file_path: str
):
    user_wallet = wallets.get_wallet()
    with allure.step("Create eACL public container"):
        cid = create_container(
            user_wallet.wallet_path,
            basic_acl=PUBLIC_ACL,
            shell=client_shell,
            endpoint=cluster.default_rpc_endpoint,
        )

    with allure.step("Add test objects to container"):
        objects_oids = [
            put_object_to_random_node(
                user_wallet.wallet_path,
                file_path,
                cid,
                attributes={"key1": "val1", "key": val, "key2": "abc"},
                shell=client_shell,
                cluster=cluster,
            )
            for val in range(OBJECT_COUNT)
        ]

    yield cid, objects_oids, file_path

    # with allure.step('Delete eACL public container'):
    #     delete_container(user_wallet, cid)
