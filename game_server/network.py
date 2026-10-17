"""Explicit IPv4 network boundary shared by HTTP and game listeners."""
from ipaddress import ip_address, ip_network


class NetworkPolicy:
    def __init__(self, networks=()):
        if not isinstance(networks,(list,tuple)) or any(not isinstance(n,str) for n in networks):
            raise ValueError('allowed_networks must be a list of IPv4 CIDRs')
        self.networks=[ip_network('127.0.0.0/8')]
        for value in networks:
            network=ip_network(value,strict=False)
            if network.version!=4 or network.prefixlen==0:
                raise ValueError('Use a specific IPv4 LAN subnet')
            self.networks.append(network)

    def allows(self, address):
        try:
            ip=ip_address(address)
            return any(ip in network for network in self.networks)
        except ValueError:
            return False
