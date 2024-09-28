
from abc import ABC, abstractmethod

# Base Class for Network Fabric
class NetworkFabric(ABC):

    @abstractmethod
    def connect(self):
        """Abstract method to establish a connection to the network fabric."""
        pass

    @abstractmethod
    def get_device_inventory(self):
        """Abstract method to retrieve switch inventory from the fabric."""
        pass

    @abstractmethod
    def get_interface_inventory(self):
        """Abstract method to retrieve interface inventory from the fabric."""
        pass

    @abstractmethod
    def get_vlan_inventory(self):
        """Abstract method to retrieve vlan inventory from the fabric."""
        pass
    
    @abstractmethod
    def get_lag_inventory(self):
        """Abstract method to retrieve LAG inventory from the fabric."""
        pass

    @abstractmethod
    def get_connection_inventory(self):
        """Abstract method to retrieve connection inventory from the fabric."""
        pass
