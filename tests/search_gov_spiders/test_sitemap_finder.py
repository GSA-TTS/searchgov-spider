from unittest.mock import patch, mock_open, MagicMock
from search_gov_crawler.search_gov_spiders.sitemaps.sitemap_finder import (
    SitemapFinder,
    write_dict_to_csv
)

class TestWriteDictToCsv:
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    def test_write_dict_to_csv_overwrite(self, mock_exists, mock_file):
        """Test overwriting a CSV file with the dictionary data"""
        mock_exists.return_value = True
        data = {"https://example.com": "https://example.com/sitemap.xml"}
        
        write_dict_to_csv(data, "test_file.csv", overwrite=True)
        
        mock_file.assert_called_once_with("test_file.csv", mode="w", newline="", encoding="utf-8")
        handle = mock_file()
        calls = handle.write.call_args_list
        assert "starting_urls,sitemap_url\r\n" in calls[0][0][0]  # Header
        assert "https://example.com,https://example.com/sitemap.xml\r\n" in calls[1][0][0]  # Data

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    def test_write_dict_to_csv_append_existing(self, mock_exists, mock_file):
        """Test appending data to an existing CSV file without header"""
        mock_exists.return_value = True
        data = {"https://example.com": "https://example.com/sitemap.xml"}
        
        write_dict_to_csv(data, "test_file.csv", overwrite=False)
        
        mock_file.assert_called_once_with("test_file.csv", mode="a", newline="", encoding="utf-8")
        handle = mock_file()
        calls = handle.write.call_args_list
        # No header should be written when appending to existing file
        assert len(calls) == 1
        assert "https://example.com,https://example.com/sitemap.xml\r\n" in calls[0][0][0]

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    def test_write_dict_to_csv_append_new(self, mock_exists, mock_file):
        """Test appending data to a new CSV file with header"""
        mock_exists.return_value = False
        data = {"https://example.com": "https://example.com/sitemap.xml"}
        
        write_dict_to_csv(data, "test_file.csv", overwrite=False)
        
        mock_file.assert_called_once_with("test_file.csv", mode="a", newline="", encoding="utf-8")
        handle = mock_file()
        calls = handle.write.call_args_list
        # Header should be written when appending to non-existing file
        assert "starting_urls,sitemap_url\r\n" in calls[0][0][0]
        assert "https://example.com,https://example.com/sitemap.xml\r\n" in calls[1][0][0]

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    def test_write_dict_to_csv_adds_extension(self, mock_exists, mock_file):
        """Test that .csv extension is added if not provided"""
        mock_exists.return_value = True
        data = {"https://example.com": "https://example.com/sitemap.xml"}
        
        write_dict_to_csv(data, "test_file", overwrite=True)
        
        mock_file.assert_called_once_with("test_file.csv", mode="w", newline="", encoding="utf-8")

