# **Fabrics2DCIM** 
### Imports Devices, Interfaces, LAGS, VLANS, IP Addresses, and Connections to other devices to DCIM

## Fabrics:

### BigSwitch Converged Fabric / Arista Converged Cloud Fabric (In progress)
### Cisco Nexus ACI  (In progress)

## DCIM/DDI:

### Netbox 4 (maybe older, havent tested)
### Nautobot (probably, need to test API is still the same)

```bash
cp .env.example to .env
[ ! -f .env ] || export $(grep -v '^#' .env | xargs)
./fabric2dcim.py
```

or command line:

```bash
usage: fabric2dcim.py [-h] [--fabric-type FABRIC_TYPE] [--fabric-url FABRIC_URL] [--username USERNAME] [--password PASSWORD] [--netbox-url NETBOX_URL]
                      [--netbox-token NETBOX_TOKEN]

Sync network fabric information to NetBox

optional arguments:
  -h, --help            show this help message and exit
  --fabric-type FABRIC_TYPE
                        Fabric type (bigswitch or cisco-aci) (FABRIC_TYPE environment variable)
  --fabric-url FABRIC_URL
                        Fabric controller URL (FABRIC_URL environment variable)
  --username USERNAME   Fabric username (FABRIC_USERNAME environment variable)
  --password PASSWORD   Fabric password (FABRIC_PASSWORD environment variable)
  --netbox-url NETBOX_URL
                        NetBox URL (NETBOX_URL environment variable)
  --netbox-token NETBOX_TOKEN
                        NetBox API token (NETBOX_TOKEN environment variable)

```