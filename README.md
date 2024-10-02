# **Fabric2DCIM** 
### Imports Devices, Interfaces, LAGS, VLANS, IP Addresses, and Connections to other devices to DCIM

## Fabrics:

#### BigSwitch Converged Fabric / Arista Converged Cloud Fabric (In progress)
#### Cisco Nexus ACI (In progress)

## DCIM:

#### Netbox 4 (maybe older, havent tested)
#### Nautobot (probably, need to test API is still the same)

## Installation:
```
git clone https://github.com/erichester76/fabric2dcim.git
pip install -r requirements.txt
```
## Usage:
```
cp .env.example to .env 
vi .env (adjust variables to your setup)
set -a            
source .env
set +a
./fabric2dcim
```
#### or command line:
usage: fabric2dcim [-h] [--fabric-type FABRIC_TYPE] [--fabric-url FABRIC_URL] [--fabric-name FABRIC_NAME] [--username USERNAME] [--password PASSWORD] [--netbox-url NETBOX_URL] [--netbox-token NETBOX_TOKEN]
                   [--netbox-site NETBOX_SITE] [--cache-filename CACHE_FILENAME] [--cache-timeout CACHE_TIMEOUT] [--debug DEBUG]

Sync network fabric information to NetBox

optional arguments:
  -h, --help            show this help message and exit
  --fabric-type FABRIC_TYPE
                        Fabric type (bigswitch or cisco-aci) (FABRIC_TYPE environment variable)
  --fabric-url FABRIC_URL
                        Fabric controller URL (FABRIC_URL environment variable)
  --fabric-name FABRIC_NAME
                        Fabric controller name (FABRIC_URL environment variable)
  --username USERNAME   Fabric username (FABRIC_USERNAME environment variable)
  --password PASSWORD   Fabric password (FABRIC_PASSWORD environment variable)
  --netbox-url NETBOX_URL
                        NetBox URL (NETBOX_URL environment variable)
  --netbox-token NETBOX_TOKEN
                        NetBox API token (NETBOX_TOKEN environment variable)
  --netbox-site NETBOX_SITE
                        NetBox site name to use (NETBOX_SITE environment variable)
  --cache-filename CACHE_FILENAME
                        Cache Netbox data to Filename (CACHE_FILENAME environment variable)
  --cache-timeout CACHE_TIMEOUT
                        Cache file timeout (CACHE_FILE_TIMEOUT environment variable)
  --debug DEBUG         Show Debug output (DEBUG environment variable)NetBox API token (NETBOX_TOKEN environment variable)

```