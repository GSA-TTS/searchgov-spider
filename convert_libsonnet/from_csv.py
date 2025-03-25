import csv
import os
from pathlib import Path

def convert_to_libsonnet(options):
    """
    Convert a CSV file to a .libsonnet file, that can then be copy-pasted into
    its respective .libsonnet file (like: domains_elasticsearch.libsonnet)
    Args:
        options (dict): Dictionary containing:
            - file_name (str): Path to the input CSV file
            - column_index (dict): Mapping of field names to CSV column indices
            - depth_limit (int): Crawl depth limit for all entries
            - schedule (str): Cron expression for scheduling
    """

    ROOT_DIR = Path(__file__).parent

    with open(ROOT_DIR / options["file_name"], "r", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        
        # Skips the header row, though might not always have a header depending on 
        # how you exported it from google sheets (or SuperAdmin)
        next(reader)
        
        items = []
        unique_map = {}
        
        for row in reader:
            name: str = row[options["column_index"]["name"]]
            name = name.replace("'", "\\'") # since we use single quotes in our libsonnet files
            affiliate: str = row[options["column_index"]["affiliate"]]
            allowed_domains: str = row[options["column_index"]["allowed_domains"]]

            if allowed_domains in unique_map:
                print(f"Found a duplicate of: {allowed_domains}")
                continue
            
            unique_map[allowed_domains] = True
            schedule = options["schedule"]
            depth_limit = options["depth_limit"]
            
            jsonnet_array_item = \
f"""  {{
    name: '{name} ({affiliate})',
    config: DomainConfig(allowed_domains='{allowed_domains}',
                         starting_urls='https://{allowed_domains}/',
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
        "schedule": "30 20 * * FRI",
    }
    
    convert_to_libsonnet(options)