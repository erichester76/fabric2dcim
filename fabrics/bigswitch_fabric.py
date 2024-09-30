import pybsn
import re
import pprint
import ipaddress
from fabrics.network_fabric_base import NetworkFabric
    
# Big Switch Subclass
class BigSwitchFabric(NetworkFabric):

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
                'platform': re.sub(r'^([A-Za-z\ ]+)(\ )([A-Z0-9\:\-\(\)\.\,\ ]+).*$',r'\1',switch.get('software-description')),
                'serial': switch.get('serial-number-description'),
                'status': 'active' if switch.get('connected') else 'offline',
                'primary_ip6': re.sub(r'\%3',r'',switch.get('inet-address', {}).get('ip'))+"/64",
                'primary_ip4': switch.get('inet-address', {}).get('ip')+"/32",
                'site': {'name': self.default_site}
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
                print(f"Found {switch_name} with {len(interfaces[0].get('interface'))} interfaces") if self.DEBUG else None
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
                            'device': {'name': switch_name},
                            'name': re.sub(r'-[0-9a-f]{8}$', '', interfaces[0].get('fabric-lag')[lag].get('name')),
                            'description': interfaces[0].get('fabric-lag')[lag].get('lag-type'),
                            'type': 'lag',
                            'members': [
                                {
                                'name': interfaces[0].get('fabric-lag')[lag].get('member')[mem].get('src-interface'),
                                } for mem in range(len(interfaces[0].get('fabric-lag')[lag].get('member')))
                            ],
                    } for lag in range(len(interfaces[0].get('fabric-lag')))
                    ]
                }
                switches_data.append(switch_info)
            return switches_data
        except Exception as e:
            print(f"Error fetching network inventory: {e}")
            return []
    
    def get_network_inventory(self):
        """Retrieve l2/l3 network inventory from Big Switch."""
        try:
            
            print(f"Processing Interface Groups..")

            interface_groups = self.client.get("controller/applications/bcf/info/fabric/interface-group/detail")
            ig_data=[]
            # Loop through the response at the "group" level
            for group in interface_groups:
                group_name = group.get('name')
                if group_name == 'segment': continue # skip the segment entries

                # Initialize an empty list to hold the members for the entire group
                members = []

                # Loop through each 'interface' in the group and extract member-info
                for interface in group.get('interface', []):
                    # Extract member info (single dictionary per interface)
                    member_info = interface.get('member-info', {})
                    member_data = {
                        'device': member_info.get('associated-switch-name') or member_info.get('switch-name'),
                        'interface': member_info.get('associated-interface-name') or member_info.get('interface-name'),
                        'endpoint': member_info.get('host-name'),
                        'endpoint_interface': member_info.get('interface-name'),
                        'type': member_info.get('type')
                    }
                    if member_data.get('interface'): members.append(member_data) #skip the no interface entries


                # Create a dictionary for the processed group with all members in a single nest
                if members:
                    group_data = {
                      'group_name': group_name,
                      'members': members  
                    }
                    # Append the processed data to the array
                    ig_data.append(group_data)
                    
            print(f"Processing layer2 info..")
            segments = self.client.get("controller/applications/bcf/tenant/segment")
            # Merge the second API response with processed_interfaces
            for segment in segments:
                # Extract the group name from 'interface-group-membership-rule' if available
                if 'interface-group-membership-rule' in segment:
                    for rule in segment['interface-group-membership-rule']:
                        interface_group = rule.get('interface-group')

                        # Find the matching group in 'processed_interfaces'
                        for group in ig_data:
                            if group['group_name'] == interface_group:
                                # Add 'vlan', 'description', and 'segment' to the group
                                group['vlan'] = rule.get('vlan')
                                group['description'] = segment.get('description')
                                group['segment'] = segment.get('id')
                
            print(f"Processing layer3 info..")
            
            logical_routers = self.client.get("controller/applications/bcf/tenant/logical-router/segment-interface")
            for ip_info in logical_routers:
                segment = ip_info.get('segment')
                
                # Iterate throughig_data to find the matching segment
                for index, group in enumerate(ig_data):
                    if group.get('segment') == segment:
                        # Initialize fields for IPv4 and IPv6
                        ipv4_cidr = None
                        ipv6_cidr = None
                        virtual_ip4 = None
                        virtual_ip6 = None

                        # Loop through the 'ip-subnet' in the IP info
                        for subnet in ip_info.get('ip-subnet', []):
                            ip_cidr = subnet.get('ip-cidr')

                            virtual_ip = subnet.get('virtual-ip', {}).get('ip-address', None)
                            ip4_address = None
                            ip4_network = None
                            ip6_address = None
                            ip6_network = None

                            # Check if it's an IPv4 or IPv6 based on format
                            if ':' in ip_cidr:  # IPv6
                                ip6_address = ip_cidr
                                # Calculate the network prefix using ipaddress module
                                ip6_network = str(ipaddress.ip_network(ip_cidr, strict=False))
                            else:  # IPv4
                                ip4_address = ip_cidr
                                # Calculate the network prefix using ipaddress module
                                ip4_network = str(ipaddress.ip_network(ip_cidr, strict=False))

                        # Update the group data at the found index
                        ig_data[index]['ip4_prefix'] = ip4_network
                        ig_data[index]['ip6_prefix'] = ip6_network
                        ig_data[index]['ip4_address'] = ip4_address
                        ig_data[index]['ip6_address'] = ip6_address

            return ig_data
            
        except Exception as e:
            print(f"Error fetching switch inventory: {e}")
            return []
    
            
    
    def get_connection_inventory(self):
        """Retrieve connection inventory from Big Switch."""
        pass
    
