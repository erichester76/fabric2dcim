from dnacentersdk import api
from fabrics.network_fabric_base import NetworkFabric
import re
import ipaddress
import pprint

# Cisco DNA Center Subclass
class CiscoDNAC(NetworkFabric):

    def __init__(self, config, ip_manager):
        self.config = config
        self.ip_manager = ip_manager
        self.host = self.config.get('fabric_url')
        self.username = self.config.get('fabric_user')
        self.password = self.config.get('fabric_pass')
        self.default_site = self.config.get('netbox_site')
        self.DEBUG = self.config.get('debug')
        self.client = None

    def connect(self):
        """Connect to Cisco DNA Center."""
        self.client = api.DNACenterAPI(
            base_url=self.host,
            username=self.username,
            password=self.password,
            verify=False
        )
        print(f"Connected to Cisco DNA Center API at {self.host}")

    def get_device_inventory(self):
        """Retrieve device inventory from Cisco DNA Center."""
        try:
            devices = self.client.devices.get_device_list()
            devices_data = []

            for device in devices.response:
                device_info = {
                    'name': device.hostname,
                    'role': {'name': device.role},
                    'device_type': {'model': device.type, 'manufacturer': {'name': 'Cisco'}},
                    'platform': device.platformId,
                    'serial': device.serialNumber,
                    'status': 'active' if device.reachabilityStatus == 'Reachable' else 'offline',
                    'primary_ip4': f"{device.managementIpAddress}/32" if device.managementIpAddress else None,
                    'site': {'name': self.default_site}
                }
                devices_data.append(device_info)

            return devices_data
        except Exception as e:
            print(f"Error fetching device inventory: {e}")
            return []

    def get_interface_inventory(self):
        """Retrieve interface inventory from Cisco DNA Center."""
        try:
            devices = self.client.devices.get_device_list()
            interfaces_data = []

            for device in devices.response:
                interfaces = self.client.interfaces.get_interfaces_by_device_id(device.id)
                device_interfaces = {
                    'name': device.hostname,
                    'mac_address': device.macAddress,
                    'platform': device.platformId,
                    'interfaces': [
                        {
                            'device': {'name': device.hostname},
                            'name': interface.interfaceName,
                            'mac_address': interface.macAddress,
                            'enabled': interface.status == 'up',
                            'speed_type': interface.speed
                        }
                        for interface in interfaces.response
                    ]
                }
                interfaces_data.append(device_interfaces)

            return interfaces_data
        except Exception as e:
            print(f"Error fetching interface inventory: {e}")
            return []

    def get_network_inventory(self):
        """Retrieve network inventory (Layer 2/Layer 3) from Cisco DNA Center."""
        try:
            vlans = self.client.vlan.get_vlan()
            networks_data = []

            for vlan in vlans.response:
                vlan_info = {
                    'vlan': vlan.id,
                    'name': vlan.name,
                    'status': vlan.status
                }
                networks_data.append(vlan_info)

            return networks_data
        except Exception as e:
            print(f"Error fetching network inventory: {e}")
            return []

    def get_connection_inventory(self):
        """Retrieve connection inventory from Cisco DNA Center."""
        try:
            links = self.client.topology.get_physical_topology()
            connections = []

            for link in links.response.links:
                connection_data = {
                    'dst-device': link.targetDeviceName,
                    'dst-interface': link.targetInterfaceName,
                    'src-device': link.sourceDeviceName,
                    'src-interface': link.sourceInterfaceName
                }
                connections.append(connection_data)

            return connections
        except Exception as e:
            print(f"Error fetching connection inventory: {e}")
            return []
