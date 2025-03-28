import csv
import os
from pathlib import Path
from typing import Dict

day_names = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]

def generate_cron_expressions(current_expression: int, total_expressions: int  = 30):
    """
    Generate a cron expression that's evenly spread throughout the week.
    
    :param current_expression: Current expression number
    :param total_expressions: Total expressions expected (does not need to be exact)
    :return: Cron expression as strings.
    """

    minute_offset = min(round(current_expression * 10080 / total_expressions), 10080 - 1)
    day_of_week_num = minute_offset // 1440
    day_of_week = day_names[day_of_week_num]
    minute_of_day = minute_offset % 1440
    hour = minute_of_day // 60
    minute = minute_of_day % 60

    return f"{minute} {hour} * * {day_of_week}"

def convert_to_libsonnet(options):
    """
    Convert a CSV file to a .libsonnet file, that can then be copy-pasted into
    its respective .libsonnet file (like: domains_elasticsearch.libsonnet)
    Args:
        options (dict): Dictionary containing:
            - file_name (str): Path to the input CSV file
            - column_index (dict): Mapping of field names to CSV column indices, eg:
                "name": 1, #The name that will be in the name field
                "affiliate": 2, #The affiliate name that will be part of the name field
                "allowed_domains": 3, #Will go into the allowed domains field, www. will be stripped
            - depth_limit (int): Crawl depth limit for all entries
    """

    ROOT_DIR = Path(__file__).parent

    with open(ROOT_DIR / options["file_name"], "r", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        
        # Skips the header row, though might not always have a header depending on 
        # how you exported it from google sheets (or SuperAdmin)
        next(reader)
        
        items: list[str] = []
        unique_map: Dict[str, bool] = {}
        rows = []

        for row in reader:
            name: str = row[options["column_index"]["name"]]
            name = name.replace("'", "\\'") # since we use single quotes in our libsonnet files
            affiliate: str = row[options["column_index"]["affiliate"]]
            allowed_domains: str = row[options["column_index"]["allowed_domains"]]
            starting_urls: str = f"https://{allowed_domains}/"

            if allowed_domains.startswith("www."):
                allowed_domains = allowed_domains[4:]

            if allowed_domains in unique_map:
                print(f"Found a duplicate of: {allowed_domains}")
                continue
            
            unique_map[allowed_domains] = True
            
            rows.append({
                "name": name,
                "affiliate": affiliate,
                "allowed_domains": allowed_domains,
                "starting_urls": starting_urls,
                "depth_limit": options["depth_limit"],
            })
        
        # We need to do this in a seperate loop since we need the exact number of expected items.
        # There's no way to get it from the byte reader since the head can not go back/re-read
        rows_length = len(rows)
        for index, row in enumerate(rows):
            name = row.get("name")
            affiliate = row.get("affiliate")
            allowed_domains = row.get("allowed_domains")
            depth_limit = row.get("depth_limit")
            starting_urls = row.get("starting_urls")
            schedule = generate_cron_expressions(index, rows_length)
            
            jsonnet_array_item = \
f"""  {{
    name: '{name} ({affiliate})',
    config: DomainConfig(allowed_domains='{allowed_domains}',
                         starting_urls='{starting_urls}',
                         schedule='{schedule}',
                         output_target=output_target,
                         depth_limit={depth_limit}),
  }}"""

            items.append(jsonnet_array_item)
        
        objects_str = ",\n".join(items)
        libsonnet_str = f"[\n{objects_str}\n]"
        
        output_file = os.path.splitext(options["file_name"])[0] + ".libsonnet"
        
        with open(ROOT_DIR / output_file, "w", encoding="utf-8") as f:
            f.write(libsonnet_str)


if __name__ == "__main__":
    options = {
        "file_name": "Bing Transition Batches  - Batch 7.csv",
        "column_index": {
            "name": 1,
            "affiliate": 2,
            "allowed_domains": 3,
        },
        "depth_limit": 8,
    }
    
    convert_to_libsonnet(options)
