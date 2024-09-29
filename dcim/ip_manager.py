

class IPManager:
    def __init__(self):
        # Temporary storage for IPs to be assigned
        self.ip_addresses_to_assign = {}

    def store_ip_for_device(self, device_name, primary_ip4, primary_ip6):
        self.ip_addresses_to_assign[device_name] = {
            'primary_ip4': primary_ip4,
            'primary_ip6': primary_ip6
        }

    def assign_ip_to_interface(self, interface_data, netbox_instance):
        device_name = interface_data['device']['name']
        interface_ip = interface_data.get('ip_address')

        # Check if this device has stored IPs to assign
        if device_name in self.ip_addresses_to_assign:
            primary_ips = self.ip_addresses_to_assign[device_name]

            if interface_ip == primary_ips.get('primary_ip4'):
                print(f"Assigning primary_ip4 to interface: {interface_data['name']}")
                netbox_ip = netbox_instance.ipam.ip_addresses.get(address=interface_ip)
                netbox_ip.update({'assigned_object_id': interface_data['id']})

            if interface_ip == primary_ips.get('primary_ip6'):
                print(f"Assigning primary_ip6 to interface: {interface_data['name']}")
                netbox_ip = netbox_instance.ipam.ip_addresses.get(address=interface_ip)
                netbox_ip.update({'assigned_object_id': interface_data['id']})

    def update_device_with_primary_ips(self, netbox_instance):
        for device_name, ips in self.ip_addresses_to_assign.items():
            device = netbox_instance.dcim.devices.get(name=device_name)
            if ips['primary_ip4']:
                device.update({
                    'primary_ip4': netbox_instance.ipam.ip_addresses.get(address=ips['primary_ip4'])
                })
            if ips['primary_ip6']:
                device.update({
                    'primary_ip6': netbox_instance.ipam.ip_addresses.get(address=ips['primary_ip6'])
                })
            print(f"Updated device {device.name} with primary IPs")
