from frostfs_testlib.shell import Shell


class IpTablesHelper:
    @staticmethod
    def drop_input_traffic_to_port(shell: Shell, ports: list[str]) -> None:
        for port in ports:
            shell.exec(f"sudo iptables -A INPUT -p tcp --dport {port} -j DROP")

    @staticmethod
    def restore_input_traffic_to_port(shell: Shell, ports: list[str]) -> None:
        for port in ports:
            shell.exec(f"sudo iptables -D INPUT -p tcp --dport {port} -j DROP")
