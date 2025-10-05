SITE_BUILDERS = {
    "WordPress": ["/wp-content/", "/wp-includes/"],
    "Wix": ["wix.com", "static.wixstatic.com", "wixsite.com", "wixstatic.com"],
    "Carrd": ["carrd.co", "cdn.carrd.co"],
    "Squarespace": ["squarespace.com", "static.squarespace.com", "squarespace-cdn.com"],
    "Weebly": ["weebly.com", "cdn.weebly.com"],
    "Shopify": ["myshopify.com", "cdn.shopify.com", "Shopify.theme"],
    "Drupal": ["drupalSettings"],
    "BigCommerce": ["cdn.bigcommerce.com", "Bigcommerce"],
    "Webflow": ["webflow.com"],
    "Duda": ["dudamobile.com", "duda.co", "duda.io"],
    "Jimdo": ["jimdo.com", "site.jimdo.com"],
    "SITE123": ["site123.com", "cdn.site123.me"],
    "Zyro": ["zyrosite.com", "zyrocdn.com"],
    "Webnode": ["webnode.com", "webnodecdn.com"],
    "Tilda": ["tilda.cc", "tildacdn.com"],
    "IMCreator": ["imcreator.com", "imcreatorcdn.com"],
    "GoDaddy Website Builder": ["godaddy.com", "godaddysites.com"],
    "Strikingly": ["strikingly.com", "cdn.strikingly.com"],
    "Oxygen": ["oxygen"]
}

def detect_site_builder(html):
    try:
        html = html.lower()
        detected = []

        for builder, patterns in SITE_BUILDERS.items():
            for pattern in patterns:
                if pattern.lower() in html:
                    detected.append(builder)
                    break

        return {
            "builders_detected": detected if detected else ["Unknown"]
        }
    except Exception as e:
        return {"error": str(e)}

