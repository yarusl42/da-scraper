import time

def load_page(url, page):
    start = time.time()
    page.goto(url, wait_until='load', timeout=30000)
    end = time.time()
    
    perf = page.evaluate("() => JSON.stringify(window.performance.timing)")
    
    return page, {
        "url": url,
        "load_time_seconds": end - start,
        "performance_timing": perf
    }
