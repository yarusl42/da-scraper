def detect_frontend_frameworks(page, soup, html):
    frameworks = []
    # Next.js (React meta-framework)
    if soup.find('meta', attrs={'name':'next-head'}) or '__NEXT_DATA__' in html or '_next/' in html:
        frameworks.append("Next.js")
    # React
    elif page.evaluate("() => !!window.__REACT_DEVTOOLS_GLOBAL_HOOK__") or \
        'data-reactroot' in html or '__reactInternalInstance' in html:
        frameworks.append("React")

    # Nuxt.js (Vue meta-framework)
    if soup.find('meta', attrs={'name':'nuxt-head'}) or '__NUXT__' in html or '_nuxt/' in html:
        frameworks.append("Nuxt.js")
    # Vue
    elif page.evaluate("() => !!window.Vue") or '__vue__' in html or 'data-v-' in html:
        frameworks.append("Vue")
    
    # Angular
    if soup.find(attrs={'ng-version': True}) or page.evaluate("() => !!document.querySelector('[ng-version]')"):
        frameworks.append("Angular")

    # Svelte
    if page.evaluate("() => !!window.__SVELTE_DEVTOOLS_GLOBAL_HOOK__") or 'data-svelte' in html or 'svelte-h' in html:
        frameworks.append("Svelte")

    # Ember.js
    if page.evaluate("() => !!window.Ember") or 'ember-view' in html:
        frameworks.append("Ember.js")

    # Solid.js
    if page.evaluate("() => !!window.__SOLID_DEVTOOLS_GLOBAL_HOOK__"):
        frameworks.append("Solid.js")

    # Alpine.js
    if page.evaluate("() => !!window.Alpine") or 'x-data' in html:
        frameworks.append("Alpine.js")

    # Astro
    if '_astro/' in html:
        frameworks.append("Astro")

    # Marko
    if 'data-marko' in html or page.evaluate("() => !!window.$Marko"):
        frameworks.append("Marko.js")

    # Stimulus.js
    if 'data-controller' in html:
        frameworks.append("Stimulus.js")

    # Lit / LitElement
    if page.evaluate("() => !!window.LitElement") or 'lit-element' in html:
        frameworks.append("Lit / LitElement")

    if not frameworks:
        frameworks.append("Unknown")


    return frameworks
