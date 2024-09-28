import pynetbox
import re

class NetBoxManager:
    
    def __init__(self, netbox_url, netbox_token):
        self.nb = pynetbox.api(url=netbox_url, token=netbox_token)

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
        existing_object = getattr(api_section, object_type).get(**{lookup_field: lookup_value})

        if existing_object:
            print(f"{object_type.capitalize()} with {lookup_field} '{lookup_value}' already exists. Skipping creation.")
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
        """Create or update an interface in NetBox with dependency and IP checks."""
        # Ensure the device for the interface exists
        if 'device' in interface_data:
            device_name = interface_data['device']['name']
            interface_data['device'] = self.create_or_update(
                'devices', 'name', device_name, {'name': device_name}
            ).id

        # Ensure the IP address exists on the interface
        if 'ip_addresses' in interface_data:
            for ip in interface_data['ip_addresses']:
                ip_obj = self.create_or_update(
                    'ip_addresses', 'address', ip, {'address': ip}, api='ipam'
                )
                # Attach IP to the interface
                self.nb.ipam.ip_addresses.update(ip_obj.id, {'interface': interface_data['id']})

        # Now create the interface
        return self.create_or_update('interfaces', 'name', interface_data['name'], interface_data)

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