class TestSitemapFinder:
    def setup_method(self):
        self.finder = SitemapFinder()
        self.base_url = "https://example.com"
    
    def test_init(self):
        """Test initialization of SitemapFinder"""
        assert self.finder.timeout_seconds == 5
        assert len(self.finder.common_sitemap_names) > 0
        assert "sitemap.xml" in self.finder.common_sitemap_names
    
    def test_join_base_with_relative_path(self):
        """Test joining base URL with relative path"""
        result = self.finder._join_base("https://example.com/", "sitemap.xml")
        assert result == "https://example.com/sitemap.xml"
    
    def test_join_base_with_absolute_url(self):
        """Test that absolute URLs are not modified when joining"""
        absolute_url = "https://another-domain.com/sitemap.xml"
        result = self.finder._join_base("https://example.com/", absolute_url)
        assert result == absolute_url
    
    def test_fix_http(self):
        """Test that http URLs are converted to https"""
        http_url = "http://example.com/sitemap.xml"
        result = self.finder._fix_http(http_url)
        assert result == "https://example.com/sitemap.xml"

    @patch.object(SitemapFinder, "confirm_sitemap_url")
    def test_check_common_locations_found(self, mock_confirm):
        """Test finding sitemap in common locations"""
        mock_confirm.return_value = True
        result = self.finder._check_common_locations(self.base_url)
        assert result == f"{self.base_url}/sitemap.xml"  # First in the list
        mock_confirm.assert_called_once()

    @patch.object(SitemapFinder, "confirm_sitemap_url")
    def test_check_common_locations_not_found(self, mock_confirm):
        """Test when sitemap is not found in common locations"""
        mock_confirm.return_value = False
        result = self.finder._check_common_locations(self.base_url)
        assert result is None
        # Should be called for each common sitemap name
        assert mock_confirm.call_count == len(self.finder.common_sitemap_names)

    @patch("requests.get")
    def test_check_robots_txt_found(self, mock_get):
        """Test finding sitemap in robots.txt"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nDisallow: /admin\nSitemap: https://example.com/custom-sitemap.xml"
        mock_get.return_value = mock_response
        
        result = self.finder._check_robots_txt(self.base_url)
        assert result == "https://example.com/custom-sitemap.xml"
        mock_get.assert_called_once_with(f"{self.base_url}/robots.txt", timeout=self.finder.timeout_seconds)

    @patch("requests.get")
    def test_check_robots_txt_not_found(self, mock_get):
        """Test when sitemap is not found in robots.txt"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nDisallow: /admin"  # No Sitemap: directive
        mock_get.return_value = mock_response
        
        result = self.finder._check_robots_txt(self.base_url)
        assert result is None
        mock_get.assert_called_once_with(f"{self.base_url}/robots.txt", timeout=self.finder.timeout_seconds)

    @patch("requests.get")
    def test_check_robots_txt_exception(self, mock_get):
        """Test handling exception when checking robots.txt"""
        mock_get.side_effect = Exception("Connection error")
        
        result = self.finder._check_robots_txt(self.base_url)
        assert result is None
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_check_html_source_link_tag(self, mock_get):
        """Test finding sitemap in HTML link tag"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><head><link rel="sitemap" href="/sitemap.xml"></head></html>'
        mock_get.return_value = mock_response
        
        result = self.finder._check_html_source(self.base_url)
        assert result == f"{self.base_url}/sitemap.xml"
        mock_get.assert_called_once_with(self.base_url, timeout=self.finder.timeout_seconds)

    @patch("requests.get")
    def test_check_html_source_href(self, mock_get):
        """Test finding sitemap reference in HTML href"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body><a href="sitemap.xml">Sitemap</a></body></html>'
        mock_get.return_value = mock_response
        
        result = self.finder._check_html_source(self.base_url)
        assert result == "https://example.com/sitemap.xml"
        mock_get.assert_called_once_with(self.base_url, timeout=self.finder.timeout_seconds)

    @patch("requests.get")
    def test_check_html_source_not_found(self, mock_get):
        """Test when sitemap is not found in HTML source"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body>No sitemap references here</body></html>'
        mock_get.return_value = mock_response
        
        result = self.finder._check_html_source(self.base_url)
        assert result is None
        mock_get.assert_called_once_with(self.base_url, timeout=self.finder.timeout_seconds)

    @patch("requests.get")
    @patch.object(SitemapFinder, "confirm_sitemap_url")
    def test_check_xml_files_in_root(self, mock_confirm, mock_get):
        """Test finding XML files in root directory"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body><a href="sitemap-index.xml">Sitemap</a></body></html>'
        mock_get.return_value = mock_response
        mock_confirm.return_value = True
        
        result = self.finder._check_xml_files_in_root(self.base_url)
        assert result == f"{self.base_url}/sitemap-index.xml"
        mock_get.assert_called_once_with(self.base_url, timeout=self.finder.timeout_seconds)
        mock_confirm.assert_called_once()

    @patch("requests.get")
    @patch.object(SitemapFinder, "confirm_sitemap_url")
    def test_check_xml_files_in_root_not_found(self, mock_confirm, mock_get):
        """Test when XML files are not found in root directory"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body><a href="page.html">Not sitemap</a></body></html>'
        mock_get.return_value = mock_response
        mock_confirm.return_value = True
        
        result = self.finder._check_xml_files_in_root(self.base_url)
        assert result is None
        mock_get.assert_called_once_with(self.base_url, timeout=self.finder.timeout_seconds)
        # Confirm should not be called since no sitemap-like XML files were found
        mock_confirm.assert_not_called()

    @patch("requests.head")
    def test_confirm_sitemap_url_success(self, mock_head):
        """Test successful confirmation of sitemap URL"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response
        
        result = self.finder.confirm_sitemap_url("https://example.com/sitemap.xml")
        assert result is True
        mock_head.assert_called_once_with(
            "https://example.com/sitemap.xml", 
            timeout=self.finder.timeout_seconds,
            allow_redirects=True
        )

    @patch("requests.head")
    def test_confirm_sitemap_url_not_found(self, mock_head):
        """Test confirmation when sitemap URL returns 404"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_head.return_value = mock_response
        
        result = self.finder.confirm_sitemap_url("https://example.com/sitemap.xml")
        assert result is False
        mock_head.assert_called_once()

    @patch("requests.head")
    def test_confirm_sitemap_url_exception(self, mock_head):
        """Test handling exception when confirming sitemap URL"""
        mock_head.side_effect = Exception("Connection error")
        
        result = self.finder.confirm_sitemap_url("https://example.com/sitemap.xml")
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
    @patch.object(SitemapFinder, "_fix_http")
    def test_find_found_in_common_locations(
        self, mock_fix, mock_xml, mock_html, mock_robots, mock_common
    ):
        """Test finding sitemap using common locations method"""
        mock_common.return_value = "https://example.com/sitemap.xml"
        mock_fix.return_value = "https://example.com/sitemap.xml"
        
        result = self.finder.find(self.base_url)
        
        assert result == "https://example.com/sitemap.xml"
        mock_common.assert_called_once()
        mock_fix.assert_called_once_with("https://example.com/sitemap.xml")
        # Other methods should not be called
        mock_robots.assert_not_called()
        mock_html.assert_not_called()
        mock_xml.assert_not_called()

    @patch.object(SitemapFinder, "_check_common_locations")
    @patch.object(SitemapFinder, "_check_robots_txt")
    @patch.object(SitemapFinder, "_check_html_source")
    @patch.object(SitemapFinder, "_check_xml_files_in_root")
    @patch.object(SitemapFinder, "_fix_http")
    def test_find_found_in_robots(
        self, mock_fix, mock_xml, mock_html, mock_robots, mock_common
    ):
        """Test finding sitemap using robots.txt method"""
        mock_common.return_value = None
        mock_robots.return_value = "https://example.com/sitemap-from-robots.xml"
        mock_fix.return_value = "https://example.com/sitemap-from-robots.xml"
        
        result = self.finder.find(self.base_url)
        
        assert result == "https://example.com/sitemap-from-robots.xml"
        mock_common.assert_called_once()
        mock_robots.assert_called_once()
        mock_fix.assert_called_once_with("https://example.com/sitemap-from-robots.xml")
        # Later methods should not be called
        mock_html.assert_not_called()
        mock_xml.assert_not_called()

    @patch.object(SitemapFinder, "_check_common_locations")
    @patch.object(SitemapFinder, "_check_robots_txt")
    @patch.object(SitemapFinder, "_check_html_source")
    @patch.object(SitemapFinder, "_check_xml_files_in_root")
    def test_find_not_found(self, mock_xml, mock_html, mock_robots, mock_common):
        """Test when sitemap is not found using any method"""
        mock_common.return_value = None
        mock_robots.return_value = None
        mock_html.return_value = None
        mock_xml.return_value = None
        
        result = self.finder.find(self.base_url)
        
        assert result is None
        mock_common.assert_called_once()
        mock_robots.assert_called_once()
        mock_html.assert_called_once()
        mock_xml.assert_called_once()

    def test_find_normalizes_url(self):
        """Test that URLs are normalized before processing"""
        with patch.object(SitemapFinder, "_check_common_locations", return_value=None) as mock_common, \
             patch.object(SitemapFinder, "_check_robots_txt", return_value=None) as mock_robots, \
             patch.object(SitemapFinder, "_check_html_source", return_value=None) as mock_html, \
             patch.object(SitemapFinder, "_check_xml_files_in_root", return_value=None) as mock_xml:
            
            # Test without protocol
            self.finder.find("example.com")
            mock_common.assert_called_with("https://example.com/")
            
            # Test without trailing slash
            mock_common.reset_mock()
            self.finder.find("https://example.com")
            mock_common.assert_called_with("https://example.com/")
