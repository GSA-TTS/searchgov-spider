import json
import sys
from collections import defaultdict
from pathlib import Path


def clean_schedule_time(time: str) -> str:
    """Clean the schedule time string to a standard format."""
    minute, hour, *_ = time.split(" ")
    return f"{hour:0>2}:{minute:0>2}"


def expand_day_name(day: str) -> str:
    """Expand day abbreviations to full names."""

    match day.lower().strip():
        case "sun":
            return "Sunday"
        case "mon":
            return "Monday"
        case "tue":
            return "Tuesday"
        case "wed":
            return "Wednesday"
        case "thu":
            return "Thursday"
        case "fri":
            return "Friday"
        case "sat":
            return "Saturday"
        case _:
            msg = "Invalid day abbreviation: {day}"
            raise ValueError(msg)


def transform_schedule(raw_schedule: dict) -> defaultdict:
    """Transform the raw schedule into a more usable format."""

    transformed_schedule = defaultdict(list)
    for entry in raw_schedule:
        schedule = entry["schedule"]
        schedule_time, _, schedule_day, *_ = schedule.split("*")
        day = expand_day_name(schedule_day)
        entry["time"] = clean_schedule_time(schedule_time)
        transformed_schedule[day].append(entry)

    # Sort the schedule by time
    for day, entries in transformed_schedule.items():
        transformed_schedule[day] = sorted(entries, key=lambda x: x["time"])

    return transformed_schedule


def create_markdown_tables(transformed_schedule: dict) -> str:
    """Create a markdown table for the given day and data."""
    days_of_week = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")

    md_tables = ""
    for day in days_of_week:
        entries = transformed_schedule[day]
        md_tables += f"\n\n## {day} ({len(entries)})\n|Name|Time (UTC)|Allowed Domains|JS|Depth|Deny Paths|\n"
        md_tables += "|---|---|---|---|---|---|\n"
        for entry in entries:
            name = entry["name"]
            schedule = entry["time"]
            allowed_domains = entry["allowed_domains"]
            js = "Y" if entry["handle_javascript"] else "N"
            depth = entry["depth_limit"]
            deny_paths = ",".join(entry["deny_paths"]) if entry["deny_paths"] else ""
            row = f"|{name}|{schedule}|{allowed_domains}|{js}|{depth}|{deny_paths}|\n"
            md_tables += row

    return md_tables


def create_header_and_toc(environment: str, transformed_schedule: dict) -> tuple[str, str]:
    """Generate the header and table of contents for the markdown file."""

    header = f"# {environment.capitalize()} Schedule\n"

    toc = ""
    days_of_week = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
    for day in days_of_week:
        daily_entries = len(transformed_schedule[day])
        toc += f" * [{day} ({daily_entries})](#{day.lower()}-{daily_entries})\n"

    return header, toc


def create_markdown_schedule(input_file: Path) -> None:
    """Create a markdown schedule file from the input JSON file."""
    with input_file.open("r", encoding="utf-8") as f:
        raw_schedule = json.load(f)

    if not raw_schedule:
        print(f"Error: {input_file} is empty or not a valid JSON file.")

    transformed_schedule = transform_schedule(raw_schedule)

    environment = input_file.stem.split("-")[2]
    header, toc = create_header_and_toc(environment, transformed_schedule)
    schedule_tables = create_markdown_tables(transformed_schedule)

    output_file = input_file.with_suffix(".md")

    with output_file.open("w", encoding="utf-8") as f:
        f.write(header)
        f.write(toc)
        f.write(schedule_tables)

    print(f"Generated markdown schedule {output_file.name} based on {input_file.name}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        schedule_file = Path(sys.argv[1]).resolve()
        create_markdown_schedule(schedule_file)
    else:
        domains_dir = Path(__file__).parent
        schedule_filenames = ["crawl-sites-development.json", "crawl-sites-staging.json", "crawl-sites-production.json"]
        for schedule_filename in schedule_filenames:
            schedule_file = domains_dir / schedule_filename
            create_markdown_schedule(schedule_file)
