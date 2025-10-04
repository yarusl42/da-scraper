import requests

def check_http_allowed(domain):
    http_url = f"http://{domain}"
    try:
        # allow redirects, but we want to see if it responds over HTTP
        r = requests.get(http_url, timeout=10, allow_redirects=True)
        # if we get a 200–399 response, HTTP is allowed
        if r.status_code >= 200 and r.status_code < 400:
            # check if it redirected to HTTPS
            if r.url.startswith("https://"):
                return {"domain": domain, "http_allowed": True, "redirects_to_https": True}
            else:
                return {"domain": domain, "http_allowed": True, "redirects_to_https": False}
        else:
            return {"domain": domain, "http_allowed": False, "status_code": r.status_code}
    except requests.exceptions.SSLError:
        # SSL error usually means HTTPS required
        return {"domain": domain, "http_allowed": False, "error": "SSL required"}
    except requests.exceptions.RequestException as e:
        return {"domain": domain, "http_allowed": False, "error": str(e)}

# Example usage
domains = [
    "denverweldingfab.com",
    "example.com",
    "httpbin.org",
    "brothersglasscompany.com"

]

for d in domains:
    result = check_http_allowed(d)
    print(result)
