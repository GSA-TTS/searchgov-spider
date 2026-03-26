from unittest.mock import MagicMock, patch

import pytest

from search_gov_crawler.search_gov_spiders.sitemaps.sitemap_finder import (
    SitemapFinder,
    write_dict_to_csv,
)


def test_write_dict_to_csv_overwrite(mocker):
    """Test overwriting a CSV file with the dictionary data"""
    mocker.patch("os.path.exists", return_value=True)
    mock_csv_writer = mocker.patch("csv.writer")
    mock_file = mocker.patch("builtins.open")

    data = {"https://example.com": ["https://example.com/sitemap.xml"]}
    write_dict_to_csv(data, "test_file.csv", overwrite=True)

    mock_file.assert_called_once_with("test_file.csv", mode="w", newline="", encoding="utf-8")
    mock_csv_writer.return_value.writerow.assert_any_call(["starting_urls", "sitemap_urls"])
    mock_csv_writer.return_value.writerow.assert_any_call(["https://example.com", ["https://example.com/sitemap.xml"]])


def test_write_dict_to_csv_append_existing(mocker):
    """Test appending data to an existing CSV file without header"""
    mocker.patch("os.path.exists", return_value=True)
    mock_csv_writer = mocker.patch("csv.writer")
    mock_file = mocker.patch("builtins.open")

    data = {"https://example.com": ["https://example.com/sitemap.xml"]}
    write_dict_to_csv(data, "test_file.csv", overwrite=False)

    mock_file.assert_called_once_with("test_file.csv", mode="a", newline="", encoding="utf-8")
    # Header should not be written
    for call in mock_csv_writer.return_value.writerow.call_args_list:
        assert call.args[0] != ["starting_urls", "sitemap_urls"]
    mock_csv_writer.return_value.writerow.assert_called_once_with(
        ["https://example.com", ["https://example.com/sitemap.xml"]]
    )


def test_write_dict_to_csv_append_new(mocker):
    """Test appending data to a new CSV file with header"""
    mocker.patch("os.path.exists", return_value=True)
    mock_csv_writer = mocker.patch("csv.writer")
    mock_file = mocker.patch("builtins.open")

    data = {"https://example.com": ["https://example.com/sitemap.xml"]}
    write_dict_to_csv(data, "test_file.csv", overwrite=False)

    mock_file.assert_called_once_with("test_file.csv", mode="a", newline="", encoding="utf-8")
    mock_csv_writer.return_value.writerow.assert_any_call(["https://example.com", ["https://example.com/sitemap.xml"]])


def test_write_dict_to_csv_adds_extension(mocker):
    """Test that .csv extension is added if not provided"""
    mocker.patch("os.path.exists", return_value=True)
    mock_file = mocker.patch("builtins.open")

    data = {"https://example.com": ["https://example.com/sitemap.xml"]}
    write_dict_to_csv(data, "test_file", overwrite=True)

    mock_file.assert_called_once_with("test_file.csv", mode="w", newline="", encoding="utf-8")


@pytest.fixture(name="sitemap_finder")
def fixture_sitemap_finder():
    return SitemapFinder()


@pytest.fixture(name="base_url")
def fixture_base_url():
    return "https://example.com"


def test_sitemap_finder_init(sitemap_finder):
    """Test initialization of SitemapFinder"""
    assert sitemap_finder.timeout_seconds == 5
    assert "sitemap.xml" in sitemap_finder.common_sitemap_names


JOIN_BASE_TEST_CASES = [
    ("sitemap.xml", "https://example.com/sitemap.xml"),
    ("https://another-domain.com/sitemap.xml", "https://another-domain.com/sitemap.xml"),
]


@pytest.mark.parametrize(("path", "expected"), JOIN_BASE_TEST_CASES)
def test_join_base(sitemap_finder, base_url, path, expected):
    """Test joining base URL with relative path"""
    result = sitemap_finder._join_base(base_url, path)
    assert result == expected


def test_fix_http(sitemap_finder):
    """Test that http URLs are converted to https"""
    http_url = "http://example.com/sitemap.xml"
    result = sitemap_finder._fix_http(http_url)
    assert result == "https://example.com/sitemap.xml"


