
import requests
from fabrics.network_fabric_base import NetworkFabric

# Cisco ACI Subclass
class CiscoACIFabric(NetworkFabric):

    def __init__(self, config, ip_manager):
        self.config = config
        self.ip_manager = ip_manager
        self.apic_url = self.config.get('fabric_url')
        self.username = self.config.get('fabric_user')
        self.password = self.config.get('fabric_pass')
        self.default_site = self.config.get('netbox_site')
        self.DEBUG = self.config.get('debug')
        self.client = None

    def connect(self):
        """Implement connection logic specific to Cisco ACI."""
        login_url = f"{self.apic_url}/api/aaaLogin.json"
        payload = {
            "aaaUser": {
                "attributes": {
                    "name": self.username,
                    "pwd": self.password
                }
            }
        }
        try:
            response = requests.post(login_url, json=payload, verify=False)
            response.raise_for_status()
            self.session = response.cookies
            print("Connected to Cisco ACI.")
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Cisco ACI: {e}")
    
    def get_switch_inventory(self):
        """Retrieve switches from Cisco ACI."""
        switch_url = f"{self.apic_url}/api/node/class/fabricNode.json"
        try:
            response = requests.get(switch_url, cookies=self.session, verify=False)
            response.raise_for_status()
            switches = response.json()["imdata"]
            switches_data = []
            for switch in switches:
                attributes = switch["fabricNode"]["attributes"]
                switch_info = {
                    "name": attributes["name"],
                    "model": attributes["model"],
                    "serial": attributes["serial"],
                    "role": attributes["role"],
                    "address": attributes["address"]
                }
                switches_data.append(switch_info)
            return switches_data
        except Exception as e:
            print(f"Error fetching switch inventory from Cisco ACI: {e}")
            return []

    def get_interface_inventory(self):
        """Retrieve interface inventory from Cisco ACI."""
        interface_url = f"{self.apic_url}/api/node/class/l1PhysIf.json"
        try:
            response = requests.get(interface_url, cookies=self.session, verify=False)
            response.raise_for_status()
            interfaces = response.json()["imdata"]
            interfaces_data = []
            for interface in interfaces:
                attributes = interface["l1PhysIf"]["attributes"]
                interface_info = {
                    "id": attributes["id"],
                    "description": attributes["descr"],
                    "speed": attributes["speed"],
                    "mtu": attributes["mtu"]
                }
                interfaces_data.append(interface_info)
            return interfaces_data
        except Exception as e:
            print(f"Error fetching interface inventory from Cisco ACI: {e}")
            return []

    def get_lag_inventory(self):
        """Retrieve LAG inventory from Cisco ACI."""
        # Cisco ACI handles Port-Channel, you can implement logic to retrieve port-channel details
        pass

    def get_connection_inventory(self):
        """Retrieve connection inventory from Cisco ACI."""
        # Connections (Cables) can be inferred from interface and port-channel relationships
        pass
