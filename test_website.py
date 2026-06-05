"""
Automated functional tests for DofusFashionistaVanced.
Requires the dev server to be running (default: http://localhost:8000).

Usage:
    python test_website.py
    python test_website.py --url http://localhost:8000
    python test_website.py --url https://dofusfashionista.gg
"""

import sys
import argparse
import time
import json
import re
import requests

# ── ANSI colour helpers ───────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

_passed = []
_failed = []
_skipped = []

def ok(name):
    _passed.append(name)
    print(f"  {GREEN}[OK]{RESET} {name}")

def fail(name, reason=""):
    _failed.append(name)
    msg = f"  {RED}[FAIL] {name}{RESET}"
    if reason:
        msg += f"\n         {YELLOW}-> {reason}{RESET}"
    print(msg)

def skip(name, reason=""):
    _skipped.append(name)
    print(f"  {YELLOW}[SKIP] {name}{RESET}" + (f" ({reason})" if reason else ""))

def section(title):
    print(f"\n{BOLD}{CYAN}--- {title} ---{RESET}")

# ── Shared session ────────────────────────────────────────────────────────────
session = requests.Session()

def get(path, **kw):
    timeout = kw.pop("timeout", 10)
    return session.get(BASE + path, allow_redirects=True, timeout=timeout, **kw)

def post(path, data=None, **kw):
    timeout = kw.pop("timeout", 10)
    return session.post(BASE + path, data=data, allow_redirects=True, timeout=timeout, **kw)

def csrf():
    """Extract the current CSRF token from the session cookie jar."""
    return session.cookies.get("csrftoken", "")

def get_csrf_from_page(html):
    m = re.search(r'csrfmiddlewaretoken.*?value="([^"]+)"', html)
    return m.group(1) if m else ""

# ── Individual checks ─────────────────────────────────────────────────────────

def check_status(name, path, expected=200, **kw):
    try:
        r = get(path, **kw)
        if r.status_code == expected:
            ok(name)
            return r
        else:
            fail(name, f"HTTP {r.status_code} (expected {expected}) at {path}")
            return r
    except Exception as e:
        fail(name, str(e))
        return None

def check_contains(name, path, needle, cookies=None):
    try:
        kw = {"cookies": cookies} if cookies else {}
        r = get(path, **kw)
        if r.status_code != 200:
            fail(name, f"HTTP {r.status_code}")
            return
        if needle in r.text:
            ok(name)
        else:
            fail(name, f"'{needle[:80]}' not found in {path}")
    except Exception as e:
        fail(name, str(e))

def check_contains_any(name, path, needles, cookies=None):
    try:
        kw = {"cookies": cookies} if cookies else {}
        r = get(path, **kw)
        if r.status_code != 200:
            fail(name, f"HTTP {r.status_code}")
            return
        if any(needle in r.text for needle in needles):
            ok(name)
        else:
            preview = ", ".join(f"'{needle[:40]}'" for needle in needles)
            fail(name, f"none of {preview} found in {path}")
    except Exception as e:
        fail(name, str(e))

def check_json(name, path):
    try:
        r = get(path)
        if r.status_code != 200:
            fail(name, f"HTTP {r.status_code}")
            return None
        try:
            data = r.json()
            ok(name)
            return data
        except Exception:
            fail(name, "Response is not valid JSON")
            return None
    except Exception as e:
        fail(name, str(e))
        return None

# ── Test groups ───────────────────────────────────────────────────────────────

def test_pages():
    section("Page availability")
    pages = [
        ("/",                  "Home"),
        ("/about/",            "About"),
        ("/faq/",              "FAQ"),
        ("/contact/",          "Contact"),
        ("/license/",          "License"),
        ("/setup/",            "New project setup"),
        ("/sharedbuilds/",     "Shared builds"),
        ("/encyclopedia/",     "Encyclopedia"),
        ("/login_page/",       "Login page"),
        ("/register/",         "Register page"),
        ("/robots.txt",        "robots.txt"),
        ("/sitemap.xml",       "sitemap.xml"),
    ]
    for path, name in pages:
        check_status(name, path)

def test_versioned_pages():
    section("Multi-version routing")
    check_status("dofus3 home (/)", "/", 200)
    version_prefixes = [
        ("beta", "/beta/"),
        ("dofus2", "/dofus2/"),
        ("retro", "/retro/"),
        ("touch", "/touch/"),
    ]
    for version_name, prefix in version_prefixes:
        check_status(f"{version_name} home", prefix, 200)
        check_status(f"{version_name} setup", f"{prefix}setup/", 200)
        check_status(f"{version_name} encyclopedia", f"{prefix}encyclopedia/", 200)
        check_status(f"{version_name} shared builds", f"{prefix}sharedbuilds/", 200)