def test_check_common_locations_found(mocker, sitemap_finder, base_url):
    """Test finding sitemap in common locations"""
    mock_confirm = mocker.patch.object(SitemapFinder, "confirm_sitemap_url")
    mock_confirm.side_effect = lambda url: "sitemap.xml" in url

    result = sitemap_finder._check_common_locations(f"{base_url}/")
    expected_result = [
        "https://example.com/sitemap.xml",
        "https://example.com/wp-sitemap.xml",
        "https://example.com/page-sitemap.xml",
        "https://example.com/tag-sitemap.xml",
        "https://example.com/category-sitemap.xml",
        "https://example.com/post-sitemap.xml",
    ]
    assert sorted(result) == sorted(expected_result)
    assert mock_confirm.call_count == len(sitemap_finder.common_sitemap_names)


class TestSitemapFinder:
    def setup_method(self):
        self.finder = SitemapFinder()
        self.base_url = "https://example.com"

    @patch.object(SitemapFinder, "confirm_sitemap_url")
    def test_check_common_locations_not_found(self, mock_confirm):
        """Test when sitemap is not found in common locations"""
        mock_confirm.return_value = False
        result = self.finder._check_common_locations(f"{self.base_url}/")
        assert result == []
        assert mock_confirm.call_count == len(self.finder.common_sitemap_names)

    @patch("requests.get")
    def test_check_robots_txt_found(self, mock_get):
        """Test finding sitemap in robots.txt"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nSitemap: https://example.com/custom-sitemap.xml"
        mock_get.return_value = mock_response

        result = self.finder._check_robots_txt(f"{self.base_url}/")
        assert result == ["https://example.com/custom-sitemap.xml"]
        mock_get.assert_called_once_with(f"{self.base_url}/robots.txt", timeout=self.finder.timeout_seconds)

    @patch("requests.get")
    def test_check_robots_txt_not_found(self, mock_get):
        """Test when sitemap is not found in robots.txt"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *"  # No Sitemap directive
        mock_get.return_value = mock_response

        result = self.finder._check_robots_txt(f"{self.base_url}/")
        assert result == []
        mock_get.assert_called_once_with(f"{self.base_url}/robots.txt", timeout=self.finder.timeout_seconds)

    @patch("requests.get")
    def test_check_robots_txt_exception(self, mock_get):
        """Test handling exception when checking robots.txt"""
        mock_get.side_effect = Exception("Connection error")
        result = self.finder._check_robots_txt(f"{self.base_url}/")
        assert result == []
        mock_get.assert_called_once()

    @patch("requests.get")
    @patch.object(SitemapFinder, "confirm_sitemap_url", return_value=True)
    def test_check_html_source_found(self, mock_confirm, mock_get):
        """Test finding sitemaps in HTML source"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
            <html><head><link rel="sitemap" href="/sitemap1.xml"></head>
            <body><a href="https://example.com/sitemap2.xml">Sitemap</a></body></html>
        """
        mock_get.return_value = mock_response

        result = self.finder._check_html_source(f"{self.base_url}/")
        assert set(result) == {f"{self.base_url}/sitemap1.xml", f"{self.base_url}/sitemap2.xml"}
        mock_get.assert_called_once_with(f"{self.base_url}/", timeout=self.finder.timeout_seconds)
        assert mock_confirm.call_count == 3

    @patch("requests.get")
    def test_check_html_source_not_found(self, mock_get):
        """Test when sitemap is not found in HTML source"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>No sitemap references here</body></html>"
        mock_get.return_value = mock_response

        result = self.finder._check_html_source(f"{self.base_url}/")
        assert result == []
        mock_get.assert_called_once_with(f"{self.base_url}/", timeout=self.finder.timeout_seconds)

    @patch("requests.get")
    @patch.object(SitemapFinder, "confirm_sitemap_url", return_value=True)
    def test_check_xml_files_in_root_found(self, mock_confirm, mock_get):
        """Test finding XML files in root directory"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body><a href="sitemap-index.xml">Sitemap</a></body></html>'
        mock_get.return_value = mock_response

        result = self.finder._check_xml_files_in_root(f"{self.base_url}/")
        assert result == [f"{self.base_url}/sitemap-index.xml"]
        mock_get.assert_called_once_with(f"{self.base_url}/", timeout=self.finder.timeout_seconds)
        mock_confirm.assert_called_once_with(f"{self.base_url}/sitemap-index.xml")

    @patch("requests.get")
    @patch.object(SitemapFinder, "confirm_sitemap_url")
    def test_check_xml_files_in_root_not_found(self, mock_confirm, mock_get):
        """Test when no suitable XML files are found in root directory"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body><a href="data.xml">Other XML</a></body></html>'
        mock_get.return_value = mock_response

        result = self.finder._check_xml_files_in_root(f"{self.base_url}/")
        assert not result
        mock_get.assert_called_once_with(f"{self.base_url}/", timeout=self.finder.timeout_seconds)
        mock_confirm.assert_not_called()

    @patch("requests.head")
    def test_confirm_sitemap_url_success(self, mock_head):
        """Test successful confirmation of sitemap URL"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers.get.return_value = "application/xml"
        mock_head.return_value = mock_response

        result = self.finder.confirm_sitemap_url(f"{self.base_url}/sitemap.xml")
        assert result is True
        mock_head.assert_called_once_with(
            f"{self.base_url}/sitemap.xml", timeout=self.finder.timeout_seconds, allow_redirects=True
        )

    @patch("requests.head")
    def test_confirm_sitemap_url_wrong_content_type(self, mock_head):
        """Test confirmation fails with incorrect Content-Type"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers.get.return_value = "text/html"
        mock_head.return_value = mock_response

        result = self.finder.confirm_sitemap_url(f"{self.base_url}/sitemap.xml")
        assert result is False

    @patch("requests.head")
    def test_confirm_sitemap_url_not_found(self, mock_head):
        """Test confirmation when sitemap URL returns 404"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_head.return_value = mock_response

        result = self.finder.confirm_sitemap_url(f"{self.base_url}/sitemap.xml")
        assert result is False
        mock_head.assert_called_once()

    @patch("requests.head")
    def test_confirm_sitemap_url_exception(self, mock_head):
        """Test handling exception when confirming sitemap URL"""
        mock_head.side_effect = Exception("Connection error")

        result = self.finder.confirm_sitemap_url(f"{self.base_url}/sitemap.xml")
        assert result is False
        mock_head.assert_called_once()

    def test_confirm_sitemap_url_none(self):
        """Test confirmation with None URL"""
        result = self.finder.confirm_sitemap_url(None)
        assert result is False

    @patch.object(SitemapFinder, "_check_common_locations")
    @patch.object(SitemapFinder, "_check_robots_txt")
    @patch.object(SitemapFinder, "_check_html_source")
    @patch.object(SitemapFinder, "_check_xml_files_in_root")
    def test_find_aggregates_unique_urls(self, mock_xml, mock_html, mock_robots, mock_common):
        """Test find() aggregates unique URLs from all methods"""
        mock_common.return_value = ["https://example.com/sitemap.xml"]
        mock_robots.return_value = ["https://example.com/robots.xml", "https://example.com/sitemap.xml"]
        mock_html.return_value = []
        mock_xml.return_value = ["https://example.com/root.xml"]

        result = self.finder.find(self.base_url)

        expected = {"https://example.com/sitemap.xml", "https://example.com/robots.xml", "https://example.com/root.xml"}
        assert result == expected
        mock_common.assert_called_once()
        mock_robots.assert_called_once()
        mock_html.assert_called_once()
        mock_xml.assert_called_once()

    @patch.object(SitemapFinder, "_check_common_locations", return_value=[])
    @patch.object(SitemapFinder, "_check_robots_txt", return_value=[])
    @patch.object(SitemapFinder, "_check_html_source", return_value=[])
    @patch.object(SitemapFinder, "_check_xml_files_in_root", return_value=[])
    def test_find_not_found(self, mock_xml, mock_html, mock_robots, mock_common):
        """Test when sitemap is not found using any method"""
        result = self.finder.find(self.base_url)
        assert result == set()
        mock_common.assert_called_once()
        mock_robots.assert_called_once()
        mock_html.assert_called_once()
        mock_xml.assert_called_once()

    @patch.object(SitemapFinder, "_check_common_locations", return_value=[])
    @patch.object(SitemapFinder, "_check_robots_txt", return_value=[])
    @patch.object(SitemapFinder, "_check_html_source", return_value=[])
    @patch.object(SitemapFinder, "_check_xml_files_in_root", return_value=[])
    def test_find_normalizes_url(self, mock_xml, mock_html, mock_robots, mock_common):
        """Test that URLs are normalized before processing"""
        # Test without protocol and without trailing slash
        self.finder.find("example.com")

        # All methods should be called with a normalized URL
        normalized_url = "https://example.com/"
        mock_common.assert_called_with(normalized_url)
        mock_robots.assert_called_with(normalized_url)
        mock_html.assert_called_with(normalized_url)
        mock_xml.assert_called_with(normalized_url)
