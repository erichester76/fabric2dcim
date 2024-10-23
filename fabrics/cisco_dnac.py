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


    def get_paginated_devices(self, client, limit=500):
        """
        Retrieves all devices from DNAC using pagination.
        
        Args:
            client: The DNAC API client.
            limit: The maximum number of devices to retrieve per request (default: 500).

        Returns:
            A list of all devices across all pages.
        """
        devices = []
        offset = 0

        while True:
            # Fetch devices with pagination (limit and offset)
            response = client.devices.get_device_list(offset=offset, limit=limit)
            
            # Append the current batch of devices to the overall list
            devices.extend(response.response)
            
            # Break if the number of devices retrieved is less than the limit (no more pages)
            if len(response.response) < limit:
                break

            # Increment the offset for the next page
            offset += limit
            
            print(f'Retrieved {offset-1} devices from DNAC...')

        return devices
    
    def get_device_inventory(self):
        """Retrieve device inventory from Cisco DNA Center."""
        try:
            devices = self.get_paginated_devices(self.client)
            print(f'Retrieved {len(devices)} total devices from DNAC...')

            devices_data = []

            for device in devices:
                
                if device.hostname:
                    # Ensure platformId, serialNumber, and hostname are strings
                    platform_id = str(device.platformId or '')
                    serial_number = str(device.serialNumber or '')
                    hostname = str(device.hostname or '')
                    serial_number = re.sub(r'^([^\,]+)\,.+', r'\1', serial_number)
                    part_number = re.sub(r'^([^\,]+)\,.+', r'\1', platform_id)
                    
                    #TODO need to manage stackwise better. 
                    #Its just creating interfaces on the main device now and not creating a stack/virtual chassis
                    
                    model = re.sub(r'^C', r'Catalyst ', platform_id)
                    model = re.sub(r'^WS\-C', r'Catalyst ', model)
                    model = re.sub(r'^IE\-', r'Catalyst IE', model)
                    model = re.sub(r'^AIR\-AP', r'Catalyst ', model)
                    model = re.sub(r'^AIR\-CAP', r'Catalyst ', model)
                    model = re.sub(r'\-K9$', r'', model)
                    model = re.sub(r'^([^\,]+)\,.+', r'\1', model)


                    role = device.family
                    
                    if 'Third Party Device' in role:
                        continue
                    
                    name = re.sub(r'(^[^\.]+)\.clemson\.edu', r'\1', hostname).lower() # TODO make this a variable vs clemson specific
                    interfaces = []
                    
                    # Fetch interfaces for this device
                    try:
                        interfaces_response = self.client.devices.get_interface_info_by_id(device.id).response
                        print(f"Fetched {len(interfaces_response)} interfaces for device {name}")
                        
                        # Process interfaces
                        interfaces = [
                            {
                                'device': {'name': name},
                                'name': interface.get('portName'),
                                'mac_address': interface.get('macAddress'),
                                'enabled': interface.get('status') == 'up',
                                'speed_type': interface.get('speed')
                            }
                            for interface in interfaces_response
                        ]

                    except Exception as e:
                        interfaces = []

                    manufacturer = device.vendor or 'Cisco'
                    manufacturer = re.sub(r' Systems Inc',r'', manufacturer)
                    manufacturer = re.sub(r'^NA$',r'Cisco', manufacturer)

                    device_info = {
                        'name': name,
                        'role': {'name': role},
                        'device_type': {'model': model, 'manufacturer': {'name': manufacturer}, 'part_number': part_number},
                        'platform': f"{device.softwareType or 'AP-IOS'} {device.softwareVersion or ''}",
                        'serial': serial_number,
                        'status': 'active' if device.reachabilityStatus == 'Reachable' else 'offline',
                        'primary_ip4': f"{device.managementIpAddress}/32" if device.managementIpAddress else None,
                        'site': {'name': self.default_site},
                        'interfaces': interfaces  

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
