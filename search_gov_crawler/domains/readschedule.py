import json
import sys


def read_json_file(file_path) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in: {file_path}")
        return None


def create_time(time):
    minute = time.split(" ")[0]
    hour = time.split(" ")[1]

    if len(minute) < 2:
        minute = "0" + minute

    if len(hour) < 2:
        hour = "0" + hour

    time = hour + ":" + minute
    return time


def put_into_schedule_format(data):
    unsorted_schedule = [[], [], [], [], [], [], []]
    for entry in data:
        name = entry["name"]
        schedule = entry["schedule"]
        day = schedule.split("*")[2]
        time = schedule.split("*")[0]
        time = create_time(time)
        match day.strip():
            case "MON":
                unsorted_schedule[0].append({"name": name, "time": time})
            case "TUE":
                unsorted_schedule[1].append({"name": name, "time": time})
            case "WED":
                unsorted_schedule[2].append({"name": name, "time": time})
            case "THU":
                unsorted_schedule[3].append({"name": name, "time": time})
            case "FRI":
                unsorted_schedule[4].append({"name": name, "time": time})
            case "SAT":
                unsorted_schedule[5].append({"name": name, "time": time})
            case "SUN":
                unsorted_schedule[6].append({"name": name, "time": time})
    return unsorted_schedule


def create_markdown(day, data, file_name):
    if not data:
        return ""

    md_table = f"""\n\n## {day}\n|Domain|Time (UTC)|\n|---|---|\n"""

    for entry in data:
        name = entry["name"]
        schedule = entry["time"]
        row = f"|{name}|{schedule}|\n"
        md_table = md_table + row
    write_schedule(md_table, file_name)


def write_schedule(md_table, file_path):
    file_name = file_path.split(".")[0] + ".md"
    with open(file_name, "a+", encoding="utf-8") as file:
        file.write(md_table)


def create_sorted_markdown(unsorted_schedule, file_path):
    days_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for i, schedule in enumerate(unsorted_schedule):
        day = days_names[i]
        sorted_by_time = sorted(schedule, key=lambda x: x["time"])
        create_markdown(day, sorted_by_time, file_path)


def create_markdown_schedule_file(file_path):
    env = file_path.split(".")[0]
    file_name = env + ".md"
    title = env.split("-")[-1]
    header = "# " + title.capitalize() + " Schedule\n"
    toc = " * [Monday](#monday)\n * [Tuesday](#tuesday)\n * [Wednesday](#wednesday)\n * [Thursday](#thursday)\n * [Friday](#friday)\n * [Saturday](#saturday)\n * [Sunday](#sunday)\n"

    with open(file_name, "w", encoding="utf-8") as file:
        file.write(header)
        file.write(toc)


def main(file_path):
    data = read_json_file(file_path)
    if data is not None:
        unsorted_schedule = put_into_schedule_format(data)
        create_markdown_schedule_file(file_path)
        create_sorted_markdown(unsorted_schedule, file_path)
    else:
        print(f"No data found in {file_path}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        schedules = ["crawl-sites-development.json", "crawl-sites-staging.json", "crawl-sites-production.json"]
        for json_schedule in schedules:
            main(json_schedule)
