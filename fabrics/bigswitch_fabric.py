import pybsn
import re
from fabrics.network_fabric_base import NetworkFabric

DEFAULT_SITE='University of San Diego'

# Big Switch Subclass
class BigSwitchFabric(NetworkFabric):

    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password
        self.client = None

    def connect(self):
        """Implement connection logic specific to Big Switch."""
        self.client = pybsn.connect(
            host=self.host,
            username=self.username,
            password=self.password,
            verify_tls=False
        )
        print(f"Connected to Big Switch API at {self.host}")

    def get_device_inventory(self):
        """Retrieve switches from Big Switch via the /fabric/switch endpoint."""
        try:
            switches = self.client.get("controller/applications/bcf/info/fabric/switch")
            switches_data = []
            
            for switch in switches:
                switch_info = {
                'name': switch.get('name'),
                'role': {'name': switch.get('fabric-role')},  
                'device_type': {'model': switch.get('model-number-description')}, 
                'manufacturer': {'name': 'Generic'}, 
                'platform': re.sub(r'^([A-Za-z\ ]+)(\ )([A-Z0-9\:\-\(\)\.\,\ ]+).*$',r'\1',switch.get('software-description')),
                'serial_number': switch.get('serial-number-description'),
                'status': 'active' if switch.get('connected') else 'offline',
                'primary_ip6': re.sub(r'\%3',r'',switch.get('inet-address', {}).get('ip'))+"/64",
                'primary_ip4': switch.get('inet-address', {}).get('ip')+"/32",
                'site': {'name': DEFAULT_SITE}
                }
                switches_data.append(switch_info)
            
            return switches_data
        except Exception as e:
            print(f"Error fetching switch inventory: {e}")
            return []

    def get_interface_inventory(self):
        """Retrieve switches from Big Switch."""     
        try:
            switches = self.client.get("controller/core/switch-config")
            switches_data = []
            for switch in switches:
                switch_name = switch.get('name')
                switch_mac = switch.get('mac')
                interfaces = self.client.get(f'controller/core/switch[name="{switch_name}"]')
                switch_info = {
                    'name': switch_name,
                    'mac_address': switch_mac,
                    'platform': interfaces[0].get('implementation'),
                    'interfaces': [
                        {
                            'device': {'name': switch_name},
                            'name': interfaces[0].get('interface')[iface].get('name'),
                            'mac_address': interfaces[0].get('interface')[iface].get('hardware-address'),
                            'enabled': True if interfaces[0].get('interface')[iface].get('state') == 'up' else False,
                            'speed_type': interfaces[0].get('interface')[iface].get('current-features')
                        } for iface in range(len(interfaces[0].get('interface')))
                    ],
                    'lags': [
                        {
                            'name': interfaces[0].get('fabric-lag')[lag].get('name'),
                            'type': interfaces[0].get('fabric-lag')[lag].get('lag-type'),
                            'members': [
                                {
                                'interface': interfaces[0].get('fabric-lag')[lag].get('member')[mem].get('src-interface')
                                } for mem in range(len(interfaces[0].get('fabric-lag')[lag].get('member')))
                            ],
                    } for lag in range(len(interfaces[0].get('fabric-lag')))
                    ]
                }
                switches_data.append(switch_info)
            return switches_data
        except Exception as e:
            print(f"Error fetching switch inventory: {e}")
            return []

    def get_lag_inventory(self):
        """Retrieve LAG inventory from Big Switch."""
        pass
    
    def get_vlan_inventory(self):
        """Retrieve connection inventory from Big Switch."""
        pass
    
    def get_connection_inventory(self):
        """Retrieve connection inventory from Big Switch."""
        pass
    
