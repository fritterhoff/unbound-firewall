# Using unbound as DNS Firewall

During my bachelor study I had to write a short term paper about DNS-Firewalls. 

This repo provides the results of this paper, containing the installation and configuration of `unbound` as a local DNS-Firewall and a script for simplified generation of RPZ zone definitions. Therefore the quite new functionality DNS-RPZ, introduced with `unbound` in version 1.10 [https://nlnetlabs.nl/news/2020/Feb/20/unbound-1.10.0-released/](nlnetlabs), is used. The blocklists are taken from the [https://firebog.net/](The Big Blocklist Collection).

# Installation

## Unbound

As mentioned before `unbound` is required in version 1.10. This version is e.g. available using [https://packages.debian.org/buster-backports/unbound](buster-backports). 

For installing unbound execute: `sudo apt install unbound`. I also strongly recommend installing the `dns-utils` package.

## Required tools for blocklist generation

The provided script `download.py` requires Python3 and the pip module `requests`. If not already installed, install python3 using `sudo apt install python3-minimal python3-pip` and install the requests package `sudo pip3 install requests`.

# Configuration

## Unbound

After installing unbound some basic configuration must be done.
Therefore, a template is provided in this repo.

1. Backup and replace the existing configuration file `/etc/unbound/unbound.conf` with the provided template.
2. Adjust the specific variables for your network. You must define the following properties:
    * `private-domain`
    * `domain-insecure`
    * `forward-addr`
3. Download the latest blocklists by executing `sudo python3 download.py` script.
4. Check the unbound configuration using `sudo unbound-checkconf`
5. Restart unbound `sudo systemctl restart unbound`

Afterwards you can check the functionality using `dig`

For example `dig @localhost www.google.de` should return a valid ip, while `dig @localhost adservice.google.de` should return the status `NXDOMAIN` and no valid ip.

## Clients & Router

So far the resolver is prepared and ready for usage. You can change the DNS-Configuration of each client or change the DHCP settings of your DHCP-Server. In a normal network this will be your router. Depending on the manufacturer, model and firmware the settings will be in different locations, so please look up the right way using the help pages matching to your hardware.

# Advanced configuration

Sometimes it can be necessary to whitelist one or more hostnames. This requires some manual changes in the configuration.

1. Uncomment the whitelist block in the `unbound.conf` 
```diff
-# rpz: 
-#  name: "rpz.whitelist.zone"
-#  zonefile: "rpz.whitelist.zone"
+ rpz: 
+  name: "rpz.whitelist.zone"
+  zonefile: "rpz.whitelist.zone"
```
2. Create a file `rpz.whitelist.zone` inside `/etc/unbound/`
3. Insert a valid zone header. This can header can copy-pasted from the other files.
4. Insert the required to be whitelisted domains pointing to the `CNAME rpz-passthru.`

    The following example will whitelist all subdomains of google.de 
    ```
    google.de CNAME rpz-passthru.
    *.google.de CNAME rpz-passthru.
    ``` 
5. Increment or adjust the zone serial so unbound detects the changes
6. Check the unbound configuration using `sudo unbound-checkconf`
7. Restart unbound `sudo systemctl restart unbound`

The changes can be checked executing `dig` as explained above.  