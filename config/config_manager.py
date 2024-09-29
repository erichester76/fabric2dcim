import os
import argparse

class ConfigManager:
    def __init__(self):
        # Initialize the configuration dictionary
        self.config = {}

    def load(self):
        """
        Load configuration values from command-line arguments.
        """
        parser = argparse.ArgumentParser(description="Sync network fabric information to NetBox")
        parser.add_argument('--fabric-type', type=str, help='Fabric type (bigswitch or cisco-aci) (FABRIC_TYPE environment variable)')
        parser.add_argument('--fabric-url', type=str, help='Fabric controller URL (FABRIC_URL environment variable)')
        parser.add_argument('--fabric-name', type=str, help='Fabric controller name (FABRIC_URL environment variable)')
        parser.add_argument('--username', type=str, help='Fabric username (FABRIC_USERNAME environment variable)')
        parser.add_argument('--password', type=str, help='Fabric password (FABRIC_PASSWORD environment variable)')
        parser.add_argument('--netbox-url', type=str, help='NetBox URL (NETBOX_URL environment variable)')
        parser.add_argument('--netbox-token', type=str, help='NetBox API token (NETBOX_TOKEN environment variable)')
        parser.add_argument('--netbox-site', type=str, help='NetBox site name to use (NETBOX_SITE environment variable)')
        parser.add_argument('--debug', type=str, help='Show Debug output (DEBUG environment variable)')

        args = parser.parse_args()

        # Load Environment variables if not on command line
        self.config['netbox_url'] = args.netbox_url or os.getenv('NETBOX_URL')
        self.config['netbox_token'] = args.netbox_token or os.getenv('NETBOX_TOKEN')
        self.config['netbox_site'] = args.netbox_site or os.getenv('NETBOX_SITE')
        self.config['fabric_type'] = args.fabric_type or os.getenv('FABRIC_TYPE')
        self.config['fabric_url'] = args.fabric_url or os.getenv('FABRIC_URL')
        self.config['fabric_user'] = args.username or os.getenv('FABRIC_USERNAME')
        self.config['fabric_pass'] = args.password or os.getenv('FABRIC_PASSWORD')
        self.config['fabric_name'] = args.username or os.getenv('FABRIC_NAME')
        self.config['debug'] = args.debug or os.getenv('DEBUG') or 0
        
        return self.config

    def get(self, key, default=None):
        """
        Get a configuration value by key.
        """
        return self.config.get(key, default)