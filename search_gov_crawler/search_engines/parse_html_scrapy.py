from scrapy import Selector
import search_gov_crawler.search_gov_spiders.helpers.content as content

def extract_article_content(html_selector: Selector) -> str:
    """
    Extracts the main content from an article in HTML while excluding links, button text, etc, 
    and ignoring <style> and <script> tags.
    
    :param html_selector: Scrapy HTML content selector.
    :return: The extracted content as a string.
    """
    
    body = html_selector.css("body")
    
    if not body:
        return ""
    
    content_text = body.xpath(".//text()[not(ancestor::a) and not(ancestor::button) and not(ancestor::style) and not(ancestor::script)]").getall()
    
    content_text = " ".join(text.strip() for text in content_text if text.strip())
    return content.replace_whitespace(content_text)


def get_meta_values(html_selector: Selector, meta_names: list) -> dict:
    """
    Extracts meta tag values by their name or property attributes and returns a dictionary.
    
    :param html_selector: Scrapy HTML content selector.
    :param meta_names: A list of meta tag names/properties to extract values for.
    :return: A dictionary with meta names as keys and extracted values or None.
    """
    meta_values = {}
    
    for name in meta_names:
        value = html_selector.xpath(f"//meta[@content and (@name=\"{name}\" or @property=\"{name}\")]/@content").get()
        meta_values[name] = value if value else None
    
    return meta_values

def convert_html_scrapy(html_content: str) -> dict:
    return_obj = {}
    html_selector = Selector(text=html_content)

    meta_tags = get_meta_values(html_selector, [
        "keywords", "description", "summary", "date", "revised", "audience", "pagename", "language", "url",
        "og:title", "og:image", "og:site_name", "og:description"
    ])

    return_obj["audience"] = meta_tags["audience"]
    return_obj["title"] = (
        html_selector.xpath("//title/text()").get()
        or html_selector.css("title::text").get()
        or meta_tags["og:title"]
        or meta_tags["og:site_name"]
        or meta_tags["pagename"]
    )
    return_obj["language"] = (
        html_selector.xpath("//html/@lang").get()
        or html_selector.css("html::attr(lang)").get()
        or meta_tags["language"]
    )
    if return_obj["language"]:
        return_obj["language"] = return_obj["language"].split("-")[0].lower()
    return_obj["url"] = meta_tags["url"]
    return_obj["keywords"] = meta_tags["keywords"]
    return_obj["description"] = meta_tags["description"] or meta_tags["og:description"]
    return_obj["summary"] = meta_tags["summary"]
    return_obj["created_at"] = meta_tags["date"] or meta_tags["revised"]
    return_obj["changed"] = meta_tags["revised"]
    return_obj["thumbnail_url"] = meta_tags["og:image"]

    for key in return_obj:
        return_obj[key] = content.replace_whitespace(return_obj[key])

    return_obj["content"] = extract_article_content(html_selector)

    return return_obj
