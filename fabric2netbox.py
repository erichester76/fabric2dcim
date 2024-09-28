#!/usr/bin/python3

import os
import argparse
import pprint
from bigswitch_fabric import BigSwitchFabric
from cisco_aci_fabric import CiscoACIFabric
from netbox_manager import NetBoxManager


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Sync network fabric information to NetBox")
    parser.add_argument('--fabric-type', type=str, help='Fabric type (bigswitch or cisco-aci) (FABRIC_TYPE environment variable)')
    parser.add_argument('--fabric-url', type=str, help='Fabric controller URL (FABRIC_URL environment variable)')
    parser.add_argument('--username', type=str, help='Fabric username (FABRIC_USERNAME environment variable)')
    parser.add_argument('--password', type=str, help='Fabric password (FABRIC_PASSWORD environment variable)')
    parser.add_argument('--netbox-url', type=str, help='NetBox URL (NETBOX_URL environment variable)')
    parser.add_argument('--netbox-token', type=str, help='NetBox API token (NETBOX_TOKEN environment variable)')
    args = parser.parse_args()
    
    # Load Environment variables if not on command line
    netbox_url = args.netbox_url or os.getenv('NETBOX_URL')
    netbox_token = args.netbox_token or os.getenv('NETBOX_TOKEN')
    fabric_type = args.fabric_type or os.getenv('FABRIC_TYPE')
    fabric_url = args.fabric_url or os.getenv('FABRIC_URL')
    fabric_user = args.username or os.getenv('FABRIC_USERNAME')
    fabric_pass = args.password or os.getenv('FABRIC_PASSWORD')
    DEBUG=os.getenv('DEBUG') or 0

    if not netbox_url or not netbox_token:
        raise ValueError("NetBox URL and token must be provided either as arguments or environment variables (--help for more)")

    if not fabric_type or not fabric_url or not fabric_user or not fabric_pass:
        raise ValueError("Must specify fabric information (type, url, user, pass) as arguments or environment variables (--help for more)")


    # Initialize the NetBox Manager
    netbox_manager = NetBoxManager(netbox_url=netbox_url, netbox_token=netbox_token)
    if netbox_manager: print(f'Connected to netbox API at {netbox_url}')
    else:
        raise ValueError(f'Failed to connect to netbox API at {netbox_url}')

    # Initialize the appropriate fabric based on the --fabric-type argument
    if fabric_type.lower() == 'bigswitch':
        fabric = BigSwitchFabric(host=fabric_url, username=fabric_user, password=fabric_pass)
    elif fabric_type.lower() == 'cisco-aci':
        fabric = CiscoACIFabric(apic_url=fabric_url, username=fabric_user, password=fabric_pass)
    else:
        raise ValueError("Unsupported fabric type. Supported values are 'bigswitch' and 'cisco-aci'.")

    # Connect to the fabric
    fabric.connect()

    # Sync switches to NetBox
    switches = fabric.get_device_inventory()
    for switch in switches:
        netbox_manager.create_device(switch)
    
    # Sync interfaces to NetBox
    switches = fabric.get_interface_inventory()
    if switches:
        for switch in switches:
           for interface in switch['interfaces']:
              netbox_manager.create_interface(interface)

    # Sync LAGs to NetBox
    lags = fabric.get_lag_inventory()
    if lags:
        for lag in lags:
            netbox_manager.create_lag(lag)

    # Sync connections (cables) to NetBox
    connections = fabric.get_connection_inventory()
    if connections:
        for connection in connections:
            netbox_manager.create_connection(connection)

if __name__ == "__main__":
    main()
