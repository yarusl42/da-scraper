DEBUG = True

import requests
from bs4 import BeautifulSoup
from src.metrics.allowesHttps import check_http_allowed
from src.metrics.findFramework import detect_frontend_frameworks
from src.metrics.isTitleGeneric import check_generic_title
from src.metrics.loadTime import load_page
from src.metrics.lastupdatetest import guess_last_update
from src.metrics.countImages import count_images
from src.metrics.countWords import count_words
from src.metrics.usesJs import check_if_js_is_used
from src.metrics.countSitemapPages import check_sitemap
from src.metrics.findSiteBuilder import detect_site_builder, SITE_BUILDERS
from src.metrics.isJquery import detect_jquery
from src.metrics.hasAnalitics import has_analytics
from src.metrics.has_meta_viewport import isResponsive
from src.metrics.has_meta_description import has_meta_description
from src.metrics.has_h1 import has_h1
from src.metrics.has_favicon import has_favicon
from src.metrics.isHtml5 import is_html5
from src.calculate_quality_score import calculate_quality_score
from playwright.sync_api import sync_playwright


url = "https://www.denverweldingfab.com/"
# allows http is not working correctly

def performance_metrics(row, page):
    url = row.get("query_url", "").strip()
    http_url = url.replace("https://", "http://")
    domain = http_url.split("/")[2]
    base_url = f"http://{domain}"

    head = requests.head(url, timeout=10)
    requests_html = requests.get(url, timeout=10).text
    req_http = requests.get(http_url, timeout=10, allow_redirects=True)
    page, speedMetrics = load_page(url, page)
    loaded_html = page.content()

    soup = BeautifulSoup(loaded_html, "html.parser")
    soup_unloaded = BeautifulSoup(requests_html, "html.parser")

    isHttpAllowed = check_http_allowed(req_http, domain)
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
    phoneStartsWithPlus = row.get("phone", "").startswith("+")
    hasPhone = bool(row.get("phone", ""))
    hasAddress = bool(row.get("address", ""))
    gbp_is_verified = row.get("gbp_is_verified", False)
    n_categories = len(row.get("categories", []))
    gbp_has_image = row.get("gbp_has_image", False)
    attributes = row.get("attributes", -1)

    page.close()

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
        "html5": html5,
        "phoneStartsWithPlus": phoneStartsWithPlus,
        "hasPhone": hasPhone,
        "hasAddress": hasAddress,
        "gbp_is_verified": gbp_is_verified,
        "n_categories": n_categories,
        "gbp_has_image": gbp_has_image,
        "attributes": attributes
    }


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    metrics = performance_metrics("https://www.lyonsfabrication.com/", page)
    result = calculate_quality_score(metrics)
    print(result)
    browser.close()

# genericTitle