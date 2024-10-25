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

    def devices_to_sites(self):
        """
        Map Device Serial Number to Site ID from Cisco DNA Center.
        """
        results = {}
        devices = []

        # Fetch sites from DNA Center
        sites_response = self.client.sites.get_site().response
        if not sites_response:
            raise ValueError("No sites found in Cisco DNA Center.")
        counter=0
        for site in sites_response:
            counter += 1
            print(f'Processing Site {counter} of {len(sites_response)}')  
            if counter == 1: continue 
            print(f"Devices: {devices}, Sites: {results}")  # Debugging line

            if counter == 3: return devices,results
                   
            # Fetch membership for each site
            membership = self.client.sites.get_membership(site_id=site.id)
            
            if not membership or not hasattr(membership, 'device'):
                # Log if membership is None or doesn't have 'device'
                continue  # Skip if no membership or devices
            if membership.device is None:
                # Log and continue if device is None
                continue  # Skip the site if devices are missing

            # If membership contains devices, map them
            for members in membership.device:
                
                if not members or not hasattr(members, 'response'):
                    continue  # Skip if no valid device response
                
                print(f'{len(members.response)} Devices Found.')

                for device in members.response:
                    if hasattr(device, 'serialNumber'):
                        #print(f"found device {device.hostname} in site {site.get('siteNameHierarchy')}")
                        devices.append(device)
                        results[device.serialNumber] = site.get('siteNameHierarchy')
                    
        return devices,results

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
        offset = 1

        while True:
            # Fetch devices with pagination (limit and offset)
            response = client.devices.get_device_list(offset=offset, limit=limit)
            
            # Append the current batch of devices to the overall list
            devices.extend(response.response)

            # Break if the number of devices retrieved is less than the limit (no more pages)
            #if len(response.response) < limit:
            if offset == 1:
                break

            # Increment the offset for the next page
            offset += limit
            
        return devices
    
    def get_device_inventory(self):
        """Retrieve device inventory from Cisco DNA Center."""
        try:
            #devices = self.get_paginated_devices(self.client)
            #print(f'Retrieved {len(devices)} total devices from DNAC...')

            devices_data = []
            print('Retrieving Device Information from DNAC...')
            (devices,sites) = self.devices_to_sites()
            print(f'Retrieved {len(devices)} total devices.')
            print(f'Retrieved {len(sites)} total sites.')

            for device in devices:
                site = 'Clemson Network'
                location = None
                
                if device.get('serialNumber'):
                    parts = sites[device.serialNumber].split('/')
                    site = parts[2] if len(parts) > 2 else None        # Reeves Football Ops
                    location = parts[3] if len(parts) > 3 else None    # First Floor
                            
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
                        'site': {'name': site},
                        'location': {'name': location},
                        'interfaces': interfaces  

                    }

                    devices_data.append(device_info)

            return devices_data, sites

        except Exception as e:
            print(f"Error fetching device inventory: {e}")
            return []

    def get_interface_inventory(self):
        """Abstract method to retrieve interface inventory from the fabric."""
        pass

    def get_network_inventory(self):
        """Retrieve detailed VLAN information from Cisco DNA Center (via Topology API)."""
        pass

    def get_vlan_inventory(self,devices,sites):
        """Retrieve network inventory (Layer 2/Layer 3) from Cisco DNA Center."""
        try:
            vlans_data = {}  # Dictionary to store VLAN information by VLAN number
            prefixes_data = {}  # Dictionary to store Prefix information by VLAN number
            
            for device in devices:
                parts = sites[device.serialNumber].split('/')
                site_group = parts[1] if len(parts) > 1 else None  # Athletics
                site = parts[2] if len(parts) > 2 else None        # Reeves Football Ops
                location = parts[3] if len(parts) > 3 else None    # First Floor
                            
                try:
                    # Fetch VLAN information for the device's interfaces
                    vlans = self.client.devices.get_device_interface_vlans(device.id).response

                    for vlan in vlans:
                        # Create or update VLAN structure (indexed by vlan_number)
                        if vlan.get('vlanNumber') not in vlans_data:  # Check if VLAN is new
                            print(f"VLAN {site_group}: {site}: {location} :: {vlan.get('vlanNumber')} {vlan.get('vlanType', 'Unknown')}")
                            vlans_data[vlan.get('vlanNumber')] = {
                                'vid': vlan.get('vlanNumber'),
                                'name': vlan.get('vlanType', (f"{device.hostname} vlan {vlan.get('vlanNumber')}")),
                                'status': 'active'
                            }

                        # Create or update Prefix structure (indexed by vlan_number, only if IP-related data exists)
                        if vlan.get('networkAddress') and vlan.get('prefix'):
                            if vlan.get('vlanNumber') not in prefixes_data:  # Check if Prefix is new
                                print(f"Prefix {site_group}: {site}: {location} :: {vlan.get('networkAddress')}/{vlan.get('prefix')}")
                                prefixes_data[vlan.get('vlanNumber')] = {
                                    'name': vlan.get('vlanType', (f"{device.hostname} vlan {vlan.get('vlanNumber')}")),
                                    'vlan': vlan.get('vlanNumber'),
                                    'prefix': f"{vlan.get('networkAddress')}/{vlan.get('prefix')}", 
                                    'status': 'active'
                                }


                except Exception as e:
                    continue #print(f"Error fetching VLANs for device {device.hostname}: {e}")
            
            return vlans_data, prefixes_data
            
        except Exception as e:
            print(f"Error fetching network inventory: {e}")
            return {}, {}

    def get_connection_inventory(self):
        """Retrieve connection inventory from Cisco DNA Center."""
        try:
            links = self.client.topology.get_physical_topology()
            pprint.pp(links)
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
