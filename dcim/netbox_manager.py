import pynetbox

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
        self.DEBUG = self.config.get('debug')
        self.client = None
        # Initialize the NetBoxCache inside NetBoxManager
        nb_cacher = NetBoxCache(self.config, self.nb)
        self.netbox_cache = nb_cacher.cache
        self.object_mapping = nb_cacher.object_mapping
        
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
            'Te': '10g',   # TenGigabitEthernet (10G)
            'Twe': '20g',   # TenGigabitEthernet (20G)
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
            '5g': {'fiber': '5gbase-x-sfp', 'copper': '5gbase-t'},
            '10g': {'fiber': '10gbase-x-sfpp', 'copper': '10gbase-t'},
            '25g': {'fiber': '25gbase-x-sfp28', 'copper': '25gbase-x-sfp28'},
            '40g': {'fiber': '40gbase-x-qsfpp', 'copper': '40gbase-x-qsfpp'},
            '100g': {'fiber': '100gbase-x-cfp2', 'copper': '100gbase-x-cfp2'}
        }

        # Default to 'fiber' if type is not specified
        connection_type = 'fiber'
        if interface_type and 'copper' in interface_type.lower():
            connection_type = 'copper'

        # Check for matching speed in the mapping
        if speed and speed in speed_mapping:
            return speed_mapping[speed][connection_type]

        # Fallback if no match found
        return 'other'

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
                device_name = data['device']['name']
            else:
                # Use reverse lookup to convert ID to name
                device_id = data['device']
                device_name = self.cache['id_lookup'].get(device_id, {}).get('name', f"UnknownDevice-{device_id}")
            
            cache_key = f"{device_name}_{data[lookup_field]}"  # Device Name + Interface Name

        elif object_type == 'virtual_interfaces':
            # Same logic for VM interfaces
            if isinstance(data['virtual_machine'], dict) and 'name' in data['virtual_machine']:
                vm_name = data['virtual_machine']['name']
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
                print(f"Updating {object_type}: {lookup_value}") if self.DEBUG == 1 else None
                existing_object.update(data)  
                self.netbox_cache[object_type][cache_key] = existing_object  # Update cache with new data
            return existing_object
        else:
            # If not found in cache, create the object
            print(f"Creating new {object_type}: {lookup_value}") if self.DEBUG == 1 else None
            new_object = self.create_object(object_type, data)
            self.netbox_cache[object_type][cache_key] = new_object
            return new_object

    def create_object(self, object_type, data):
        """Helper method to create a new object in NetBox."""
        api_section, _ = self.object_mapping[object_type]
        return api_section.create(data)

    def compare_objects(self, existing_object, new_data):
        """Compare existing object with new data. Returns True if they match, False otherwise."""
        for key, value in new_data.items():
            # Try both attribute and dictionary access
            existing_value = existing_object.get(key, None)
            print(f'{key}: {existing_value} :: {value}') if self.DEBUG == 1 else None 

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
                print('Cache and Fabric do NOT Match') if self.DEBUG == 1 else None    
                return False
        print('Cache and Fabric Match') if self.DEBUG == 1 else None   
        return True

    def create_virtual_chassis(self, vc_data):
        """Create or update a Virtual Chassis in NetBox with dependency checks."""

        return self.create_or_update('virtual_chassis', 'name', vc_data['name'], vc_data)

    def create_device(self, device_data):
        """Create or update a device in NetBox with dependency and IP checks."""
        
        # Store the IPs to assign after interfaces are created
        device_name = device_data['name']
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
                'device_roles', 'name', role_name, {'name': role_name, 'slug': role_name.lower().replace(" ", "-")}
            ).get('id')

        if 'device_type' in device_data:
            type_model = device_data['device_type']['model']
            manufacturer = device_data.get('device_type', {}).get('manufacturer', {}).get('name', 'Generic')
            manufacturer_obj = self.create_or_update(
                'manufacturers', 'name', manufacturer, {'name': manufacturer, 'slug': manufacturer.lower().replace(" ", "-")}
            )
            device_data['device_type'] = self.create_or_update(
                'device_types', 'model', type_model, {'model': type_model, 'slug': manufacturer.lower().replace(" ", "-")+'-'+type_model.lower().replace(" ", "-"), 'manufacturer': manufacturer_obj.get('id')}
            ).get('id')

        if 'platform' in device_data:
            platform_name = device_data['platform']
            device_data['platform'] = self.create_or_update(
                'platforms', 'name', platform_name, {'name': platform_name, 'slug': platform_name.lower().replace(" ", "-")}
            ).get('id')

        if 'site' in device_data:
            site_name = device_data['site']['name']
            device_data['site'] = self.create_or_update(
                'sites', 'name', site_name, {'name': site_name, 'slug': site_name.lower().replace(" ", "-")}
            ).get('id')

        # Now create the device itself
        return self.create_or_update('devices', 'name', device_data['name'], device_data)

    def create_interface(self, interface_data):
        """Create or update an Interface in NetBox with dependency checks."""

        # Extract the media type and speed from the speed_type list
        media_type = interface_data['speed_type'][0] if interface_data['speed_type'] else None
        speed = interface_data['speed_type'][1] if interface_data['speed_type'] else None        
        interface_data['type'] = self.interface_netbox_type(interface_data.get('name'), speed, media_type)
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
        """Create or update a connection (cable) in NetBox with interface termination checks."""
        lookup_value_a = connection_data['termination_a_id']
        lookup_value_b = connection_data['termination_b_id']

        # Ensure the interfaces for the terminations exist
        termination_a = self.nb.dcim.interfaces.get(id=lookup_value_a)
        termination_b = self.nb.dcim.interfaces.get(id=lookup_value_b)

        if not termination_a:
            raise ValueError(f"Interface A with ID '{lookup_value_a}' does not exist.")
        if not termination_b:
            raise ValueError(f"Interface B with ID '{lookup_value_b}' does not exist.")

        # Check if a cable already exists between the terminations
        existing_cable = self.nb.dcim.cables.filter(
            termination_a_id=lookup_value_a,
            termination_b_id=lookup_value_b
        )

        if existing_cable:
            print(f"Connection (cable) between A '{lookup_value_a}' and B '{lookup_value_b}' already exists. Skipping creation.") if self.DEBUG == 1 else None
            return existing_cable
        else:
            print(f"Creating new connection (cable) between A '{lookup_value_a}' and B '{lookup_value_b}'.") if self.DEBUG == 1 else None
            return self.nb.dcim.cables.create(connection_data)
