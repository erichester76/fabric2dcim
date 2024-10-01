import os
import json
import time

class NetBoxCache:
    def __init__(self, config, netbox):
        self.netbox = netbox
        self.DEBUG = config.get('debug')
        self.cache = {}
        self.cache_file_name = config.get('cache_file_name') or './netbox_cache.json'
        self.cache_time = config.get('cache_time') or 3600 # Default cache time of 1 hour
            
        # Object mapping: maps object_type to (API section, lookup key)
        self.object_mapping = {
            'device_roles': (self.netbox.dcim.device_roles, 'name'),
            'device_types': (self.netbox.dcim.device_types, 'model'),
            'manufacturers': (self.netbox.dcim.manufacturers, 'name'),
            'platforms': (self.netbox.dcim.platforms, 'name'),
            'sites': (self.netbox.dcim.sites, 'name'),
            'ip_addresses': (self.netbox.ipam.ip_addresses, 'address'),
            'interfaces': (self.netbox.dcim.interfaces, lambda i: f"{i.device.name}_{i.name}"),
            'devices': (self.netbox.dcim.devices, 'name'),
            'prefixes': (self.netbox.ipam.prefixes, 'prefix'),
            'cables': (self.netbox.dcim.cables, 'id'),
            'virtual_machines': (self.netbox.virtualization.virtual_machines, 'name'),
            'virtual_interfaces': (self.netbox.virtualization.interfaces, lambda i: f"{i.virtual_machine.name}_{i.name}"),
            'virtual_clusters': (self.netbox.virtualization.clusters, 'name'),
            'virtual_chassis': (self.netbox.dcim.virtual_chassis, 'name')
        }

        self.preload_objects()

    def preload_objects(self):
        """Preload objects either from file or from NetBox based on cache time."""
        if self.is_cache_valid():
            if self.DEBUG:
                print("Loading cache from file.")
            self.load_cache_from_file()
            self.print_cache_summary()  
        else:
            if self.DEBUG:
                print("Cache file is too old or doesn't exist, loading from NetBox.")
            self.load_cache_from_netbox()
            self.save_cache_to_file()
            self.print_cache_summary()  # Print summary after loading from NetBox

    def is_cache_valid(self):
        """Check if the cache file exists and is still valid based on the configured cache time."""
        if not os.path.exists(str(self.cache_file_name)):
            return False
        
        file_age = time.time() - os.path.getmtime(str(self.cache_file_name))
        return file_age < int(self.cache_time)

    def load_cache_from_file(self):
        """Load cache from the JSON file."""
        with open(str(self.cache_file_name), 'r') as cache_file:
            self.cache = json.load(cache_file)

    def save_cache_to_file(self):
        """Save the current cache to a JSON file."""
        with open(str(self.cache_file_name), 'w') as cache_file:
            json.dump(self.cache, cache_file)
        if self.DEBUG:
            print(f"Cache saved to {str(self.cache_file_name)}.")

    def load_cache_from_netbox(self):
        """Load objects from NetBox API and store them in the cache."""
        for object_type, (api_section, lookup_key) in self.object_mapping.items():
            self.cache[object_type] = {}
            for obj in api_section.all():
                if callable(lookup_key):
                    cache_key = lookup_key(obj)  # Use the lambda function to generate the key
                else:
                    cache_key = f"{getattr(obj, lookup_key)}"
                # Convert NetBox objects to serializable form if necessary (e.g., using .serialize())
                self.cache[object_type][cache_key] = obj.serialize() if hasattr(obj, 'serialize') else obj

    def print_cache_summary(self):
        """Print the summary of the preloaded objects."""
        for object_type in self.object_mapping.keys():
            if self.DEBUG:
                print(f"Preloaded {object_type} with {len(self.cache.get(object_type, {}))} entries.")

    def get_cache(self):
        """Return the preloaded cache."""
        return self.cache
