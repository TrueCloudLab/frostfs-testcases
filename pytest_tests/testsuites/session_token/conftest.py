import pytest

from pytest_tests.helpers.wallet import WalletFactory, WalletFile


@pytest.fixture(scope="module")
def owner_wallet(wallet_factory: WalletFactory) -> WalletFile:
    """
    Returns wallet which owns containers and objects
    """
    return wallet_factory.create_wallet()


@pytest.fixture(scope="module")
def user_wallet(wallet_factory: WalletFactory) -> WalletFile:
    """
    Returns wallet which will use objects from owner via static session
    """
    return wallet_factory.create_wallet()


@pytest.fixture(scope="module")
def stranger_wallet(wallet_factory: WalletFactory) -> WalletFile:
    """
    Returns stranger wallet which should fail to obtain data
    """
    return wallet_factory.create_wallet()
