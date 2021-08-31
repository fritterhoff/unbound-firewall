# %%
import datetime
import ipaddress
import json
import re
import requests
import subprocess
import os
import csv
import socket


class UnboundDownloader(object):
    __location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

    unbound_conf_dir = "/etc/unbound/"
    ip_range_lists = {}
    categories = {}
    category_domains = {}
    header = ""
    ip_regex = r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"

    def _format_domain(self, domain: bytes) -> (str, bool):
        domain = str(domain, "utf-8").strip()
        # Ignore comments and emtpy lines
        if domain.startswith("#") or len(domain) == 0:
            return None, False

        # Split the lines at spaces, tabs, ... and handle a prefixed ip adress
        parts = re.split(r"\s+", domain)
        if len(parts) >= 2:
            if re.match(self.ip_regex, parts[0]):
                domain = parts[1]

        # Remove trailing comments
        domain = domain.split("#")[0]
        if len(domain) != 0:
            return domain.strip().lstrip('.'), True
        return None, False

    def _format_ipv4(self, ip_range: bytes) -> (str, bool):
        ip_range = str(ip_range, "utf-8").strip()
        if ip_range.startswith("#") or ip_range.startswith(";"):
            return ip_range, False
        ip_range = ip_range.split(";")[0].strip()
        try:
            _ = ipaddress.ip_network(ip_range)

            parts = re.split(r"[./]", ip_range)
            data = ""
            for idx in range(len(parts)):
                item = parts[len(parts) - idx - 1]
                data += item + "."
            data += "rpz-ip"
            return data, True
        except ValueError:
            return None, False

    def _format_ipv6(self, ip_range: bytes) -> (str, bool):
        ip_range = str(ip_range, "utf-8").strip()
        if ip_range.startswith("#") or ip_range.startswith(";"):
            return None, False
        ip_range = ip_range.split(";")[0].strip()
        try:
            _ = ipaddress.ip_network(ip_range)
            parts = ip_range.split("/")

            data = parts[1]
            parts[0] = parts[0].replace("::", ":zz:")
            parts = parts[0].split(":")
            for idx in range(len(parts)):
                item = parts[len(parts) - idx - 1]
                if len(item) != 0:
                    data += item
                data += "."
            data += "rpz-ip"
            return data, True
        except ValueError:
            return None, False

    def _read_providers(self, filename: str) -> (dict, list):
        with open(filename) as file:
            content = json.load(file)
        file_source = content["domain_categories_source"]
        file_categories = content["domain_categories"]
        file_ip_range_lists = content["ip_range_lists"]
        return file_source, file_categories, file_ip_range_lists

    def prepareDatasets(self):

        source, self.categories, self.ip_range_lists = self._read_providers(os.path.join(self.__location__, "providers.json"))

        lists = requests.get(source).iter_lines()
        for item in lists:
            csv_reader = csv.reader([str(item, "utf-8")])
            for row in csv_reader:
                if row[1] == "tick":
                    for _, data in self.categories.items():
                        if data["description"] == row[0]:
                            if "providers" not in data:
                                data["providers"] = []
                            data["providers"].append(row[4])
                            break

        for category_id, data in self.categories.items():
            parsedDomains = set()
            self.category_domains[category_id] = set()
            for provider in data["providers"]:
                try:
                    domains = requests.get(provider).iter_lines()
                    for domain in domains:
                        domain, ok = self._format_domain(domain)
                        if ok:
                            parsedDomains.add(domain)
                except Exception:
                    print(f"Handling {provider} failed")
            parsedDomains = sorted(parsedDomains)
            target = self.categories[category_id]["target"]
            for domain in parsedDomains:
                self.category_domains[category_id].add(f"{domain} CNAME {target}")

        with open(os.path.join(self.__location__, "./zone_template")) as file:
            self.header = file.read().replace("{SERIAL}", datetime.datetime.now().strftime("%Y%m%d%H")).replace("{HOSTNAME}", socket.getfqdn())

    def domain_data(self):
        for category_combination in range(len(self.categories)):
            description = self.categories[str(category_combination)]["description"]

            file_header = self.header.replace("{ZONE}", f"{description}")
            description = str.lower(description).replace(" ", "-")
            file_path = os.path.join(self.unbound_conf_dir, f"rpz.{description}.zone")
            domains = "\n".join(self.category_domains[str(category_combination)]) + "\n"

            # Ensure that the content is different. Otherwise changes can be prevented.
            if os.path.exists(file_path):
                with open(file_path, "r") as file:
                    present = file.read()
                    present = present[len(file_header):]
                    if present == domains:
                        print(f"Content of type {description} is unchanged -> Leaving file unchanged")
                        continue

            with open(file_path, "w") as file:
                file.write(file_header)
                file.write(domains)

    def ip_data(self):
        # Spamhaus IP LIST
        ip_range_header = self.header.replace("{ZONE}", "block.ip_range")
        with open(self.unbound_conf_dir + "rpz.ip-range.zone", "w+") as file:
            file.write(ip_range_header)
            ips = []
            for ip_range_list in self.ip_range_lists["lists"]:
                ip_ranges = requests.get(ip_range_list).iter_lines()
                # Pick correct format function
                format_ip = self._format_ipv6 if "v6" in ip_range_list else self._format_ipv4
                for ip_range in ip_ranges:
                    ip_range, ok = format_ip(ip_range)
                    if ok:
                        ips.append(ip_range)

            maxLength = len(max(ips, key=len))
            for ip in ips:
                file.write(f'{ip:{maxLength}} CNAME {self.ip_range_lists["target"]}\n')


if __name__ == "__main__":
    dl = UnboundDownloader()
    dl.prepareDatasets()
    dl.ip_data()
    dl.domain_data()
# %%