def test_static_files():
    section("Static files")
    statics = [
        ("/static/chardata/changelog_lighttheme.css", "Changelog light CSS"),
        ("/static/chardata/changelog_darktheme.css",  "Changelog dark CSS"),
        ("/static/chardata/changelog.js",             "Changelog JS"),
        ("/static/chardata/common_lighttheme.css",    "Common light CSS"),
        ("/static/chardata/common_darktheme.css",     "Common dark CSS"),
    ]
    for path, name in statics:
        check_status(name, path)

def test_changelog():
    section("Changelog modal")
    try:
        r = get("/")
        html = r.text
        checks = [
            ("Modal container present",   'id="changelog-modal"'),
            ("Overlay present",           'id="changelog-overlay"'),
            ("Footer button present",     'openChangelog()'),
            ("Changelog JS linked",       'changelog.js'),
            ("Changelog CSS linked",      'changelog-css'),
            ("Dofus 3.0 era entry",       'Dofus 3.0'),
            ("Dofus 3.3 era entry",       'Dofus 3.3'),
            ("Dofus 3.5 era entry",       'Dofus 3.5'),
        ]
        count = html.count('cl-entry')
        if count >= 15:
            ok(f"Has {count} changelog entries (min 15)")
        else:
            fail(f"Changelog entries count", f"only {count} cl-entry divs found (min 15)")
        for name, needle in checks:
            if needle in html:
                ok(name)
            else:
                fail(name, f"'{needle}' not found in page")
    except Exception as e:
        fail("Changelog modal tests", str(e))

def test_changelog_translations():
    section("Changelog translations")
    lang_checks = [
        ("fr", "Décembre 2024",       "French — December 2024"),
        ("fr", "Dofus 3.0",           "French — Dofus 3.0 badge"),
        ("fr", "Mise à jour Dofus",   "French — Dofus 3.x title"),
        ("de", "Dezember 2024",       "German — December 2024"),
        ("de", "Kompatibilitäts",     "German — compatibility entry"),
        ("es", "Diciembre",           "Spanish — December 2024"),
        ("pt", "Dezembro",            "Portuguese — December 2024"),
    ]
    for lang, needle, name in lang_checks:
        check_contains(name, "/", needle, cookies={"django_language": lang})

def test_encyclopedia():
    section("Encyclopedia")
    check_status("Encyclopedia main page", "/encyclopedia/")
    check_contains("Search results for 'gelano'", "/encyclopedia/?search=gelano",
                   "encyclopedia-page-link")
    check_contains("Search results for 'bouftou'", "/encyclopedia/?search=bouftou",
                   "encyclopedia")
    # Ensure a known item page loads — find a real ankama_id from search
    try:
        r = get("/encyclopedia/?search=Bouftou+Amulet")
        m = re.search(r'/encyclopedia/item/([^/]+)/(\d+)-([^/]+)/', r.text)
        if m:
            item_path = f"/encyclopedia/item/{m.group(1)}/{m.group(2)}-{m.group(3)}/"
            check_status("Encyclopedia item page", item_path)
        else:
            skip("Encyclopedia item page", "no item link found in search results")
    except Exception as e:
        fail("Encyclopedia item page", str(e))

def test_shared_builds():
    section("Shared builds")
    try:
        r = get("/sharedbuilds/")
        if r.status_code != 200:
            fail("Shared builds page", f"HTTP {r.status_code}")
            return
        ok("Shared builds page loads")
        if "build-card" in r.text or "shared" in r.text.lower():
            ok("Shared builds page has expected content")
        else:
            fail("Shared builds page has expected content", "no 'build-card' or 'shared'")
    except Exception as e:
        fail("Shared builds", str(e))

def test_spell_simulator():
    section("Spell simulator")
    # The spells view needs a char_id; /spells/1/ redirects or errors gracefully
    try:
        r = get("/spells/1/")
        if r.status_code in (200, 302, 404):
            ok(f"Spell simulator at /spells/1/ (HTTP {r.status_code})")
        else:
            fail("Spell simulator at /spells/1/", f"HTTP {r.status_code}")
    except Exception as e:
        fail("Spell simulator", str(e))

def test_i18n():
    section("Internationalisation")
    langs = ["fr", "de", "es", "pt"]
    for lang in langs:
        try:
            r = get("/", cookies={"django_language": lang})
            if r.status_code == 200 and "<html" in r.text.lower():
                ok(f"Language '{lang}' — page renders without error")
            else:
                fail(f"Language '{lang}'", f"HTTP {r.status_code}")
        except Exception as e:
            fail(f"Language '{lang}'", str(e))

