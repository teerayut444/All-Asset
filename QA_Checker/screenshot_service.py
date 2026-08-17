import os
import hashlib
import asyncio
import re
from typing import Dict, Any, List
from playwright.async_api import async_playwright

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(CURRENT_DIR, "cache", "screenshots")
os.makedirs(CACHE_DIR, exist_ok=True)

def get_url_cache_path(url: str, property_id: str = "") -> str:
    """Generate a stable, safe file path for caching screenshots."""
    clean_id = re.sub(r'[^a-zA-Z0-9_-]', '_', str(property_id).strip())
    url_hash = hashlib.md5(url.strip().encode('utf-8')).hexdigest()[:10]
    if clean_id and clean_id not in ["nan", "None", ""]:
        filename = f"{clean_id}_{url_hash}.png"
    else:
        filename = f"asset_{url_hash}.png"
    return os.path.join(CACHE_DIR, filename)

UNIVERSAL_CLEANER_JS = """
(() => {
    // 1. Remove by specific known class, ID, and tag selectors
    const selectors = [
        '.disclaimer', '[class*="disclaimer" i]', '[id*="disclaimer" i]',
        '#privacyModal', '.v3_modal', '.modal', '.modal-backdrop', '.fade',
        '[id*="cookie" i]', '[class*="cookie" i]',
        '[id*="consent" i]', '[class*="consent" i]',
        '[id*="privacy" i]', '[class*="privacy" i]',
        '[id*="pdpa" i]', '[class*="pdpa" i]',
        '[aria-label*="cookie" i]', '[aria-label*="consent" i]',
        '.swal2-container', '.swal2-shown',
        '#onetrust-consent-sdk', '.onetrust-pc-dark-filter',
        '#CybotCookiebotDialog', '#CybotCookiebotDialogBodyUnderlay',
        'div[class*="ConsentDialog"]', 'div[class*="CookieBanner"]',
        'div[class*="cookie-popup"]', 'div[class*="cookie-bar"]',
        'div[class*="cookie-modal"]', 'div[class*="popup-cookie"]'
    ];

    selectors.forEach(sel => {
        try {
            document.querySelectorAll(sel).forEach(el => {
                const tag = el.tagName.toUpperCase();
                if (tag !== 'BODY' && tag !== 'HTML' && tag !== 'MAIN' && tag !== 'HEADER') {
                    el.remove();
                }
            });
        } catch(e) {}
    });

    // 2. Intelligent scan: remove any floating/fixed banner containing cookie/consent keywords
    const keywords = ['คุกกี้', 'cookie', 'pdpa', 'privacy', 'นโยบาย', 'ยอมรับ', 'consent', 'disclaimer', 'ข้อกำหนด'];
    document.querySelectorAll('*').forEach(el => {
        const tag = el.tagName.toUpperCase();
        if (tag === 'BODY' || tag === 'HTML' || tag === 'MAIN' || tag === 'HEADER') return;
        
        try {
            const style = window.getComputedStyle(el);
            const isFloating = style.position === 'fixed' || style.position === 'sticky' || parseInt(style.zIndex, 10) >= 99;
            if (isFloating) {
                const text = (el.innerText || el.textContent || '').toLowerCase();
                if (keywords.some(kw => text.includes(kw.toLowerCase()))) {
                    if (tag !== 'NAV' || text.includes('คุกกี้') || text.includes('privacy')) {
                        el.remove();
                    }
                }
            }
        } catch(e) {}
    });

    // 3. Unlock body & HTML scrolling
    try {
        document.body.classList.remove('modal-open');
        document.body.style.setProperty('overflow', 'auto', 'important');
        document.body.style.setProperty('padding-right', '0px', 'important');
        document.documentElement.style.setProperty('overflow', 'auto', 'important');
    } catch(e) {}
})();
"""

async def capture_single_url(
    url: str,
    property_id: str = "",
    force_refresh: bool = False,
    timeout_ms: int = 35000,
    full_page: bool = True
) -> Dict[str, Any]:
    """Capture a screenshot of a single URL using Playwright with stealth & universal cookie/popup removal."""
    url = str(url).strip()
    if not url or url.lower() in ["nan", "none", "-", ""]:
        return {
            "success": False,
            "url": url,
            "path": None,
            "error": "URL ว่างเปล่าหรือไม่ถูกต้อง",
            "is_cloudflare": False
        }
    
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    target_path = get_url_cache_path(url, property_id)
    
    if not force_refresh and os.path.exists(target_path) and os.path.getsize(target_path) > 1000:
        return {
            "success": True,
            "url": url,
            "path": target_path,
            "cached": True,
            "error": None,
            "is_cloudflare": False
        }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox"
                ]
            )
            context = await browser.new_context(
                viewport={"width": 1366, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="th-TH",
                ignore_https_errors=True
            )
            page = await context.new_page()
            
            try:
                await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
            except Exception:
                try:
                    await page.wait_for_timeout(1000)
                except Exception:
                    pass

            # Check if page is blocked by Cloudflare Turnstile / Bot detection
            is_cloudflare = False
            try:
                title = await page.title()
                content = await page.content()
                if "กำลังทำการตรวจสอบความปลอดภัย" in content or "Just a moment" in title or "Cloudflare" in title:
                    is_cloudflare = True
            except Exception:
                pass

            # Universal cookie and popup removal
            try:
                await page.evaluate(UNIVERSAL_CLEANER_JS)
                await page.wait_for_timeout(350)
                await page.evaluate(UNIVERSAL_CLEANER_JS)
            except Exception:
                pass

            # Capture screenshot
            await page.screenshot(path=target_path, full_page=full_page)
            await browser.close()
            
            if os.path.exists(target_path) and os.path.getsize(target_path) > 500:
                return {
                    "success": True,
                    "url": url,
                    "path": target_path,
                    "cached": False,
                    "error": None,
                    "is_cloudflare": is_cloudflare
                }
            else:
                return {
                    "success": False,
                    "url": url,
                    "path": None,
                    "error": "ไม่สามารถบันทึกไฟล์ภาพหน้าจอได้",
                    "is_cloudflare": is_cloudflare
                }

    except Exception as e:
        return {
            "success": False,
            "url": url,
            "path": None,
            "error": str(e),
            "is_cloudflare": False
        }

def capture_url_sync(url: str, property_id: str = "", force_refresh: bool = False, full_page: bool = True) -> Dict[str, Any]:
    """Synchronous wrapper for capture_single_url."""
    try:
        return asyncio.run(capture_single_url(url, property_id, force_refresh, full_page=full_page))
    except Exception as e:
        return {
            "success": False,
            "url": url,
            "path": None,
            "error": str(e),
            "is_cloudflare": False
        }
