def detect_jquery(page, soup):
    try:
        jquery_detected = page.evaluate("() => !!window.jQuery || !!window.$")
        if jquery_detected:
            return True

        for script in soup.find_all('script', src=True):
            if "jquery" in script['src'].lower():
                return True

        return False
    except Exception as e:
        return str(e)