def test_optimizer_flow():
    """
    Light smoke-test of the optimizer flow:
      1. GET /setup/ to seed CSRF cookie
      2. POST /createproject/ to create an anonymous build
      3. POST /fashion/{id}/ to trigger the optimizer
      4. GET /solution/{id}/ to load the result page
    Uses minimal params (level 200, Sacrieur, AP-only target) so PuLP is fast.
    """
    section("Optimizer flow (smoke test)")
    try:
        # Step 1: get CSRF
        r = get("/setup/")
        if r.status_code != 200:
            skip("Optimizer flow", f"/setup/ returned {r.status_code}")
            return
        token = get_csrf_from_page(r.text)
        if not token:
            skip("Optimizer flow", "no CSRF token found on /setup/")
            return
        ok("CSRF token obtained")

        # Step 2: create project
        r = post("/createproject/", data={
            "csrfmiddlewaretoken": token,
            "char_name": "test_auto",
            "char_level": "200",
            "char_class": "1",   # Feca (index 1)
            "game_version": "dofus3",
        })
        if r.status_code not in (200, 302):
            fail("Create project", f"HTTP {r.status_code}")
            return
        ok("Create project POST accepted")

        # Extract char_id from the response URL or body
        char_id = None
        m = re.search(r'/(?:setup|stats|solution)/(\d+)/', r.url or "")
        if not m:
            m = re.search(r'/(?:setup|stats|solution|options|min_stats)/(\d+)/', r.text)
        if m:
            char_id = m.group(1)
        else:
            skip("Optimizer run", "could not extract char_id from createproject response")
            return
        ok(f"char_id = {char_id} extracted")

        # Step 3: trigger optimizer
        r2 = get(f"/setup/") # refresh CSRF
        token2 = get_csrf_from_page(r2.text) or token
        r = post(f"/fashion/{char_id}/", data={
            "csrfmiddlewaretoken": token2,
        }, timeout=120)
        if r.status_code not in (200, 302):
            fail("Optimizer run", f"HTTP {r.status_code}")
            return
        ok("Optimizer run accepted")

        # Step 4: solution page
        r = get(f"/solution/{char_id}/", timeout=30)
        if r.status_code == 200:
            if "solution" in r.text.lower() or "item" in r.text.lower():
                ok("Solution page renders with content")
            else:
                fail("Solution page renders with content", "no 'solution' or 'item' in body")
        else:
            fail("Solution page", f"HTTP {r.status_code}")
    except Exception as e:
        fail("Optimizer flow", str(e))

def test_error_pages():
    section("Error handling")
    check_status("403 page", "/403/")
    check_status("404 page", "/404/")
    check_status("500 page", "/500/")
    # A genuinely missing page should return 404
    r = check_status("Unknown URL -> 404", "/this-page-does-not-exist/", expected=404)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global BASE

    parser = argparse.ArgumentParser(description="DofusFashionistaVanced website tests")
    parser.add_argument("--url", default="http://localhost:8000",
                        help="Base URL of the running server (default: http://localhost:8000)")
    parser.add_argument("--skip-optimizer", action="store_true",
                        help="Skip the slow optimizer smoke test")
    args = parser.parse_args()

    BASE = args.url.rstrip("/")

    print(f"\n{BOLD}DofusFashionistaVanced — automated tests{RESET}")
    print(f"Target: {CYAN}{BASE}{RESET}\n")

    # Quick connectivity check
    try:
        r = requests.get(BASE + "/", timeout=5)
    except Exception as e:
        print(f"{RED}Server not reachable at {BASE}: {e}{RESET}")
        sys.exit(1)

    t0 = time.time()

    test_pages()
    test_versioned_pages()
    test_static_files()
    test_changelog()
    test_changelog_translations()
    test_encyclopedia()
    test_shared_builds()
    test_spell_simulator()
    test_i18n()
    if not args.skip_optimizer:
        test_optimizer_flow()
    test_error_pages()

    elapsed = time.time() - t0

    print(f"\n{'-'*50}")
    total = len(_passed) + len(_failed) + len(_skipped)
    print(f"{BOLD}Results:{RESET} "
          f"{GREEN}{len(_passed)} passed{RESET}, "
          f"{RED}{len(_failed)} failed{RESET}, "
          f"{YELLOW}{len(_skipped)} skipped{RESET} "
          f"/ {total} total  ({elapsed:.1f}s)")

    if _failed:
        print(f"\n{RED}{BOLD}Failed tests:{RESET}")
        for name in _failed:
            print(f"  {RED}[FAIL] {name}{RESET}")

    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
