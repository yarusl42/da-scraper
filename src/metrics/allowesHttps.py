import requests

def check_http_allowed(r, domain):
    """Determine if the site serves over HTTP and whether HTTPS has SSL issues.

    Inputs:
    - r: Response from an HTTP request (e.g., requests.get("http://domain", allow_redirects=True))
    - domain: bare domain like "example.com" or "www.example.com"

    Returns a dict with:
    - domain
    - http_allowed: bool (True if HTTP loads or redirects)
    - redirects_to_https: bool|None (True if HTTP redirected to HTTPS; False if stayed on HTTP; None if HTTP failed)
    - ssl_bad: bool|None (True if HTTPS certificate is bad; False if appears OK; None if HTTPS not reachable)
    - status_code or error: optional diagnostic fields
    """
    result = {"domain": domain, "http_allowed": False, "redirects_to_https": None, "ssl_bad": None}

    # 1) Evaluate HTTP behavior from provided response r
    try:
        status = getattr(r, "status_code", None)
        url = getattr(r, "url", "") or ""
        if status is not None:
            if 200 <= status < 400:
                result["http_allowed"] = True
                result["redirects_to_https"] = url.startswith("https://")
            else:
                result["http_allowed"] = False
                result["status_code"] = status
        else:
            result["error"] = "Invalid response object"
    except requests.exceptions.RequestException as e:
        result["error"] = str(e)

    # 2) Probe HTTPS to detect SSL issues (HEAD first, fallback to GET)
    https_url = f"https://{domain}"
    try:
        # Use HEAD to be cheap; some servers disallow HEAD, so fallback to GET
        resp = requests.head(https_url, timeout=10, allow_redirects=True, verify=True)
        if 200 <= resp.status_code < 400:
            result["ssl_bad"] = False
        else:
            # Non-success on HTTPS doesn't necessarily mean bad SSL, just record
            result["ssl_bad"] = False
            result["https_status_code"] = resp.status_code
    except requests.exceptions.SSLError as e:
        result["ssl_bad"] = True
        result["ssl_error"] = str(e)
    except requests.exceptions.RequestException:
        # Retry with GET in case HEAD is blocked
        try:
            resp = requests.get(https_url, timeout=10, allow_redirects=True, verify=True)
            if 200 <= resp.status_code < 400:
                result["ssl_bad"] = False
            else:
                result["ssl_bad"] = False
                result["https_status_code"] = resp.status_code
        except requests.exceptions.SSLError as e:
            result["ssl_bad"] = True
            result["ssl_error"] = str(e)
        except requests.exceptions.RequestException as e:
            # Could not reach HTTPS; leave ssl_bad as None to indicate unknown
            if result.get("ssl_bad") is None:
                result["ssl_bad"] = None
            result["https_error"] = str(e)

    return result
