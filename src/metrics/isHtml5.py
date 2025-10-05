def is_html5(html):
    html = html.lstrip().lower()
    if html.startswith("<!doctype html>"):
        return True
    return False