"""Define your item pipelines here
Don't forget to add your pipeline to the ITEM_PIPELINES setting
See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
"""

import os
from scrapy.exceptions import DropItem


class SearchGovSpidersPipeline:
    """
    Class for pipeline that takes items and adds them
    to output file with a max size of 3.9MB
    """

    current_file_size = 0
    file_number = 1
    base_path_name = "output/all-links.csv"
    max_file_size = 3900
    PAGINATE = True

    def process_item(self, item, _spider):
        """Checks that the file is not at max size.
        Adds it to the file if less, or creates a new file if too large."""
        short_file = open(self.base_path_name, "w", encoding="utf-8")
        line = item["url"]
        self.current_file_size += 1
        next_file_size = self.current_file_size + len(line)
        if self.PAGINATE and next_file_size > self.max_file_size:
            short_file.close()
            new_name = "output/all-links" + str(self.file_number) + ".csv"
            os.rename(self.base_path_name, new_name)
            self.file_number = self.file_number + 1
            short_file = open(self.base_path_name, "w", encoding="utf-8")
            self.current_file_size = 0

        short_file.write(line)
        short_file.write("\n")
        self.current_file_size = self.current_file_size + len(line)

        return item


class DeDeuplicatorPipeline:
    """Class for pipeline that removes duplicate items"""

    itemlist = []

    def process_item(self, item, spider):
        """Checks that the file is not at max size.
        Adds it to the file if less, or creates a new file if too large."""
        if item in self.itemlist:
            raise DropItem("already in list")
        self.itemlist.append(item)

        return item
