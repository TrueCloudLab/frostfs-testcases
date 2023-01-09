import logging
import os

import allure
import pytest
import yaml
from cluster_test_base import ClusterTestBase
from common import FREE_STORAGE, FROSTFS_CLI_EXEC, WALLET_CONFIG
from frostfs_testlib.cli import FrostfsCli
from frostfs_testlib.shell import CommandResult, Shell
from wallet import WalletFactory, WalletFile

logger = logging.getLogger("NeoLogger")
DEPOSIT_AMOUNT = 30


@pytest.mark.sanity
@pytest.mark.payments
@pytest.mark.skipif(FREE_STORAGE, reason="Test only works on public network with paid storage")
class TestBalanceAccounting(ClusterTestBase):
    @pytest.fixture(scope="class")
    def main_wallet(self, wallet_factory: WalletFactory) -> WalletFile:
        return wallet_factory.create_wallet()

    @pytest.fixture(scope="class")
    def other_wallet(self, wallet_factory: WalletFactory) -> WalletFile:
        return wallet_factory.create_wallet()

    @pytest.fixture(scope="class")
    def cli(self, client_shell: Shell) -> FrostfsCli:
        return FrostfsCli(client_shell, FROSTFS_CLI_EXEC, WALLET_CONFIG)

    @allure.step("Check deposit amount")
    def check_amount(self, result: CommandResult) -> None:
        amount_str = result.stdout.rstrip()

        try:
            amount = int(amount_str)
        except Exception as ex:
            pytest.fail(
                f"Amount parse error, should be parsable as int({DEPOSIT_AMOUNT}), but given {amount_str}: {ex}"
            )

        assert amount == DEPOSIT_AMOUNT

    @staticmethod
    @allure.step("Write config with API endpoint")
    def write_api_config(config_dir: str, endpoint: str, wallet: str) -> str:
        with open(WALLET_CONFIG, "r") as file:
            wallet_config = yaml.full_load(file)
        api_config = {
            **wallet_config,
            "rpc-endpoint": endpoint,
            "wallet": wallet,
        }
        api_config_file = os.path.join(config_dir, "frostfs-cli-api-config.yaml")
        with open(api_config_file, "w") as file:
            yaml.dump(api_config, file)
        return api_config_file

    @allure.title("Test balance request with wallet and address")
    def test_balance_wallet_address(self, main_wallet: WalletFile, cli: FrostfsCli):
        result = cli.accounting.balance(
            wallet=main_wallet.path,
            rpc_endpoint=self.cluster.default_rpc_endpoint,
            address=main_wallet.get_address(),
        )

        self.check_amount(result)

    @allure.title("Test balance request with wallet only")
    def test_balance_wallet(self, main_wallet: WalletFile, cli: FrostfsCli):
        result = cli.accounting.balance(
            wallet=main_wallet.path, rpc_endpoint=self.cluster.default_rpc_endpoint
        )
        self.check_amount(result)

    @allure.title("Test balance request with wallet and wrong address")
    def test_balance_wrong_address(
        self, main_wallet: WalletFile, other_wallet: WalletFile, cli: FrostfsCli
    ):
        with pytest.raises(Exception, match="address option must be specified and valid"):
            cli.accounting.balance(
                wallet=main_wallet.path,
                rpc_endpoint=self.cluster.default_rpc_endpoint,
                address=other_wallet.get_address(),
            )

    @allure.title("Test balance request with config file")
    def test_balance_api(self, temp_directory: str, main_wallet: WalletFile, client_shell: Shell):
        config_file = self.write_api_config(
            config_dir=temp_directory,
            endpoint=self.cluster.default_rpc_endpoint,
            wallet=main_wallet.path,
        )
        logger.info(f"Config with API endpoint: {config_file}")

        cli = FrostfsCli(client_shell, FROSTFS_CLI_EXEC, config_file=config_file)
        result = cli.accounting.balance()

        self.check_amount(result)
