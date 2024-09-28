import pynetbox
import re
import pprint

class NetBoxManager:
    
    def __init__(self, netbox_url, netbox_token):
        self.nb = pynetbox.api(url=netbox_url, token=netbox_token)
        
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
            'Gi': '1000',    # GigabitEthernet (1G)
            'Te': '10000',   # TenGigabitEthernet (10G)
            'Fo': '40000',   # FortyGigabitEthernet (40G)
            'Hu': '100000',  # HundredGigabitEthernet (100G)
        }

        # Determine speed from Cisco-style interface names if speed is not provided
        for prefix, cisco_speed in cisco_interface_speeds.items():
            if interface_name.startswith(prefix):
                speed = cisco_speed
                break

        # Mapping based on speed and type (fiber or copper)
        speed_mapping = {
            '100': {'fiber': '100base-fx', 'copper': '100base-tx'},
            '1000': {'fiber': '1000base-x-gbic', 'copper': '1000base-t'},
            '2500': {'fiber': '2.5gbase-x-sfp', 'copper': '2.5gbase-t'},
            '5000': {'fiber': '5gbase-x-sfp', 'copper': '5gbase-t'},
            '10000': {'fiber': '10gbase-x-sfpp', 'copper': '10gbase-t'},
            '25000': {'fiber': '25gbase-x-sfp28', 'copper': '25gbase-t'},
            '40000': {'fiber': '40gbase-x-qsfpp', 'copper': '40gbase-cr4'},
            '100000': {'fiber': '100gbase-x-cfp2', 'copper': '100gbase-cr4'}
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


    def create_or_update(self, object_type, lookup_field, lookup_value, data, api='dcim'):
        """
        Generic method to create or update objects in NetBox.

        Args:
            object_type (str): The type of object to check or create (e.g., 'devices', 'interfaces', 'cables').
            lookup_field (str): The field to check for existence (e.g., 'name', 'address').
            lookup_value (str): The value of the field to search for.
            data (dict): The data to create or update the object with.
            api (str): The API section to use ('dcim', 'ipam').

        Returns:
            The existing or newly created object.
        """
        api_section = getattr(self.nb, api)
         # Check if the object_type is 'interfaces', we need to filter by both name and device
        if object_type == 'interfaces':
        # Filter using both interface name and device name
            existing_object = getattr(api_section, object_type).filter(name=lookup_value, device=data['device']['name'])
        
        else:
            # For other object types, we can just use get
            existing_object = getattr(api_section, object_type).get(**{lookup_field: lookup_value})
        
        if existing_object:
            print(f"{object_type.capitalize()} with {lookup_field} '{lookup_value}' already exists.")
            return existing_object
        else:
            print(f"Creating new {object_type.capitalize()} with {lookup_field} '{lookup_value}'.")
            return getattr(api_section, object_type).create(data)

    def create_device(self, device_data):
        """Create or update a device in NetBox with dependency and IP checks."""
        # Check or create dependencies first: device_role, device_type, platform, and site
        if 'device_role' in device_data:
            role_name = device_data['device_role']['name']
            device_data['device_role'] = self.create_or_update(
                'device_roles', 'name', role_name, {'name': role_name, 'slug': role_name.lower().replace(" ", "-")}
            ).id

        if 'device_type' in device_data:
            type_model = device_data['device_type']['model']
            manufacturer = device_data['manufacturer']['name']
            manufacturer_obj = self.create_or_update(
                'manufacturers', 'name', manufacturer, {'name': manufacturer, 'slug': manufacturer.lower().replace(" ", "-")}
            )
            device_data['device_type'] = self.create_or_update(
                'device_types', 'model', type_model, {'model': type_model, 'manufacturer': manufacturer_obj.id}
            ).id

        if 'platform' in device_data:
            platform_name = device_data['platform']
            device_data['platform'] = self.create_or_update(
                'platforms', 'name', platform_name, {'name': platform_name, 'slug': platform_name.lower().replace(" ", "-")}
            ).id

        if 'site' in device_data:
            site_name = device_data['site']['name']
            device_data['site'] = self.create_or_update(
                'sites', 'name', site_name, {'name': site_name, 'slug': site_name.lower().replace(" ", "-")}
            ).id

        # Check or create primary_ip4 and primary_ip6
        if 'primary_ip4' in device_data:
            primary_ip4 = device_data['primary_ip4']
            device_data['primary_ip4'] = self.create_or_update(
                'ip_addresses', 'address', primary_ip4, {'address': primary_ip4}, api='ipam'
            ).id

        if 'primary_ip6' in device_data:
            primary_ip6 = device_data['primary_ip6']
            device_data['primary_ip6'] = self.create_or_update(
                'ip_addresses', 'address', primary_ip6, {'address': primary_ip6}, api='ipam'
            ).id

        # Now create the device itself
        return self.create_or_update('devices', 'name', device_data['name'], device_data)

    def create_interface(self, interface_data):
        """Create or update an Interface in NetBox with dependency checks."""

        # Extract the media type and speed from the speed_type list
        media_type = interface_data['speed_type'][0] if interface_data['speed_type'] else None
        speed = interface_data['speed_type'][1] if interface_data['speed_type'] else None        
        interface_data['type'] = self.interface_netbox_type(interface_data.get('name'), speed, media_type)

        """Create or update an interface in NetBox with dependency and IP checks."""
        # Now create the interface
        interface = self.create_or_update('interfaces', 'name', interface_data.get('name'), interface_data)
        return interface

    def create_lag(self, lag_data):
        """Create or update a LAG in NetBox with dependency checks."""
        # Ensure the device for the LAG exists
        if 'device' in lag_data:
            device_name = lag_data['device']['name']
            lag_data['device'] = self.create_or_update(
                'devices', 'name', device_name, {'name': device_name}
            ).id

        # Ensure member interfaces exist
        if 'lag_members' in lag_data:
            for member in lag_data['lag_members']:
                interface_name = member['name']
                self.create_or_update('interfaces', 'name', interface_name, {'name': interface_name})

        # Now create the LAG (LAG is an interface with type='lag')
        return self.create_or_update('interfaces', 'name', lag_data['name'], lag_data)

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
            print(f"Connection (cable) between A '{lookup_value_a}' and B '{lookup_value_b}' already exists. Skipping creation.")
            return existing_cable
        else:
            print(f"Creating new connection (cable) between A '{lookup_value_a}' and B '{lookup_value_b}'.")
            return self.nb.dcim.cables.create(connection_data)
