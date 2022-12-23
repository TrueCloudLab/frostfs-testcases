import allure
import epoch
import pytest
from cluster import Cluster
from neofs_testlib.shell import Shell


# To skip adding every mandatory singleton dependency to EACH test function
class ClusterTestBase:
    shell: Shell
    cluster: Cluster

    @pytest.fixture(scope="session", autouse=True)
    def fill_mandatory_dependencies(self, cluster: Cluster, client_shell: Shell):
        ClusterTestBase.shell = client_shell
        ClusterTestBase.cluster = cluster
        yield

    @allure.title("Tick {epochs_to_tick} epochs")
    def tick_epochs(self, epochs_to_tick: int):
        for _ in range(epochs_to_tick):
            self.tick_epoch()

    def tick_epoch(self):
        epoch.tick_epoch(self.shell, self.cluster)

    def get_epoch(self):
        return epoch.get_epoch(self.shell, self.cluster)

    def ensure_fresh_epoch(self):
        return epoch.ensure_fresh_epoch(self.shell, self.cluster)
