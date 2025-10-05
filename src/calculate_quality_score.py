def calculate_quality_score(metrics):
    score = 0
    reasons = []
    
    if not metrics.get("gbp_is_verified", True):
        score += 120
        reasons.append(("Unverified Google Business Profile", 120))

    gbp_categories = metrics.get("gbp_categories", [])
    if len(gbp_categories) == 1:
        score += 30
        reasons.append((f"Only one GBP category ({gbp_categories[0]})", 30))

    gbp_attributes = metrics.get("gbp_amount_of_attributes", 0)
    if gbp_attributes <= 1:
        score += 40
        reasons.append((f"Few GBP attributes ({gbp_attributes})", 40))

    if not metrics.get("has_website", True):
        score += 120
        reasons.append(("No website listed in GBP", 120))
    else:
        # --- CRITICAL ---
        if metrics.get("isHttpAllowed", {}).get("ssl_bad", False):
            score += 120
            reasons.append(("Invalid or expired SSL certificate", 120))
        elif metrics.get("isHttpAllowed", {}).get("http_allowed", False) and not metrics.get("isHttpAllowed", {}).get("redirects_to_https", True):
            score += 100
            reasons.append(("HTTP access allowed (no forced HTTPS)", 100))
        if not metrics.get("responsive", True):
            score += 100
            reasons.append(("Not responsive", 100))

        builders = metrics.get("siteBuilder", {}).get("builders_detected", [])
        for b in builders:
            # builders_detected returns names like keys in SITE_BUILDERS
            if b in ["Wix", "Carrd", "Squarespace"]:
                score += 30
                reasons.append((f"One-page site builder ({b})", 80))

        # --- STRUCTURAL ---
        if not metrics.get("favicon", True):
            score += 40
            reasons.append(("No favicon", 40))

        if not metrics.get("html5", True):
            score += 60
            reasons.append(("Not using HTML5", 60))

        if metrics.get("genericTitle", {}).get("is_generic", False):
            score += 20
            reasons.append(("Generic title", 20))

        if not metrics.get("metaDescription", True):
            score += 20
            reasons.append(("No meta description", 20))

        if not metrics.get("h1", True):
            score += 30  # doubled from 15
            reasons.append(("No H1 tag", 30))

        if not metrics.get("analytics", True):
            score += 25
            reasons.append(("No analytics or tracking", 25))

        # --- CONTENT ---
        word_count = metrics.get("words", 0)
        if word_count < 200:
            penalty = min(80, int(0.2 * (200 - word_count)))
            score += penalty
            reasons.append((f"Low text content ({word_count} words)", penalty))

        image_count = metrics.get("images", 0)
        if image_count < 3:
            penalty = min(60, 15 * (3 - image_count))
            score += penalty
            reasons.append((f"Few images ({image_count})", penalty))

        # --- AGE ---
        years_old = 0
        if "lastUpdate" in metrics:
            latest_year = metrics["lastUpdate"].get("latest_year_in_text")
            if latest_year:
                import datetime
                current_year = datetime.datetime.now().year
                years_old = max(0, current_year - latest_year)
        if years_old > 1:
            penalty = min(150, 15 * years_old)
            score += penalty
            reasons.append((f"Very old content ({years_old} years old)", penalty))

        # --- SITEMAP ---
        sitemap_info = metrics.get("sitemap", {})
        if sitemap_info.get("sitemap_found") and sitemap_info.get("total_pages", 0) < 5:
            penalty = 10 * (5 - sitemap_info["total_pages"])
            score += penalty
            reasons.append((f"Small sitemap ({sitemap_info['total_pages']} pages)", penalty))
        elif not sitemap_info.get("sitemap_found"):
            score += 30
            reasons.append(("No sitemap found", 30))

        # --- TECH STACK ---
        frameworks = metrics.get("framework", [])
        # Penalize sites using heavy SPA frameworks (Angular/React/Vue)
        # and a few older ones from our detection list.
        penalized_fw = {"Angular", "React", "Vue", "Ember.js", "Backbone", "Dojo"}
        if any(f in penalized_fw for f in frameworks):
            score += 30
            reasons.append((f"Frameworks detected ({', '.join(frameworks)})", 40))
        elif "Unknown" in metrics.get("framework") and metrics.get("usesJs") == False:
            score += 30
            reasons.append(("No JavaScript", 30))
        elif "Unknown" in metrics.get("framework") and metrics.get("jquery") == True:
            score += 30
            reasons.append(("jQuery", 30))
        
        # --- PERFORMANCE ---
        load_time = metrics.get("speedMetrics", {}).get("load_time_seconds", 0)
        if load_time > 3:
            penalty = min(50, int(5 * (load_time - 3)))
            score += penalty
            reasons.append((f"Slow load time ({load_time:.1f}s)", penalty))

    return {
        "score": score,
        "is_bad": score >= 60,
        "reasons": sorted(reasons, key=lambda x: x[1], reverse=True)
    }
