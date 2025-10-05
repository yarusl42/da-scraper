import requests

def check_http_allowed(r, domain):
    try:
        if r.status_code >= 200 and r.status_code < 400:
            if r.url.startswith("https://"):
                return {"domain": domain, "http_allowed": True, "redirects_to_https": True}
            else:
                return {"domain": domain, "http_allowed": True, "redirects_to_https": False}
        else:
            return {"domain": domain, "http_allowed": False, "status_code": r.status_code}
    except requests.exceptions.SSLError:
        return {"domain": domain, "http_allowed": False, "error": "SSL required"}
    except requests.exceptions.RequestException as e:
        return {"domain": domain, "http_allowed": False, "error": str(e)}
