import logging
import os
import random
import time
from pathlib import Path
from django.conf import settings
from django.utils import timezone
from dotenv import load_dotenv
from rest_framework.response import Response
from rest_framework import status

load_dotenv()

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
from scraper.services.job_service import JobService
from scraper.services.result_service import ResultService
from scraper.services.proxy_rotation_service import ProxyRotationService

logger = logging.getLogger(__name__)


class ScraperService:
    def __init__(self):
        self.job_service = JobService()
        self.result_service = ResultService()
        self.proxy_rotation = ProxyRotationService()

        self.config = {
            "timeouts": {
                "navigation": 60000,
                "element": 10000,
                "test": 30000,
                "chatgpt": 90000,
            }
        }
        
        # print(f"config: {self.config}")
        
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        ]
        
        self.viewports = [
            {"width": 1280, "height": 800},
            {"width": 1440, "height": 900},
            {"width": 1600, "height": 900},
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
        ]
        
        # self.USER_AGENTS = [
        #     # Windows - Chrome
        #     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        #     "AppleWebKit/537.36 (KHTML, like Gecko) "
        #     "Chrome/115.0.0.0 Safari/537.36",

        #     "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) "
        #     "Gecko/20100101 Firefox/115.0",

        #     # Windows - Edge
        #     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        #     "AppleWebKit/537.36 (KHTML, like Gecko) "
        #     "Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.183",

        #     # Mac - Chrome
        #     "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) "
        #     "AppleWebKit/537.36 (KHTML, like Gecko) "
        #     "Chrome/115.0.0.0 Safari/537.36",

        #     # Mac - Safari
        #     "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) "
        #     "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        #     "Version/16.4 Safari/605.1.15",

        #     # Mac - Firefox
        #     "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.3; rv:115.0) "
        #     "Gecko/20100101 Firefox/115.0",

        #     # Android - Chrome
        #     "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
        #     "AppleWebKit/537.36 (KHTML, like Gecko) "
        #     "Chrome/115.0.0.0 Mobile Safari/537.36",

        #     "Mozilla/5.0 (Linux; Android 12; SM-G991B) "
        #     "AppleWebKit/537.36 (KHTML, like Gecko) "
        #     "Chrome/115.0.0.0 Mobile Safari/537.36",

        #     # iPhone - Safari
        #     "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) "
        #     "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        #     "Version/16.5 Mobile/15E148 Safari/604.1",

        #     # iPad - Safari
        #     "Mozilla/5.0 (iPad; CPU OS 16_5 like Mac OS X) "
        #     "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        #     "Version/16.5 Mobile/15E148 Safari/604.1"
        # ]
        
        # Ensure screenshot dirs exist
        base = Path(getattr(settings, "BASE_DIR", Path.cwd()))
        self.result_dir = base / "public" / "images" / "result"
        self.error_dir = base / "public" / "images" / "error"
        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.error_dir.mkdir(parents=True, exist_ok=True)

    # -------------------- Public API (Node: scrapeKeyword) --------------------
        
    # def scrape_keyword(self, keyword, method="auto", tool_type="google", options=None, job_id=None):
    #     """
    #     Port of Node's scrapeKeyword (sync version).
    #     """
    #     options = options or {}
    #     job = None
    #     start_time = time.time()

    #     try:
    #         if job_id:
    #             job = self.job_service.update_job(
    #                 job_id,
    #                 updates={
    #                     "status": "running",
    #                     "started_at": timezone.now()
    #                 }
    #             )

    #         logger.info(f'Starting scrape for "{keyword}" with method={method} tool_type={tool_type}')

    #         methods = self._get_method_order(method)
    #         result = None
    #         last_error = None
    #         method_used = None

    #         for method_name in methods:
    #             try:
    #                 logger.info(f"Attempting method: {method_name}")
    #                 result = self._scrape_with_method(keyword, method_name, tool_type, options)
    #                 if result:
    #                     result["method"] = method_name
    #                     method_used = method_name
    #                     break
    #             except Exception as e:
    #                 logger.warning(f"Method {method_name} failed: {e}")
    #                 last_error = e
    #                 continue

    #         if not result:
    #             raise RuntimeError(f"All methods failed. Last error: {getattr(last_error, 'args', [''])[0]}")

    #         # augment metadata
    #         result.setdefault("metadata", {})
    #         result["metadata"].update({
    #             "duration": int((time.time() - start_time) * 1000),
    #             "methodUsed": method_used,
    #             "timestamp": timezone.now().isoformat(),
    #             "success": True,
    #         })

    #         # save result
    #         if options.get("saveResults", True) is not False:
    #             self.result_service.save_result(
    #                 keyword=keyword,
    #                 method=method_used,
    #                 data=result,
    #                 job_id=job_id,
    #                 created_at=timezone.now(),
    #                 user_id=getattr(job, "user_id", None) if job else None,
    #             )

    #         # mark job as completed
    #         if job:
    #             self.job_service.update_job(
    #                 job_id,
    #                 status="completed",
    #                 results=result,
    #                 completed_at=timezone.now(),
    #                 progress=100,
    #             )

    #         logger.info(f'Successfully scraped "{keyword}" in {int((time.time() - start_time) * 1000)}ms')
    #         return result

    #     except Exception as e:
    #         logger.error(f'Scraping failed for "{keyword}": {e}', exc_info=True)
    #         if job:
    #             self.job_service.update_job(
    #                 job_id,
    #                 status="failed",
    #                 error=str(e),
    #                 completed_at=timezone.now(),
    #             )
    #         raise
    
    def scrape_keyword(self, keyword, method="auto", tool_type="google", options=None, job_id=None):
        """
        Updated scrape_keyword with proper JobService updates and SCRAPING_BROWSER_AUTHS rotation.
        """
        options = options or {}
        job = None
        start_time = time.time()

        try:
            # Rotate SCRAPING_BROWSER_AUTHS
            # auths_env = os.getenv("SCRAPING_BROWSER_AUTHS", "")
            # auth_list = [a.strip() for a in auths_env.split(",") if a.strip()]
            # if auth_list:
            #     auth = random.choice(auth_list)
            #     options["scraping_browser_auth"] = auth
            # else:
            #     logger.warning("⚠️ No SCRAPING_BROWSER_AUTHS configured")

            # Update job status to running
            if job_id:
                job = self.job_service.update_job(
                    job_id,
                    updates={
                        "status": "running",
                        "started_at": timezone.now()
                    }
                )

            # logger.info(f'Starting scrape for "{keyword}" with method={method} tool_type={tool_type}')
            print(f'Starting scrape for "{keyword}" with method={method} tool_type={tool_type}')

            methods = self._get_method_order(method)
            result = None
            last_error = None
            method_used = None

            for method_name in methods:
                try:
                    # logger.info(f"Attempting method: {method_name}")
                    print(f"Attempting method: {method_name}")
                    result = self._scrape_with_method(keyword, method_name, tool_type, options)
                    if result:
                        result["method"] = method_name
                        method_used = method_name
                        break
                except Exception as e:
                    logger.warning(f"Method {method_name} failed: {e}")
                    last_error = e
                    continue

            if not result:
                raise RuntimeError(f"\nAll methods failed. Last error: {getattr(last_error, 'args', [''])[0]}")

            # augment metadata
            result.setdefault("metadata", {})
            result["metadata"] = {
                "duration": int((time.time() - start_time) * 1000),
                "methodUsed": method_used,
                "timestamp": timezone.now().isoformat(),
                "success": True,
            }   

            # save result
            if options.get("saveResults", True) is not False:
                self.result_service.save_result(
                    keyword=keyword,
                    method=method_used,
                    data=result,
                    job_id=job_id,
                    created_at=timezone.now(),
                    user_id=getattr(job, "user_id", None) if job else None,
                )

            # mark job as completed
            if job:
                self.job_service.update_job(
                    job_id,
                    updates={
                        "status": "completed",
                        "results": result,
                        "completed_at": timezone.now(),
                        "progress": 100,
                    }
                )

            # logger.info(f'Successfully scraped "{keyword}" in {int((time.time() - start_time) * 1000)}ms')
            print(f'Successfully scraped "{keyword}" in {int((time.time() - start_time) * 1000)}ms')
            return result

        except Exception as e:
            # logger.error(f'Scraping failed for "{keyword}": {e}', exc_info=True)
            print(f'Scraping failed for "{keyword}": {e}')
            if job:
                self.job_service.update_job(
                    job_id,
                    updates={
                        "status": "failed",
                        "error": str(e),
                        "completed_at": timezone.now(),
                    }
                )
            raise

    # -------------------- Method selection (Node: _getMethodOrder) --------------------

    def _get_method_order(self, method: str):
        if method == "scraping_browser":
            return ["scrapingBrowser"]
        if method == "residential_proxy":
            return ["residentialProxy"]
        return ["scrapingBrowser", "residentialProxy"]  # default auto

    # -------------------- Dispatcher (Node: _scrapeWithMethod) --------------------

    def _scrape_with_method(self, keyword, method, tool_type, options):
        if method == "scrapingBrowser":
            if tool_type == "google":
                return self._scrape_with_scraping_browser(keyword, options)
            elif tool_type == "chatgpt":
                raise NotImplementedError("chatgpt method not yet ported")
            elif tool_type == "perplexity":
                raise NotImplementedError("perplexity method not yet ported")
            else:
                return {"error": "tool type not matched"}
        elif method == "residentialProxy":
            # Your Node fallback currently reuses scraping browser
            if tool_type in {"google", "chatgpt", "perplexity"}:
                return self._scrape_with_scraping_browser(keyword, options)
            return {"error": "tool type not matched"}
        else:
            raise RuntimeError(f"Unknown scraping method: {method}")

    # -------------------- Google via Bright Data Scraping Browser --------------------

    def _scrape_with_scraping_browser(self, keyword, options, location="new_york"):
        # logger.info("🌐 Using Scraping Browser method")
        # logger.info("🔍 Google AI with Scraping Browser (Rotated)")
        print("🌐 Using Scraping Browser method")
        print("🔍 Google AI with Scraping Browser (Rotated)")

        # proxy_config = self.proxy_rotation.get_healthy_scraping_browser()
        browser = None

        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                # SCRAPING_BROWSER_AUTHS=
                # brd-customer-hl_6f60e14f-zone-scraping_browser40_local:6lrx6el14z7d,
                # brd-customer-hl_6f60e14f-zone-local_scraping_browser40:yykw61oh57t1,
                # brd-customer-hl_6f60e14f-zone-scraping_browser42_local:ekcd14bqfgsw,
                # brd-customer-hl_6f60e14f-zone-scraping_browser43_local:y1w019szrbod,
                # brd-customer-hl_6f60e14f-zone-scraping_browser44_local:ot3gwihnmbud
               
                # connect over CDP
                browser = p.chromium.connect_over_cdp("wss://brd-customer-hl_6f60e14f-zone-scraping_browser44_local:ot3gwihnmbud@brd.superproxy.io:9222/")
                # proxy_config["endpoint"]
                # browser = p.chromium.connect_over_cdp(proxy_config["endpoint"])
                user_agent = random.choice(self.user_agents)
                viewport = random.choice(self.viewports)
                print(f"---------------user agent: {user_agent}, viewport: {viewport}---------------")
                context = browser.new_context(
                    viewport=viewport,
                    user_agent= user_agent,
                    locale="en-US",
                    timezone_id="America/New_York",
                    ignore_https_errors=True,
                )
                
                page = context.new_page()

                LOCATIONS = {
                    "amsterdam": {"lat": 52.377956, "lon": 4.89707},
                    "london": {"lat": 51.509865, "lon": -0.118092},
                    "new_york": {"lat": 40.73061, "lon": -73.935242},
                    "paris": {"lat": 48.864716, "lon": 2.349014},
                    "mumbai": {"lat": 19.07609, "lon": 72.877426},
                }
                loc = LOCATIONS.get(location)
                if not loc:
                    raise RuntimeError("Unknown location for proxy")

                # CDP session to set proxy location (Bright Data specific)
                client = context.new_cdp_session(page)
                client.send("Proxy.setLocation", {
                    "lat": loc["lat"],
                    "lon": loc["lon"],
                    "distance": 100,
                    "strict": True,
                })
                
                # Accept-Language via context headers
                context.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})

                # test connection
                self._test_connection(page, "Scraping Browser")

                # core scraping
                result = self._perform_scraping(page, keyword, options)

                # mark healthy
                # self.proxy_rotation.update_proxy_health("scrapingBrowser", proxy_config["id"], True)

                if result:
                    result["proxyUsed"] = {
                        "type": "scrapingBrowser",
                        # "id": proxy_config["id"],
                        # "location": proxy_config["location"],
                    }
                return result

            except Exception as e:
                # mark unhealthy
                # self.proxy_rotation.update_proxy_health("scrapingBrowser", proxy_config["id"], False, str(e))
                print(f"Error in scrape with scraping browser: {e}")
                raise
            finally:
                try:
                    if browser:
                        browser.close()
                except Exception:
                    pass

    # -------------------- Helpers: connection, consent, search, extract --------------------

    def _test_connection(self, page, method_label):
        try:
            page.goto("https://www.google.com", timeout=self.config["timeouts"]["test"], wait_until="domcontentloaded")
            # logger.info(f"✅ Connection successful with {method_label}")
            print(f"✅ Connection successful with {method_label}")
        except Exception as e:
            logger.error(f"❌ Connection failed with {method_label}: {e}")
            print(f"❌ Connection failed with {method_label}: {e}")
            raise RuntimeError(f"Connection test failed with {method_label}: {e}")

    def _perform_scraping(self, page, keyword, options):
        # logger.info(f'🔍 Performing scraping for "{keyword}"')
        print(f'🔍 Performing scraping for "{keyword}"')

        # consent
        self._handle_consent(page)

        # search
        res_image_name = self._perform_search(page, keyword)
        logger.debug(f"search screenshot: {res_image_name}")

        # extract AI Overview
        response = self._extract_ai_overview(page, options, res_image_name)

        if not response:
            logger.warning(f'⚠️ No AI Overview found for "{keyword}"')
            return None

        return {
            "keyword": keyword,
            "response": response,
            "extractedAt": timezone.now().isoformat(),
            "success": True,
        }

    def _handle_consent(self, page):
        try:
            page.wait_for_timeout(2000)
            consent_selectors = [
                'button[aria-label="Accept all"]',
                'button:has-text("Accept all")',
                'button:has-text("I agree")',
                'button:has-text("Accept")',
                "#L2AGLb",
                'form[action*="consent"] button[type="submit"]',
                'button[data-ved*="accept"]',
            ]
            for selector in consent_selectors:
                try:
                    btn = page.wait_for_selector(selector, timeout=3000, state="visible")
                    if btn:
                        btn.click()
                        page.wait_for_timeout(2000)
                        # logger.info("✅ Consent dialog handled")
                        print("✅ Consent dialog handled")
                        break
                except PWTimeoutError:
                    continue
                except Exception:
                    continue
        except Exception:
            # logger.info("ℹ️ No consent dialog found or already handled")
            print("ℹ️ No consent dialog found or already handled")

    def _perform_search(self, page, keyword):
        search_selectors = [
            'input[name="q"]',
            'textarea[name="q"]',
            'input[role="combobox"]',
            "#APjFqb",
            'input[title="Search"]',
        ]
        search_box = None
        used_selector = None

        for selector in search_selectors:
            try:
                search_box = page.wait_for_selector(selector, timeout=self.config["timeouts"]["element"], state="visible")
                if search_box:
                    used_selector = selector
                    # logger.info(f"✅ Found search box with selector: {selector}")
                    print(f"✅ Found search box with selector: {selector}")
                    break
            except Exception:
                continue

        if not search_box:
            # debug screenshot
            img = self.error_dir / f"debug_no_searchbox_{int(time.time()*1000)}.png"
            page.screenshot(path=str(img), full_page=True)
            raise RuntimeError("Search box not found")

        # clear + type
        search_box.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        page.wait_for_timeout(500)

        # type like human
        for ch in keyword:
            page.type(used_selector, ch, delay=80 + int(random.random() * 120))

        page.wait_for_timeout(1000 + int(random.random() * 500))
        page.keyboard.press("Enter")

        # wait results
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000 + int(random.random() * 2000))

        img = self.result_dir / f"result_{int(time.time()*1000)}.png"
        page.screenshot(path=str(img), full_page=True)
        # logger.info("✅ Search completed successfully")
        print("✅ Search completed successfully")
        return str(img)

    def _extract_ai_overview(self, page, options, res_image_name):
        selectors = [
            "[data-subtree='mfc']",
            "div.YzCcne",
            "div[data-attrid*='ai']",
            "div.kCrYT",
            ".AI-overview",
            "[data-mcpr]",
            "div.V3FYCf",
            "div.kCrYT",
        ]
        ai_box = None
        found_selector = None

        for selector in selectors:
            try:
                els = page.query_selector_all(selector)
                for el in els:
                    txt = (el.text_content() or "").strip()
                    html = el.inner_html() or ""
                    if txt and len(txt) > 100 and (
                        "overview" in txt.lower()
                        or "according to" in txt.lower()
                        or "based on" in txt.lower()
                        or "data-snhf" in html
                        or "ai" in html.lower()
                        or len(txt.split()) > 20
                    ):
                        ai_box = el
                        found_selector = selector
                        # logger.info(f"✅ Found potential AI Overview via selector: {selector}")
                        # logger.debug(f"📝 Text preview: {txt[:150]}...")
                        print(f"✅ Found potential AI Overview via selector: {selector}")
                        print(f"📝 Text preview: {txt[:150]}...")
                        break
                if ai_box:
                    break
            except Exception:
                continue

        # always capture a page screenshot too
        img = self.result_dir / f"result_{int(time.time()*1000)}.png"
        page.screenshot(path=str(img), full_page=True)
        res_image_name = str(img)

        if not ai_box:
            return None

        # logger.info("📤 Extracting AI Overview content...")
        print("📤 Extracting AI Overview content...")

        # Use JS in the page context (identical to your Node evaluate code)
        js_func = """(box, resImage) => {
          const excludedClasses = ["YWpX0d","source-info","citation","metadata"];
          function hasExcludedParent(el) {
            while (el && el !== box) {
              if (el.classList && Array.from(el.classList).some(cls => excludedClasses.includes(cls))) return true;
              el = el.parentElement;
            }
            return false;
          }
          let cleanTextParts = [];
          function collectTextNodes(node) {
            if (node.nodeType === Node.ELEMENT_NODE && ["SCRIPT","STYLE","NOSCRIPT","TEMPLATE"].includes(node.tagName)) {
              return;
            }
            if (node.nodeType === Node.TEXT_NODE && node.textContent.trim().length > 2 && !hasExcludedParent(node.parentElement)) {
              cleanTextParts.push(node.textContent.trim());
            }
            node.childNodes && Array.from(node.childNodes).forEach(child => collectTextNodes(child));
          }
          collectTextNodes(box);

          const fullText = cleanTextParts
            .join(" ")
            .split("\\n")
            .filter(line => !line.trim().startsWith("window.CSS")
              && !line.includes("registerProperty")
              && !line.includes("{")
              && !line.includes("}")
              && !line.trim().endsWith(";"))
            .join(" ")
            .replace(/\\s{2,}/g, " ")
            .trim();

          const dataMcprValues = [];
          box.querySelectorAll(".LT6XE, [data-mcpr]").forEach(el => {
            const val = el.getAttribute("data-mcpr");
            if (val && !dataMcprValues.includes(val)) dataMcprValues.push(val);
          });

          const links = Array.from(box.querySelectorAll("a[href]"))
            .map(a => {
              const linkText = (a.innerText || "").trim();
              const ariaLabel = a.getAttribute("aria-label") || "";
              const titleAttr = a.getAttribute("title") || "";
              return (linkText || ariaLabel) ? {
                title: ariaLabel || titleAttr || linkText,
                href: a.href
              } : null;
            })
            .filter(Boolean);

          return {
            markdown: (box.innerText || "").trim(),
            rawText: fullText,
            html: box.innerHTML,
            links,
            data_mcpr_values: dataMcprValues,
            selector: box.tagName + (box.className ? "." + box.className.split(" ").join(".") : ""),
            boundingBox: box.getBoundingClientRect(),
            wordCount: (fullText || "").split(/\\s+/).length,
            characterCount: (fullText || "").length,
            images: resImage
          };
        }"""

        ai_content = ai_box.evaluate(js_func, res_image_name)

        # logger.info("🎉 AI OVERVIEW FOUND")
        # logger.info(f"📍 Selector used: {found_selector}")
        print("🎉 AI OVERVIEW FOUND")
        print(f"📍 Selector used: {found_selector}")
        
        if ai_content and ai_content.get("rawText"):
            # logger.info(f"📝 Clean text length: {len(ai_content['rawText'])} chars")
            # logger.info(f"🔗 Links found: {len(ai_content.get('links', []))}")
            # logger.debug(f"Preview:\n{ai_content['rawText'][:300]}{'...' if len(ai_content['rawText'])>300 else ''}")
            
            print(f"📝 Clean text length: {len(ai_content['rawText'])} chars")
            print(f"🔗 Links found: {len(ai_content.get('links', []))}")
            print(f"Preview:\n{ai_content['rawText'][:300]}{'...' if len(ai_content['rawText'])>300 else ''}")

        return ai_content