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
                'manufacturer': { 'name': 'Generic'}, 
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
            segment_data={}
            # Loop through the response at the "group" level
            for group in interface_groups:
                group_data = []
                group_name = group.get('name')
                print(f'Found IG: {group_name}') if self.DEBUG ==1 else None

                if group_name == 'segment': continue # skip the segment entries

                # Initialize an empty list to hold the members for the entire group
                members = []

                # Loop through each 'interface' in the group and extract member-info
                for interface in group.get('interface', []):
                    # Extract member info (single dictionary per interface)
                    leaf_group=interface.get('leaf-group')
                    down_reason=interface.get('interface-down-reason')
                    phy_state = interface.get('phy-state')
                    op_state = interface.get('op-state')
                    mode = interface.get('mode')
                    member_info = interface.get('member-info', {})
                    member_data={}
                    if member_info.get('type') == 'host':
                        member_data['endpoint'] = member_info.get('host-name')
                        member_data['endpoint_interface'] = member_info.get('interface-name')
                        if down_reason == 'None':
                            member_data['device'] = member_info.get('associated-switch-name') 
                            member_data['interface'] = member_info.get('associated-interface-name')
                        
                    if member_info.get('type') == 'switch':
                        member_data['device'] = member_info.get('switch-name') 
                        member_data['interface'] = member_info.get('interface-name') if member_info.get('type') == 'switch' else None,
                
                        
                    members.append(member_data) #skip the no interface entries

                # Create a dictionary for the processed group with all members in a single nest
                group_data = {
                    'interface_group_name': group_name,
                    'switch_group' : leaf_group,
                    'members': members if members else None,  
                    'mode': mode,
                    'admin_state': op_state,
                    'status': phy_state,                    
                    }
                merged=False
                # check if entry for group-name & leaf-group already exists, if so merge members together
                for index, group in enumerate(ig_data):
                    if group.get('interface_group_name') == group_name and group.get('switch_group') == leaf_group:
                        print(f'adding members to group {group_name}') if self.DEBUG ==1 else None
                        ig_data[index]['members'].append(members)  
                        merged=True
                # Append the processed data to the array
                if not merged: 
                    ig_data.append(group_data)
                    print(f'Adding group {group_name}') if self.DEBUG ==1 else None
                    
            print(f"Processing layer2 info..")
            segments = self.client.get("controller/applications/bcf/tenant/segment")
            for segment in segments:
                # Extract the group name from 'interface-group-membership-rule' if available
                if 'interface-group-membership-rule' in segment:
                    for rule in segment['interface-group-membership-rule']:
                        interface_group = rule.get('interface-group')
                        print(f'Found IG in segment: {interface_group}') if self.DEBUG ==1 else None
                
                        # Iterate through 'ig_data' with enumerate to track index
                        for idx, igroup in enumerate(ig_data):
                             if igroup['interface_group_name'] == interface_group:
                                print(f'Found existing group {interface_group}') if self.DEBUG ==1 else None
                                # Ensure 'segments' is a list in the group
                                if 'segments' not in igroup:
                                    igroup['segments'] = []

                                # Append the new segment to the 'segments' list
                                new_segment = {
                                    'segment': segment.get('name')
                                }
                                ig_data[idx]['segments'].append(new_segment)
                                matched = True
                                print(f'Adding segment to group {interface_group }') if self.DEBUG ==1 else None

                                break  # Stop searching once we find a match
                        
                        # If no match is found, create a new entry in 'ig_data' with a 'segments' subgroup
                        new_group = {}
                        if not matched:
                            new_group = {
                                'interface_group_name': interface_group,
                                'segments': [
                                    {
                                        'segment': segment.get('name')
                                    }
                                ]
                            }
                            matched=False
                            print(f"Adding interface group {new_group} for segment {segment.get('name')}")
                            ig_data.append(new_group)                 


                        segment_data[segment.get('name')] = {
                            'vlan': rule.get('vlan'),
                            'description': rule.get('description'),
                            'vni': segment.get('member-vni') if segment.get('member-vni') != 'None' else None,
                        }
                            
            pprint.pp(segment_data)
            print(f"Processing layer3 info..")
            
            logical_routers = self.client.get("controller/applications/bcf/tenant/logical-router/segment-interface")
            for ip_info in logical_routers:
                # Initialize fields for IPv4 and IPv6
                ip4_address = None
                ip4_network = None
                ip6_address = None
                ip6_network = None
                ip4_virtual = None
                ip6_virtual = None
                segment = None
                # Loop through the 'ip-subnet' in the IP info
                for subnet in ip_info.get('ip-subnet', []):
                    ip_cidr = subnet.get('ip-cidr')
                    virtual_ip = subnet.get('virtual-ip', {}).get('ip-address', None)
                    segment = ip_info.get('segment')

                    # Check if it's an IPv4 or IPv6 based on format
                    if ':' in ip_cidr:  # IPv6
                        ip6_address = ip_cidr
                        ip6_network = str(ipaddress.ip_network(ip_cidr, strict=False))
                        ip6_virtual = str(virtual_ip)
                    else:  # IPv4
                        ip4_address = ip_cidr
                        ip4_network = str(ipaddress.ip_network(ip_cidr, strict=False))
                        ip4_virtual = str(virtual_ip)
                        
                    for key,value in segment_data.items():
                        if str(key) == str(segment):
                            print(f'Saving IP Information to segment {segment} {ip4_address} {ip6_address}') if self.DEBUG==1 else None
                            segment_data[key]['ip4_network']=ip4_network
                            segment_data[key]['ip6_network']=ip6_network
                            segment_data[key]['ip4_address']=ip4_address
                            segment_data[key]['ip6_address']=ip6_address
                            segment_data[key]['ip4_virtual']=ip4_virtual
                            segment_data[key]['ip6_virtual']=ip6_virtual
                            
                # Update the group data at the found index

            return (ig_data,segment_data)
            
        except Exception as e:
            print(f"Error fetching switch inventory: {e}")
            return []
            
    
    def get_connection_inventory(self):
        """Retrieve connection inventory from Big Switch."""
        #get spine/leaf connections
        core_links = self.client.get("controller/applications/bcf/info/fabric/link")
        
    
