import http.server
import socketserver
import uuid

PORT = 8000

top_links = []

class SitemapHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global top_links
        if self.path == "/sitemap.xml":
            if not top_links:
                top_links = [generate_random_link() for _ in range(5)]
            else:
                top_links.append(generate_random_link())

            xml_lines = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
                         "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"]
            for link in top_links:
                xml_lines.extend([
                    "  <url>",
                    f"    <loc>{link}</loc>",
                    "  </url>"
                ])
            xml_lines.append("</urlset>")
            xml_data = "\n".join(xml_lines).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/xml; charset=utf-8")
            self.send_header("Content-Length", str(len(xml_data)))
            self.end_headers()
            self.wfile.write(xml_data)
        else:
            super().do_GET()


def generate_random_link():
    return f"https://example.com/{uuid.uuid4()}"

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), SitemapHandler) as httpd:
        endpoint = f"http://localhost:{PORT}/sitemap.xml"
        print(f"Serving sitemap server on {endpoint} use <Ctrl-C> to stop")
        httpd.serve_forever()
