import csv
import logging
import os
import re
from typing import Optional, Set
from urllib.parse import urljoin

import requests

from search_gov_crawler.scrapy_scheduler import CRAWL_SITES_FILE
from search_gov_crawler.search_gov_spiders.crawl_sites import CrawlSites

log = logging.getLogger(__name__)


def write_dict_to_csv(data: dict, filename: str, overwrite: bool = False):
    """
    Writes a dictionary to a CSV file with headers:
    'starting_urls' and 'sitemap_urls'.

    If overwrite is True, the file will be overwritten and include the header.
    If overwrite is False, the data will be appended without a header.

    Args:
        data (dict): Dictionary with string keys and values.
        filename (str): Name of the output CSV file (without .csv extension).
        overwrite (bool): Whether to overwrite the file or append to it.
    """
    filepath = filename if filename.endswith(".csv") else f"{filename}.csv"
    file_exists = os.path.exists(filepath)

    mode = "w" if overwrite else "a"
    write_header = overwrite or (not file_exists)

    with open(filepath, mode=mode, newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if write_header:
            writer.writerow(["starting_urls", "sitemap_urls"])
        for key, value in data.items():
            writer.writerow([key, value])


class SitemapFinder:
    def __init__(self):
        self.common_sitemap_names = [
            "sitemap.xml",
            "wp-sitemap.xml",
            "page-sitemap.xml",
            "tag-sitemap.xml",
            "category-sitemap.xml",
            "sitemap1.xml",
            "post-sitemap.xml",
            "sitemap_index.xml",
            "sitemap-index.xml",
            "sitemapindex.xml",
        ]

        self.timeout_seconds = 5

    def _join_base(self, base_url: str, sitemap_path: str):
        if not sitemap_path.startswith(("http://", "https://")):
            return urljoin(base_url, sitemap_path)
        return sitemap_path

    def _fix_http(self, url: str):
        url = url.strip()
        if url.startswith(("http://")):
            return url.replace("http://", "https://")
        return url

    def find(self, base_url) -> Set[str]:
        """
        Find sitemap URL using multiple methods.
        Returns a set of all successful sitemap URLs found.
        """
        base_url = base_url if base_url.endswith("/") else f"{base_url}/"
        if not base_url.startswith(("http://", "https://")):
            base_url = f"https://{base_url}"

        sitemap_urls: list[str] = []
        
        # Method 1: Try common sitemap locations
        sitemap_urls.extend(self._check_common_locations(base_url))

        # Method 2: Check robots.txt
        sitemap_urls.extend(self._check_robots_txt(base_url))

        # Method 3: Check HTML source
        sitemap_urls.extend(self._check_html_source(base_url))

        # Method 4: Check XML sitemaps in root directory
        sitemap_urls.extend(self._check_xml_files_in_root(base_url))

        return set(sitemap_urls)

    def confirm_sitemap_url(self, url: Optional[str]) -> bool:
        """
        Uses a HEAD request to confirm if a URL is likely a sitemap.

        This function checks for two conditions without downloading the body:
        1.  The URL returns a 200 OK status code.
        2.  The response's Content-Type header indicates XML (e.g., 'application/xml').

        Args:
            url (str): The sitemap URL to check.

        Returns:
            bool: True if the URL headers suggest a valid sitemap, False otherwise.
        """
        if not url:
            return False
        try:
            # A HEAD request gets headers without downloading the full content.
            response = requests.head(
                url,
                timeout=self.timeout_seconds,
                allow_redirects=True
            )
            if response.status_code != 200:
                return False

            content_type = response.headers.get("Content-Type", "").lower()
            if "xml" not in content_type:
                return False
        except Exception:
            return False

        return True

    def _check_common_locations(self, base_url: str) -> list[str]:
        """Try common sitemap locations"""
        log.info(f"Method 1: Checking common sitemap locations for: {base_url}")
        sitemap_urls: list[str] = []
        for name in self.common_sitemap_names:
            potential_url = urljoin(base_url, name)
            if self.confirm_sitemap_url(potential_url):
                log.info(f"Method 1: Found sitemap at common location: {potential_url}")
                sitemap_urls.append(potential_url)
        return sitemap_urls

    def _check_robots_txt(self, base_url: str) -> list[str]:
        """Check robots.txt for Sitemap directive."""
        log.info(f"Method 2: Checking robots.txt to find sitemaps for: {base_url}")

        sitemap_urls: list[str] = []

        try:
            robots_url = urljoin(base_url, "robots.txt")
            response = requests.get(robots_url, timeout=self.timeout_seconds)

            if response.status_code == 200:
                content = response.text
                # Look for Sitemap: directive
                sitemap_matches = re.findall(r"(?i)Sitemap:\s*(https?://\S+)", content)
                if sitemap_matches:
                    sitemap_urls = [self._fix_http(sitemap) for sitemap in sitemap_matches]
                    log.info(f"Method 2: Found sitemap in robots.txt: {sitemap_urls}")
        except Exception:
            # Silent pass, since it might be found in ofther locations
            pass

        return sitemap_urls

    def _check_html_source(self, base_url: str) -> list[str]:
        """Check HTML source for sitemap references."""
        log.info(f"Method 3: Checking HTML source to find sitemaps for: {base_url}")

        sitemap_urls: list[str] = []

        try:
            response = requests.get(base_url, timeout=self.timeout_seconds)
            if response.status_code == 200:
                html_content = response.text

                # Look for sitemap in link tags
                link_pattern = r"<link[^>]*rel=[\"'](?:sitemap|alternate)[\"'][^>]*href=[\"']([^\"']+)[\"']"
                matches = re.findall(link_pattern, html_content, re.IGNORECASE) or []
                if matches:
                    sitemap_urls = sitemap_urls + matches
                    log.info(f"Method 3: Found {len(matches)} sitemaps in HTML link tags")

                # Look for any .xml files that might be sitemaps
                xml_pattern = r"href=[\"']([^\"']*sitemap[^\"']*\.xml)[\"']"
                matches = re.findall(xml_pattern, html_content, re.IGNORECASE)
                if matches:
                    sitemap_urls = sitemap_urls + matches
                    log.info(f"Method 3: Found {len(matches)} sitemaps reference in raw HTML")
                
                sitemap_urls = [self._fix_http(self._join_base(base_url, sitemap)) for sitemap in sitemap_urls]
                sitemap_urls = [sitemap for sitemap in sitemap_urls if self.confirm_sitemap_url(sitemap)]

        except Exception:
            # Silent pass, since it might be found in ofther locations
            pass

        return sitemap_urls

    def _check_xml_files_in_root(self, base_url: str) -> list[str]:
        """
        Last resort: Sometimes web servers allow directory listing.
        Check if we can find XML files that might be sitemaps.
        """
        log.info(f"Method 4: Checking for XML files in root directory to find sitemaps for: {base_url}")

        sitemap_urls: list[str] = []
        try:
            response = requests.get(base_url, timeout=self.timeout_seconds)
            if response.status_code == 200:
                html_content = response.text

                # Look for XML files that might be sitemaps
                xml_pattern = r"href=[\"']([^\"']+\.xml)[\"']"
                matches = re.findall(xml_pattern, html_content, re.IGNORECASE)

                for match in matches:
                    if "sitemap" in match.lower():
                        sitemap_url = urljoin(base_url, match)
                        if self.confirm_sitemap_url(sitemap_url):
                            log.info(f"Method 4: Found potential sitemap XML in directory: {sitemap_url}")
                            sitemap_urls.append(sitemap_url)

        except Exception:
            # Silent pass, since we already catch this exception outside
            pass

        return sitemap_urls


def create_sitemaps_csv(csv_filename: str, batch_size: int = 10):
    """
    Finds sitemap URLs for *all* domains in 'CRAWL_SITES_FILE' file,
    and saves it in 'csv_filename'

    Args:
        csv_filename (str): The name of the file/directory where you want to save the CSV file
        batch_size (int): (internal) Batch size to stream save the URLs
    """
    log.info(f"Creating CSV file: {csv_filename} sorced from CRAWL_SITES_FILE: {CRAWL_SITES_FILE}")
    records = CrawlSites.from_file(file=CRAWL_SITES_FILE)
    sitemap_finder = SitemapFinder()

    sitemap_dict = {}
    count = 1

    write_dict_to_csv(sitemap_dict, csv_filename, True)
    for record in records:
        starting_url = record.starting_urls.split(",")[0]

        if record.sitemap_urls and len(record.sitemap_urls) > 0:
            for sitemap_url in record.sitemap_urls:
                if not sitemap_finder.confirm_sitemap_url(sitemap_url):
                    log.error(f"Failed to get existing sitemap_url: {sitemap_url} for: {starting_url}")        
        else:
            try:
                record.sitemap_urls = list(sitemap_finder.find(starting_url))
                if record.sitemap_urls and len(record.sitemap_urls) > 0:
                    log.info(f"Found sitemap_urls: {record.sitemap_urls} for starting_url: {starting_url}")
                else:
                    log.warning(f"Failed to find sitemap_urls for starting_url: {starting_url}")
            except Exception as e:
                log.warning(f"Failed to find sitemap_urls for starting_url: {starting_url}.", f"Reason: {e}")

        sitemap_dict[starting_url] = record.sitemap_urls
        if count % batch_size == 0:
            write_dict_to_csv(sitemap_dict, csv_filename)
            sitemap_dict = {}
        count += 1

    # save remaining items that did not hit batch_size mod
    write_dict_to_csv(sitemap_dict, csv_filename)
    log.info(f"Completed CSV file: {csv_filename} sorced from CRAWL_SITES_FILE: {CRAWL_SITES_FILE}")


if __name__ == "__main__":
    create_sitemaps_csv("all_production_sitemaps.csv")
