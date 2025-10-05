DEBUG = True

import requests
from bs4 import BeautifulSoup
from allowesHttps import check_http_allowed
from findFramework import detect_frontend_frameworks
from isTitleGeneric import check_generic_title
from loadTime import load_page
from lastupdatetest import guess_last_update
from countImages import count_images
from countWords import count_words
from usesJs import check_if_js_is_used
from countSitemapPages import check_sitemap
from findSiteBuilder import detect_site_builder
from isJquery import detect_jquery
from hasAnalitics import has_analytics
from has_meta_viewport import isResponsive
from has_meta_description import has_meta_description
from has_h1 import has_h1
from has_favicon import has_favicon
from isHtml5 import is_html5

from playwright.sync_api import sync_playwright


url = "https://www.denverweldingfab.com/"
# allows http is not working correctly

def performance_metrics(url):
    http_url = url.replace("https://", "http://")
    domain = http_url.split("/")[2]
    base_url = f"http://{domain}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        head = requests.head(url, timeout=10)
        requests_html = requests.get(url, timeout=10).text
        # req_http = requests.get(http_url, timeout=10, allow_redirects=True)
        page, speedMetrics = load_page(url, page)
        loaded_html = page.content()

        soup = BeautifulSoup(loaded_html, "html.parser")
        soup_unloaded = BeautifulSoup(requests_html, "html.parser")

        # isHttpAllowed = check_http_allowed(req_http, domain)
        framework = detect_frontend_frameworks(page, soup, loaded_html)
        genericTitle = check_generic_title(soup)
        lastUpdate = guess_last_update(head, soup)
        images = count_images(soup)
        words = count_words(soup)
        usesJs = check_if_js_is_used(soup, soup_unloaded)
        sitemap = check_sitemap(domain)
        siteBuilder = detect_site_builder(loaded_html)
        jquery = detect_jquery(page, soup)
        analytics = has_analytics(soup)
        responsive = isResponsive(soup, base_url)
        metaDescription = has_meta_description(soup)
        h1 = has_h1(soup)
        favicon = has_favicon(soup)
        html5 = is_html5(requests_html)

    return {
        "isHttpAllowed": isHttpAllowed,
        "framework": framework,
        "genericTitle": genericTitle,
        "speedMetrics": speedMetrics,
        "lastUpdate": lastUpdate,
        "images": images,
        "words": words,
        "usesJs": usesJs,
        "domain": domain,
        "sitemap": sitemap,
        "siteBuilder": siteBuilder,
        "jquery": jquery,
        "analytics": analytics,
        "responsive": responsive,
        "metaDescription": metaDescription,
        "h1": h1,
        "favicon": favicon,
        "html5": html5
    }

result = performance_metrics("https://denverweldingfab.com/")
print(result)


# genericTitle