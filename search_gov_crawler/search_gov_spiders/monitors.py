from pathlib import Path
from spidermon import MonitorSuite
from spidermon.contrib.actions.email.ses import SendSESEmail
from spidermon.contrib.actions.reports.files import CreateFileReport
from spidermon.contrib.scrapy.monitors.monitors import (
    ItemCountMonitor,
    UnwantedHTTPCodesMonitor,
    PeriodicItemCountMonitor,
    PeriodicExecutionTimeMonitor,
)


class CreateCustomFileReport(CreateFileReport):
    template_paths = [Path(__file__).parent / "actions"]


class SpiderCloseMonitorSuite(MonitorSuite):
    """
    These monitors will only run once when the spider is closed. These will compare the "items_scraped_count" to SPIDERMON_MIN_ITEMS. If the items_scraped_count is less than SPIDERMON_MIN_ITEMS it will count as a failure. From testing the smallest site with a dpeth of 2 returned 10 items. Therefore we expect at least 10 items from a site. UnwantedHTTPCodesMonitor checks the count of the unwanted http codes (SPIDERMON_UNWANTED_HTTP_CODES). If any of those codes have a count higher than SPIDERMON_UNWANTED_HTTP_CODES_MAX_COUNT it will count as a failure.

    A failed action will create a report which will be saved in the search_gov_crawler directory and sent to SPIDERMON_EMAIL_TO using Amazon SES.

    SPIDERMON_MIN_ITEMS, SPIDERMON_UNWANTED_HTTP_CODES, SPIDERMON_UNWANTED_HTTP_CODES_MAX_COUNT, SPIDERMON_EMAIL_TO values are all defined in search_gov_crawler/search_gov_spiders/settings.py
    """

    monitors = [ItemCountMonitor, UnwantedHTTPCodesMonitor]

    monitors_failed_actions = [CreateCustomFileReport, SendSESEmail]


class PeriodicMonitorSuite(MonitorSuite):
    """
    These monitors run once every SPIDERMON_TIME_INTERVAL (found in settings). The PeriodicItemCountMonitor looks that the "items_scraped_count" has increased by at least SPIDERMON_ITEM_COUNT_INCREASE each interval. The PeriodicExecutionTimeMonitor checks that the spider has not been running longer than SPIDERMON_MAX_EXECUTION_TIME.

    A failed action will create a report which will be saved in the search_gov_crawler directory and sent to SPIDERMON_EMAIL_TO using Amazon SES.

    SPIDERMON_TIME_INTERVAL,SPIDERMON_ITEM_COUNT_INCREASE and SPIDERMON_MAX_EXECUTION_TIME values are all defined in search_gov_crawler/search_gov_spiders/settings.py
    """

    monitors = [PeriodicItemCountMonitor, PeriodicExecutionTimeMonitor]

    monitors_failed_actions = [CreateCustomFileReport, SendSESEmail]
