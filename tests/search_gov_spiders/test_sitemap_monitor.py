import unittest
import tempfile
import shutil
import hashlib
import requests
from pathlib import Path
from unittest.mock import patch, MagicMock
from search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor import (
    SitemapMonitor,
    create_directory
)


class MockCrawlSite:
    def __init__(self, starting_urls, sitemap_url=None, depth_limit=8, check_sitemap_hours=48, **kwargs):
        self.starting_urls = starting_urls
        self.sitemap_url = sitemap_url
        self.depth_limit = depth_limit
        self.check_sitemap_hours = check_sitemap_hours


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        p = patch(
            "search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.TARGET_DIR",
            Path(self.temp_dir)
        )
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)


class TestCreateDirectory(unittest.TestCase):
    def setUp(self):
        self.base_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(self.base_dir))

    def test_create_new(self):
        target = self.base_dir / "foo"
        create_directory(target)
        self.assertTrue(target.is_dir())

    def test_idempotent(self):
        target = self.base_dir / "bar"
        target.mkdir()
        create_directory(target)
        self.assertTrue(target.is_dir())


class TestSitemapMonitor(BaseTestCase):
    def make_records(self, depths):
        return [
            MockCrawlSite(starting_urls=f"http://example{i}.com",
                          sitemap_url="http://example.com/sitemap.xml",
                          depth_limit=d)
            for i, d in enumerate(depths)
        ]

    @patch("search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.SitemapFinder")
    def test_filter_records(self, MockSitemapFinder):
        MockSitemapFinder.return_value.find.return_value = "sitemap.xml"
        MockSitemapFinder.return_value.confirm_sitemap_url.return_value = True

        # depths 7,8,9 should keep only >=8
        records = self.make_records([7, 8, 9])
        monitor = SitemapMonitor(records)

        self.assertEqual(len(monitor.records), 2)
        self.assertEqual(
            [r.starting_urls for r in monitor.records],
            ["http://example1.com", "http://example2.com"]
        )

    @patch("search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.SitemapFinder")
    def test_save_sitemap(self, MockSitemapFinder):
        MockSitemapFinder.return_value.confirm_sitemap_url.return_value = True
        monitor = SitemapMonitor([
            MockCrawlSite("http://example.com", sitemap_url="http://example.com/sitemap.xml")
        ])

        urls = {"http://example.com/a", "http://example.com/b"}
        monitor._save_sitemap("http://example.com/sitemap.xml", urls)

        # verify file contents
        h = hashlib.md5(b"http://example.com/sitemap.xml").hexdigest()
        path = Path(self.temp_dir) / f"{h}.txt"
        with open(path) as f:
            saved = {l.strip() for l in f}
        self.assertSetEqual(saved, urls)

    @patch("requests.Session")
    def test_fetch_sitemap_success(self, MockSession):
        xml = b"""<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                    <url><loc>http://ex.com/1</loc></url>
                    <url><loc>http://ex.com/2</loc></url>
                 </urlset>"""
        sess = MagicMock()
        resp = MagicMock(status_code=200, content=xml)
        sess.get.return_value = resp
        MockSession.return_value.__enter__.return_value = sess

        monitor = SitemapMonitor([])
        result = monitor._fetch_sitemap("http://ex.com/sitemap.xml")

        MockSession.assert_called_once()
        sess.headers.update.assert_called_once_with({"Cache-Control": "no-cache"})
        self.assertTrue(sess.cache_disabled)
        sess.get.assert_called_once_with("http://ex.com/sitemap.xml", timeout=30)
        self.assertSetEqual(result, {"http://ex.com/1", "http://ex.com/2"})

    @patch("requests.Session")
    def test_fetch_sitemap_error(self, MockSession):
        sess = MockSession.return_value
        sess.get.side_effect = requests.exceptions.RequestException
        monitor = SitemapMonitor([])
        self.assertSetEqual(
            monitor._fetch_sitemap("http://fake"), 
            set(),
            "Should return empty set on request errors"
        )

    @patch("search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.SitemapFinder")
    def test_check_for_changes_first_run(self, MockSitemapFinder):
        MockSitemapFinder.return_value.confirm_sitemap_url.return_value = True

        monitor = SitemapMonitor([
            MockCrawlSite("http://ex.com", sitemap_url="http://ex.com/sitemap.xml")
        ])
        # simulate first run toggle
        monitor.is_first_run["http://ex.com/sitemap.xml"] = False

        with patch.object(monitor, "_fetch_sitemap", return_value={"u1", "u2"}):
            new_urls, total = monitor._check_for_changes("http://ex.com/sitemap.xml")

        self.assertSetEqual(new_urls, {"u1", "u2"})
        self.assertEqual(total, 2)
        self.assertFalse(monitor.is_first_run["http://ex.com/sitemap.xml"])

    @patch("search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.SitemapFinder")
    def test_check_for_changes_no_new(self, MockSitemapFinder):
        MockSitemapFinder.return_value.confirm_sitemap_url.return_value = True

        monitor = SitemapMonitor([
            MockCrawlSite("http://ex.com", sitemap_url="http://ex.com/sitemap.xml")
        ])
        key = "http://ex.com/sitemap.xml"
        monitor.stored_sitemaps[key] = {"u1"}
        monitor.is_first_run[key] = False

        with patch.object(monitor, "_fetch_sitemap", return_value={"u1"}):
            new_urls, total = monitor._check_for_changes(key)

        self.assertSetEqual(new_urls, set())
        self.assertEqual(total, 1)

    @patch("search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.SitemapFinder")
    def test_check_for_changes_with_new(self, MockSitemapFinder):
        MockSitemapFinder.return_value.confirm_sitemap_url.return_value = True

        monitor = SitemapMonitor([
            MockCrawlSite("http://ex.com", sitemap_url="http://ex.com/sitemap.xml")
        ])
        key = "http://ex.com/sitemap.xml"
        monitor.stored_sitemaps[key] = {"u1"}
        monitor.is_first_run[key] = False

        with patch.object(monitor, "_fetch_sitemap", return_value={"u1", "u2"}):
            new_urls, total = monitor._check_for_changes(key)

        self.assertSetEqual(new_urls, {"u2"})
        self.assertEqual(total, 2)

    @patch("search_gov_crawler.search_gov_spiders.sitemaps.sitemap_monitor.SitemapFinder")
    def test_get_check_interval(self, MockSitemapFinder):
        MockSitemapFinder.return_value.confirm_sitemap_url.return_value = True

        rec = MockCrawlSite(
            "http://ex.com",
            sitemap_url="http://ex.com/sitemap.xml",
            check_sitemap_hours=12
        )
        monitor = SitemapMonitor([rec])
        self.assertEqual(
            monitor._get_check_interval(rec.sitemap_url),
            12 * 3600
        )
