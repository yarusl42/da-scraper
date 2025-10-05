import requests
import xml.etree.ElementTree as ET

def check_sitemap(domain):
    sitemap_urls = [
        f"https://{domain}/sitemap.xml",
        f"https://{domain}/sitemap_index.xml",  # sometimes sitemap index
        f"https://{domain}/sitemap-index.xml"
    ]

    sitemap_found = None
    total_pages = 0

    for sitemap_url in sitemap_urls:
        try:
            r = requests.get(sitemap_url, timeout=10)
            if r.status_code == 200 and 'xml' in r.headers.get('Content-Type', ''):
                sitemap_found = sitemap_url
                root = ET.fromstring(r.content)

                # Check if it's sitemap index or regular sitemap
                if root.tag.endswith('sitemapindex'):
                    # sitemap index contains multiple sitemaps
                    for sitemap in root.findall('{*}sitemap'):
                        loc = sitemap.find('{*}loc')
                        if loc is not None:
                            try:
                                r2 = requests.get(loc.text, timeout=10)
                                if r2.status_code == 200:
                                    root2 = ET.fromstring(r2.content)
                                    total_pages += len(root2.findall('{*}url'))
                            except:
                                continue
                else:
                    # regular sitemap
                    total_pages = len(root.findall('{*}url'))

                break  # stop after first found sitemap

        except Exception as e:
            continue

    return {
        "domain": domain,
        "sitemap_found": sitemap_found,
        "total_pages": total_pages
    }

