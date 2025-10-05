import requests
import tinycss2
from urllib.parse import urljoin

def has_meta_viewport(soup):
    viewport_meta = soup.find('meta', attrs={'name': 'viewport'})
    return bool(viewport_meta)

def extract_css_from_html(soup, base_url):
    css_contents = []

    for style_tag in soup.find_all('style'):
        css_contents.append(style_tag.string or "")

    for link_tag in soup.find_all('link', rel='stylesheet', href=True):
        if link_tag['href'].startswith('http'):
            css_url = link_tag['href']
        else:
            css_url = urljoin(base_url, link_tag['href'])
        try:
            r = requests.get(css_url, timeout=10)
            if r.status_code == 200:
                css_contents.append(r.text)
        except Exception:
            continue

    return css_contents

def has_media_queries(css_contents):
    """Check if any CSS content has @media rules."""
    for css in css_contents:
        rules = tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)
        for rule in rules:
            if rule.type == 'at-rule' and rule.lower_at_keyword == 'media':
                return True
    return False

def isResponsive(soup, base_url):
    if not has_meta_viewport(soup):
        return False
    return has_media_queries(extract_css_from_html(soup, base_url))

