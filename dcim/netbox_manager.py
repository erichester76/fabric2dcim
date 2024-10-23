import pynetbox
import pprint
import re

from dcim.ip_manager import IPManager 
from dcim.netbox_cache import NetBoxCache

class NetBoxManager:
    
    def __init__(self, config, ip_manager):
        self.config = config
        self.nb = pynetbox.api(url=self.config.get('netbox_url'), token=self.config.get('netbox_token'))
        self.ip_manager = ip_manager
        self.host = self.config.get('fabric_url')
        self.username = self.config.get('fabric_user')
        self.password = self.config.get('fabric_pass')
        self.default_site = self.config.get('netbox_site')
        self.default_device_role = 'Switch/Router'
        self.default_device_manufacturer = 'Generic'
        self.default_device_model = 'Switch'
        self.DEBUG = self.config.get('debug')
        self.client = None
        # Initialize the NetBoxCache inside NetBoxManager
        self.nb_cacher = NetBoxCache(self.config, self.nb)
        self.netbox_cache = self.nb_cacher.cache
        # Object mapping: maps object_type to (API section, lookup key)
        self.object_mapping = {
            'virtual_chassis': (self.nb.dcim.virtual_chassis, 'name'),
            'racks': (self.nb.dcim.racks, 'name'),
            'devices': (self.nb.dcim.devices, 'name'),
            'device_roles': (self.nb.dcim.device_roles, 'name'),
            'device_types': (self.nb.dcim.device_types, 'model'),
            'manufacturers': (self.nb.dcim.manufacturers, 'name'),
            'platforms': (self.nb.dcim.platforms, 'name'),
            'sites': (self.nb.dcim.sites, 'name'),
            'interfaces': (self.nb.dcim.interfaces, lambda i: f"{i.device.name}_{i.name}"),
            'cables': (self.nb.dcim.cables, lambda c: f"{c.a_terminations[0].id}_{c.b_terminations[0].id}"),
            'vlans': (self.nb.ipam.vlans, 'id'),
            'fhrp_groups': (self.nb.ipam.fhrp_groups, 'id'),
            'prefixes': (self.nb.ipam.prefixes, 'prefix'),
            'ip_addresses': (self.nb.ipam.ip_addresses, 'address'),
            'virtual_machines': (self.nb.virtualization.virtual_machines, 'name'),
            'virtual_interfaces': (self.nb.virtualization.interfaces, lambda i: f"{i.virtual_machine.name}_{i.name}"),
            'virtual_clusters': (self.nb.virtualization.clusters, 'name'),
        }        
    def interface_netbox_type(self, interface_name, speed=None, interface_type=None):
        """
        Convert fabric interface definition to NetBox interface type.

        Args:
            interface_name (str): The name of the interface from the fabric.
            speed (str): The speed of the interface (e.g., '1000', '10000', '2500', '5000', '25000') if available.
            interface_type (str): The type of interface (e.g., 'fiber', 'copper') if available.

        Returns:
            str: The corresponding NetBox interface type.
        """
        # Cisco interface name to speed mapping (when speed is not explicitly provided)
        cisco_interface_speeds = {
            'Gi': '1g',    # GigabitEthernet (1G)
            'Two': '2.5g', #TwoPointFiveGigabitEthernet (2.5G)
            'Fiv': '5g',
            'Te': '10g',   # TenGigabitEthernet (10G)
            'Twe': '20g',   # TwentyFiveGigabitEthernet (20G)
            'Fo': '40g',   # FortyGigabitEthernet (40G)
            'Hu': '100g',  # HundredGigabitEthernet (100G)
        }

        # Determine speed from Cisco-style interface names if speed is not provided
        for prefix, cisco_speed in cisco_interface_speeds.items():
            if interface_name.startswith(prefix):
                speed = cisco_speed
                break

        # Mapping based on speed and type (fiber or copper)
        speed_mapping = {
            '1g': {'fiber': '1000base-x-gbic', 'copper': '1000base-t'},
            '25g': {'fiber': '2.5gbase-x-sfp', 'copper': '2.5gbase-t'},
            '5g': {'fiber': '5gbase-t', 'copper': '5gbase-t'},
            '10g': {'fiber': '10gbase-x-sfpp', 'copper': '10gbase-t'},
            '25g': {'fiber': '25gbase-x-sfp28', 'copper': '25gbase-x-sfp28'},
            '40g': {'fiber': '40gbase-x-qsfpp', 'copper': '40gbase-x-qsfpp'},
            '100g': {'fiber': '100gbase-x-cfp2', 'copper': '100gbase-x-cfp2'}
        }
        
        short_to_long_mapping = {
            'Gi': 'GigabitEthernet',  # 1G
            'Two': 'TwoPointFiveGigabitEthernet',  # 2.5G
            'Fi': 'FiveGigabitEthernet',  # 5G
            'Te': 'TenGigabitEthernet',  # 10G
            'Twe': 'TwentyFiveGigabitEthernet',  # 25G
            'Fo': 'FortyGigabitEthernet',  # 40G
            'Hu': 'HundredGigabitEthernet'  # 100G
        }

        # Apply the regex substitution for short to long mapping
        for short_name, long_name in short_to_long_mapping.items():
            # Match the short interface name and capture the interface numbers (e.g., Gi1/0/1)
            my_regex = r"(" + re.escape(short_name) + r")(\d.+$)"
            
            # Replace the short name with the corresponding long name
            interface_name = re.sub(my_regex, long_name + r'\2', interface_name)
                    
        # Default to 'fiber' if type is not specified
        connection_type = 'fiber'
        if interface_type and 'copper' in interface_type.lower():
            connection_type = 'copper'

        # Check for matching speed in the mapping
        if speed and speed in speed_mapping:
            return (speed_mapping[speed][connection_type],interface_name)

        if 'Vlan' in interface_name or 'Bluetooth' in interface_name:
            return ('virtual', interface_name)
        
        # Fallback if no match found
        return ('other',interface_name)

    def create_or_update(self, object_type, lookup_field, lookup_value, data):
        """
        Generic method to create, update, or modify objects in NetBox.

        Args:
            object_type (str): The type of object to check or create (e.g., 'interfaces', 'devices').
            lookup_field (str): The field to check for existence (e.g., 'name').
            lookup_value (str): The value of the field to search for.
            data (dict): The data to create or update the object with.

        Returns:
            The existing, modified, or newly created object.
        """

        # Generate the cache lookup key for interfaces and VM interfaces
        if object_type == 'interfaces':
            # Check if 'device' in the data is a dictionary (new_data) or an ID (existing_object)
            if isinstance(data['device'], dict) and 'name' in data['device']:
                device_name = data['device'].get('name')
            else:
                # Use reverse lookup to convert ID to name
                device_id = data['device']
                device_name = self.netbox_cache['id_lookup'].get('devices_'+str(device_id))
            
            cache_key = f"{device_name}_{data[lookup_field]}"  # Device Name + Interface Name

        elif object_type == 'virtual_interfaces':
            # Same logic for VM interfaces
            if isinstance(data['virtual_machine'], dict) and 'name' in data['virtual_machine']:
                vm_name = data['virtual_machine'].get('name')
            else:
                vm_id = data['virtual_machine']
                vm_name = self.cache['id_lookup'].get(vm_id, {}).get('name', f"UnknownVM-{vm_id}")
            
            cache_key = f"{vm_name}_{data[lookup_field]}"  # VM Name + Interface Name
        else:
            # Default cache key for other object types
            cache_key = f"{data[lookup_field]}"

        # Check if the object exists in the cache
        if cache_key in self.netbox_cache[object_type]:
            print(f"Using cached {object_type}: {lookup_value} {cache_key}") if self.DEBUG == 1 else None
            existing_object = self.netbox_cache[object_type][cache_key]
            # Compare and update if necessary
            no_change = not existing_object or self.compare_objects(existing_object, data)
            if not no_change:  
                print(f"Updating {object_type}: {lookup_value}") #if self.DEBUG == 1 else None
                existing_object.update(data)  
                # Update cache with new data
                self.netbox_cache[object_type][cache_key] = existing_object  
                string_key = f"{object_type}_{existing_object['id']}"
                self.netbox_cache['id_lookup'][string_key] = existing_object
            
            return existing_object
       
        else:
       
            # If not found in cache, create the object
            print(f"Creating new {object_type}: {lookup_value}") #if self.DEBUG == 1 else None
            new_object = self.create_object(object_type, data)
            #update forward and reverse cache for new object
            self.netbox_cache[object_type][cache_key] = new_object
            string_key = f"{object_type}_{new_object['id']}"
            self.netbox_cache['id_lookup'][string_key] = new_object
       
            return new_object


    def create_object(self, object_type, data):
        """Helper method to create a new object in NetBox."""
        
        api_section, _ = self.object_mapping[object_type]
        
        try:
            # Call the API to create the object and get it imemdiately to get a complete object
            response = api_section.create(data)
            new_object = api_section.get(response.id)
            pprint.pp(new_object)
            return new_object
        
        except Exception as e:
            print(f"Error creating {object_type}: {e}")
            return None


    def compare_objects(self, existing_object, new_data):
        """Compare existing object with new data. Returns True if they match, False otherwise."""
        for key, value in new_data.items():
            # Try both attribute and dictionary access
            if key in existing_object: 
               existing_value = existing_object.get(key, None)
            else:
               existing_value = None

            print(f'COMPARING {key}: {existing_value} :: {value}') if self.DEBUG == 1 else None 

            # Handle fields that contain IDs in the existing object but names in the new data
            if isinstance(existing_value, int) and isinstance(value, dict) and value.get('name'):
                # Perform a reverse lookup to get the name from the ID
                reverse_key = f"{key}s_{existing_value}"
                print(f'looking up id for: {reverse_key}') if self.DEBUG == 1 else None 
                if reverse_key in self.netbox_cache['id_lookup']:
                    existing_value = {'name': self.netbox_cache['id_lookup'][reverse_key]['name']}
                    print(f'after lookup {key}: {existing_value} :: {value}') if self.DEBUG == 1 else None 

            # Normalize strings for comparison
            if isinstance(existing_value, str) and isinstance(value, str):
                existing_value = existing_value.strip().lower()
                value = value.strip().lower()

            if existing_value != value:
                print('CONCLUSION: Cache and Fabric do NOT Match') if self.DEBUG == 1 else None    
                return False
            
        print('CONCLUSION: Cache and Fabric Match') if self.DEBUG == 1 else None   
        return True

    def create_virtual_chassis(self, vc_data):
        """Create or update a Virtual Chassis in NetBox with dependency checks."""

        return self.create_or_update('virtual_chassis', 'name', vc_data['name'], vc_data)

    def generate_slug(self,value):
        # Convert to lowercase, replace spaces with hyphens, and remove invalid characters
        value = value.lower()
        value = re.sub(r'\s+', '-', value)  # Replace spaces with hyphens
        value = re.sub(r'[^a-z0-9_-]', '', value)  # Remove characters that aren't letters, numbers, underscores, or hyphens
        return value
    
    def create_device(self, device_data):
        """Create or update a device in NetBox with dependency and IP checks."""
        
        # Store the IPs to assign after interfaces are created
        self.ip_manager.store_ip_for_device = {
            'name': device_data['name'],
            'primary_ip4': device_data.get('primary_ip4'),
            'primary_ip6': device_data.get('primary_ip6')
        }

        # Remove IPs from device data (they can't be set yet)
        device_data.pop('primary_ip4', None)
        device_data.pop('primary_ip6', None)
        
        # Check or create dependencies first: device_role, device_type, platform, and site
        if 'role' in device_data:
            role_name = device_data['role']['name']
            device_data['role'] = self.create_or_update(
                'device_roles', 'name', role_name, {'name': role_name, 'slug': self.generate_slug(role_name)}
            ).get('id')

        if 'device_type' in device_data:
            type_model = device_data['device_type']['model']
            manufacturer = device_data.get('device_type', {}).get('manufacturer', {}).get('name', 'Generic')
            manufacturer_obj = self.create_or_update(
                'manufacturers', 'name', manufacturer, {'name': manufacturer, 'slug': self.generate_slug(manufacturer)}
            )
            slug=self.generate_slug(manufacturer)+'-'+self.generate_slug(device_data['device_type']['part_number'] if device_data['device_type']['part_number'] else type_model)
            #print(f"'device_types', 'model', {type_model}, 'model': {type_model}, 'slug': {slug}, 'part_number': {device_data['device_type']['part_number'] if device_data['device_type']['part_number'] else None}, 'manufacturer': {manufacturer_obj.get('id')}")
            device_data['device_type'] = self.create_or_update(
                'device_types', 'model', type_model, {'model': type_model, 'slug': slug, 'part_number': device_data["device_type"]["part_number"] if device_data["device_type"]["part_number"] else None, 'manufacturer': manufacturer_obj.get('id')}
            ).get('id')
            

        if 'platform' in device_data:
            platform_name = device_data['platform']
            device_data['platform'] = self.create_or_update(
                'platforms', 'name', platform_name, {'name': platform_name, 'slug': self.generate_slug(platform_name)}
            ).get('id')

        if 'site' in device_data:
            site_name = device_data['site']['name']
            device_data['site'] = self.create_or_update(
                'sites', 'name', site_name, {'name': site_name, 'slug': self.generate_slug(site_name)}
            ).get('id')

        # Now create the device itself
        return self.create_or_update('devices', 'name', device_data['name'], device_data)

    def create_interface(self, interface_data):
        """Create or update an Interface in NetBox with dependency checks."""

        # Extract the media type and speed from the speed_type list
        if interface_data.get('speed_type') and isinstance(interface_data['speed_type'], list):
            media_type = interface_data['speed_type'][0] if len(interface_data['speed_type']) > 0 else None
            speed = interface_data['speed_type'][1] if len(interface_data['speed_type']) > 1 else None
        else:
            media_type = None
            speed = None

        (interface_data['type'],interface_data['name']) = self.interface_netbox_type(interface_data.get('name'), speed, media_type)
        interface_data['mac_address']=interface_data['mac_address'].upper()
        del interface_data['speed_type']

        """Create or update an interface in NetBox with dependency and IP checks."""
        # Now create the interface
        interface = self.create_or_update('interfaces', 'name', interface_data.get('name'), interface_data)
        # Use the IPManager to assign the stored primary IP to the interface
        self.ip_manager.assign_ip_to_interface(interface_data, self.nb)
        return interface
    
    def update_device_with_primary_ips(self):
        """
        Update devices with the primary IPs after they have been assigned to interfaces.
        """
        self.ip_manager.update_device_with_primary_ips(self.nb)

    def create_lag(self, lag_data):
        """Create or update a LAG in NetBox with dependency checks."""
        members=lag_data['members']
        lag_data.pop('members', None)        
        print(f"Creating/Updating LAG {lag_data['name']}") if self.DEBUG == 1 else None
        
        lag_data=self.create_or_update('interfaces', 'name', lag_data['name'], lag_data)

        for member in members:
            member_data={}
            member_data['lag']={'name': lag_data['name'], 'device': { 'name' : lag_data['device']['name'] } }
            member_data['device']={ 'name' : lag_data['device']['name'] }
            member_data['name']=member['name']
            print(f"Adding {member['name']} to {lag_data['name']}") if self.DEBUG == 1 else None
            self.create_or_update('interfaces', 'name', member_data['name'], member_data)
        
        
    def create_connection(self, connection_data):
        """Create or update a connection (cable) in NetBox with device and interface checks, using cache."""

        # Step 1: Check the cache for the source and destination devices
        src_device_cache_key = f"{connection_data['src-device']}"
        dst_device_cache_key = f"{connection_data['dst-device']}"

        src_device = self.netbox_cache['devices'].get(src_device_cache_key)
        dst_device = self.netbox_cache['devices'].get(dst_device_cache_key)

        if not src_device :
            src_device_data = {
                'name': connection_data['src-device'],
                'status': 'active',
                'role': {'name': self.default_device_role}, 
                'device_type': {'model': self.default_device_model, 'manufacturer': {'name': self.default_device_manufacturer}}, 
                'site': {'name': self.default_site} 
            }
            print(f"Src Device {connection_data['src-device']} missing. Creating")
            src_device = self.create_or_update('devices', 'name', connection_data['src-device'], src_device_data)
            self.netbox_cache['devices'][src_device_cache_key] = src_device
            self.netbox_cache['id_lookup']['devices_'+src_device.get('id')] = src_device

        if not dst_device:
            dst_device_data = {
                'name': connection_data['dst-device'],
                'status': 'active',
                'role': {'name': self.default_device_role}, 
                'device_type': {'model': self.default_device_model, 'manufacturer': {'name': self.default_device_manufacturer}}, 
                'site': {'name': self.default_site} 
            }
            print(f"Dst Device {connection_data['dst-device']} missing. Creating")
            dst_device = self.create_or_update('devices', 'name', connection_data['dst-device'], dst_device_data)
            self.netbox_cache['devices'][dst_device_cache_key] = dst_device
            self.netbox_cache['id_lookup']['devices_'+dst_device.get('id')] = dst_device

        if not src_device or not dst_device:
            print(f"Failed to create or find devices: {connection_data['src-device']} or {connection_data['dst-device']}")
            return None

        # Step 2: Check the cache for the source and destination interfaces
        src_interface_cache_key = f"{connection_data['src-device']}_{connection_data['src-interface']}"
        dst_interface_cache_key = f"{connection_data['dst-device']}_{connection_data['dst-interface']}"

        src_interface = self.netbox_cache['interfaces'].get(src_interface_cache_key)
        dst_interface = self.netbox_cache['interfaces'].get(dst_interface_cache_key)

        if not src_interface:
            print(f"Creating new source interface for cable to attach to {src_device['name']} {connection_data['src-interface']}")
            src_interface_data = {
                'name': connection_data['src-interface'],
                'device': src_device['id'],
                'status': 'active',
                'type': dst_interface.get('type')
            }
            src_interface = self.create_or_update('interfaces', 'name', connection_data['src-interface'], src_interface_data)
            self.netbox_cache['interfaces'][src_interface_cache_key] = src_interface

        if not dst_interface:
            print(f"Creating new destination interface for cable to attach to {dst_device['name']} {connection_data['dst-interface']}")
            dst_interface_data = {
                'name': connection_data['dst-interface'],
                'device': dst_device['id'],
                'status': 'active',
                'type': src_interface.get('type')
            }
            dst_interface = self.create_or_update('interfaces', 'name', connection_data['dst-interface'], dst_interface_data)
            self.netbox_cache['interfaces'][dst_interface_cache_key] = dst_interface

        if not src_interface or not dst_interface:
            print(f"Failed to create or find interfaces: {connection_data['src-interface']} or {connection_data['dst-interface']}")
            return None

        # Step 3: Check the cache for the cable between these interfaces using the object_type_id format
        cable_cache_key = f"{src_interface['id']}_{dst_interface['id']}"
        reverse_cable_cache_key = f"{dst_interface['id']}_{src_interface['id']}"

        # Check if the cable exists in either direction in the cache
        existing_cable = self.netbox_cache['cables'].get(cable_cache_key) or self.netbox_cache['cables'].get(reverse_cable_cache_key)
        if existing_cable:
            print(f"Existing cable found between {connection_data['src-device']} and {connection_data['dst-device']}.")
            return None
        # Step 4: Create the cable (connection) in NetBox
        new_cable = self.nb.dcim.cables.create(
          a_terminations= [
                {
                "object_type": "dcim.interface",  
                "object_id": src_interface['id']
                }
             ],
          b_terminations= [
              {
              "object_type": "dcim.interface",  
              "object_id": dst_interface['id']
              }
             ],
          )        # Add the new cable to the cache in both directions
        self.netbox_cache[cable_cache_key] = new_cable
        self.netbox_cache[reverse_cable_cache_key] = new_cable

        return new_cable
