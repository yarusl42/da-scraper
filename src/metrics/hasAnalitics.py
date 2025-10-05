def has_analytics(soup):
    scripts = soup.find_all('script', src=True) + soup.find_all('script')
    analytics_patterns = [
        "www.googletagmanager.com/gtm.js",
        "www.google-analytics.com/analytics.js",
        "www.google-analytics.com/gtag/js",
        "connect.facebook.net/en_US/fbevents.js",
        "analytics.js",
        "gtag(",
        "_gaq.push"
    ]
    for script in scripts:
        src = script.get('src', '')
        if any(pat in src for pat in analytics_patterns):
            return True
        if script.string and any(pat in script.string for pat in analytics_patterns):
            return True
    return False