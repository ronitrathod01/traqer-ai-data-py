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
import asyncio
import random
import time
import logging
from datetime import datetime
from playwright.async_api import async_playwright

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
        
        # Ensure screenshot dirs exist
        base = Path(getattr(settings, "BASE_DIR", Path.cwd()))
        self.result_dir = base / "public" / "images" / "result"
        self.error_dir = base / "public" / "images" / "error"
        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.error_dir.mkdir(parents=True, exist_ok=True)
    
    def scrape_keyword(self, keyword, method="auto", tool_type=None, options=None, job_id=None):
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
            print(f'---> Starting scrape for "{keyword}" with method={method} tool_type={tool_type}')

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
                    print(f"Method {method_name} failed: {e}")
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
                    metadata=result.get("metadata", {}),
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

    # -------------------- Method selection --------------------

    def _get_method_order(self, method: str):
        if method == "scraping_browser":
            return ["scrapingBrowser"]
        if method == "residential_proxy":
            return ["residentialProxy"]
        return ["scrapingBrowser", "residentialProxy"]  # default auto

    # -------------------- Dispatcher --------------------

    def _scrape_with_method(self, keyword, method, tool_type, options):
        if method == "scrapingBrowser":
            if tool_type == "google":
                return self._scrape_with_scraping_browser(keyword, options)
            elif tool_type == "chatgpt":
                return self.scrape_with_scraping_browser_chatgpt(keyword, options)
            elif tool_type == "perplexity":
                return self.scrape_with_scraping_browser_perplexity(keyword, options)
            else:
                return {"error": "tool type not matched"}
            
        elif method == "residentialProxy":
            if tool_type == "google":
                return self._scrape_with_scraping_browser(keyword, options)
            elif tool_type == "chatgpt":
                return self.scrape_with_scraping_browser_chatgpt(keyword, options)
            elif tool_type == "perplexity":
                return self.scrape_with_scraping_browser_perplexity(keyword, options)
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
                PROXY_USER = os.getenv("BRIGHT_DATA_USERNAME")
                PROXY_PASS = os.getenv("BRIGHT_DATA_PASSWORD")
                PROXY_HOST = os.getenv("BRIGHT_DATA_HOST", "brd.superproxy.io")
                PROXY_PORT = os.getenv("BRIGHT_DATA_PORT", "9222")
                
                proxy_url = f"wss://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
                # SCRAPING_BROWSER_AUTHS=
                # brd-customer-hl_6f60e14f-zone-scraping_browser40_local:6lrx6el14z7d,
                # brd-customer-hl_6f60e14f-zone-local_scraping_browser40:yykw61oh57t1,
                # brd-customer-hl_6f60e14f-zone-scraping_browser42_local:ekcd14bqfgsw,
                # brd-customer-hl_6f60e14f-zone-scraping_browser43_local:y1w019szrbod,
                # brd-customer-hl_6f60e14f-zone-scraping_browser44_local:ot3gwihnmbud
                # wss://brd-customer-hl_6f60e14f-zone-new_scraping_browser40:lefea6sa585c@brd.superproxy.io:9222/ 
                # wss://brd-customer-hl_6f60e14f-zone-new_scraping_browser40:lefea6sa585c@brd.superproxy.io:9222
                # connect over CDP
                browser = p.chromium.connect_over_cdp(proxy_url)
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
            # logger.error(f"❌ Connection failed with {method_label}: {e}")
            print(f"❌ Connection failed with {method_label}: {e}")
            raise RuntimeError(f"Connection test failed with {method_label}: {e}")

    def _perform_scraping(self, page, keyword, options):
        # logger.info(f'🔍 Performing scraping for "{keyword}"')
        print(f'🔍 Performing google scraping for "{keyword}"')

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
    
    def scrape_with_scraping_browser_chatgpt(self, keyword, options):
        print("🌐 Using Scraping Browser method")
        print("🔍 ChatGPT with Scraping Browser (Rotated)")
        
        # proxy_config = self.proxy_rotation.get_healthy_scraping_browser()
        browser = None

        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                PROXY_USER = os.getenv("BRIGHT_DATA_USERNAME")
                PROXY_PASS = os.getenv("BRIGHT_DATA_PASSWORD")
                PROXY_HOST = os.getenv("BRIGHT_DATA_HOST", "brd.superproxy.io")
                PROXY_PORT = os.getenv("BRIGHT_DATA_PORT", "9222")
                
                proxy_url = f"wss://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
                
                browser = p.chromium.connect_over_cdp(proxy_url)
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
                
                self._test_connection_chatgpt(page, "Residential Proxy")
                
                result = self._perform_scraping_chatgpt(page, keyword, options)
                
                # Mark proxy as healthy if successful
                # Add proxy info to result
                
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
                    
    def _test_connection_chatgpt(self, page, method):
        try:
            page.goto("https://chatgpt.com?model=gpt-4o", timeout=self.config["timeouts"]["test"])
            logger.info(f"✅ Connection successful with {method}")
            print(f"✅ Connection successful with {method}")
        except Exception as e:
            logger.error(f"❌ Connection failed with {method}: {e}")
            print(f"❌ Connection failed with {method}: {e}")
            raise

    def _perform_scraping_chatgpt(self, page, keyword, options):
        try:
            # logger.info(f"🔍 Performing scraping for keyword: '{keyword}'")
            print(f"🔍 Performing scraping for keyword: '{keyword}'")

            res_image_name = self._perform_search_chatgpt(page, keyword)
            response = self._get_chatgpt_response(page, options, res_image_name)

            if not response:
                logger.warning(f"⚠️ No ChatGPT response found for keyword: '{keyword}'")
                return None

            return {
                "keyword": keyword,
                "response": response,
                "extractedAt": datetime.utcnow().isoformat(),
                "success": True,
                "tool_type": "chatgpt",
            }
        except Exception as e:
            logger.error("❌ Scraping performance failed", exc_info=e)
            raise

    def _perform_search_chatgpt(self, page, keyword):
        try:
            searchSelectors = [
                "#prompt-textarea",
                'textarea[data-id="root"]',
                'textarea[placeholder*="message"]',
            ]
            
            try:
                web_search_button = page.wait_for_selector(
                    "[data-testid='composer-button-search']",
                    timeout=self.config["timeouts"]["element"],
                    state="visible"
                )
                
                print("✅ Clicked on web search button")
            except Exception as e:
                logger.error("❌ Search button not found or not clickable")
                print("❌ Search button not found or not clickable")
                raise e
            
            searchBox = None
            usedSelector = None
            
            for selector in searchSelectors:
                try:
                    searchBox = page.wait_for_selector(selector, timeout=self.config["timeouts"]['element'],state="visible")
                    if searchBox:
                        usedSelector = selector
                        print(f"✅ Found search box with selector: {selector}")
                        break
                except Exception as e:
                    continue
                
            if not searchBox:
                img = self.error_dir / f"debug_no_searchbox_{int(time.time()*1000)}.png"
                page.screenshot(path=str(img), full_page=True)
                raise RuntimeError("Search box not found")
            
            # Clear and type search query
            searchBox.click()
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            page.wait_for_timeout(500)
            
            # type like human
            for ch in keyword:
                page.type(usedSelector, ch, delay=80 + int(random.random() * 120))

            page.wait_for_timeout(1000 + int(random.random() * 500))
            page.keyboard.press("Enter")

            # wait results
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(10000 + int(random.random() * 2000))

            img = self.result_dir / f"ChatGPT_{int(time.time()*1000)}.png"
            page.screenshot(path=str(img), full_page=True)
            # logger.info("✅ Search completed successfully")
            print("✅ Search completed successfully")
            return str(img)
        except Exception as error:
            logger.error(f"Failed to send ChatGPT prompt: {error}")
            print(f"Failed to send ChatGPT prompt: {error}")
            raise error

    # async def close_gpt5_modal(self, page):
    #     modal = page.locator('[role="dialog"]')
    #     close_btn = modal.locator('button[data-testid="close-button"]')

    #     try:
    #         appeared = await modal.wait_for(state="attached", timeout=10000)
    #     except:
    #         return False

    #     for _ in range(3):
    #         try:
    #             await close_btn.wait_for(state="visible", timeout=2000)
    #             await close_btn.click()
    #             await modal.wait_for(state="detached", timeout=3000)
    #             logger.info("✅ GPT-5 popup closed")
    #             return True
    #         except:
    #             await asyncio.sleep(0.25)

    #     try:
    #         await page.keyboard.press("Escape")
    #         await modal.wait_for(state="detached", timeout=2000)
    #         return True
    #     except:
    #         return False

    def _get_chatgpt_response(self, page, options, res_image_name):
        logger.info("⏳ Waiting for ChatGPT response...")
        print("⏳ Waiting for ChatGPT response...")

        page.wait_for_timeout(1000)
        
        attempts = 0
        max_attempts = 60 # 60 sec max
        
        while attempts < max_attempts:
            stopBtn = page.query_selector('button[aria-label="Stop streaming"]')
            
            if not stopBtn:
                print(stopBtn, "stopBtn not visible")
                break
            page.wait_for_timeout(1000)
            
            attempts += 1
            
        sourcesBtn = None
        citations = []
        
        try:
            sourcesBtn = page.wait_for_selector("button[aria-label='Sources']",timeout = 5000, state = "visible")
            
            if sourcesBtn:
                print("✅ Sources button found. Clicking...")
                print("✅ Sources button found. Scrolling into view...")
                
                # Step 1: Scroll into view to try to avoid blockers
                
                sourcesBtn.scroll_into_view_if_needed()
                page.wait_for_timeout(500)
                
                # Step 2: Try click with fallback
                try:
                    sourcesBtn.click(timeout=3000)
                    print("✅ Sources button clicked successfully.")
                except Exception as click_error:
                    logger.warning("⚠️ Regular click failed. Trying force-click via DOM...")

                    # Step 3: Use force click via JS if blocked
                    # page.evaluate("(el) => el.click()", sourcesBtn)
                    page.evaluate("el => el.click()", sourcesBtn)

                    logger.info("✅ Sources button clicked using evaluate().")
                    
                # Extract citations
                
                citations = page.eval_on_selector_all(
                    'a[href^="http"]',
                    """links => links.map(a => ({
                        href: a.href,
                        title: a.querySelector("div.font-semibold")?.textContent.trim() || "Untitled"
                    }))"""
                )

                logger.info(f"🔗 Found {len(citations)} citations.")
                print(f"🔗 Found {len(citations)} citations.")
        except Exception as err:
            print("source button not found error:", err)
            logger.warning("❌ Sources button not found or citation section failed to load.")
            
        response_selectors = [
            'div[data-message-author-role="assistant"]',
            '[data-message-author-role="assistant"] .markdown',
            '[data-message-author-role="assistant"] div[class*="prose"]',
            '.group:last-child [data-message-author-role="assistant"]',
        ]
        
        response_element = None
        for selector in response_selectors:
            try:
                elements = page.query_selector_all(selector)
                if elements and len(elements) > 0:
                    response_element = elements[-1]  # Get latest
                    break
            except Exception:
                continue
            
        # ✅ Scroll down to the bottom of the response
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        logger.info("⬇️ Scrolled to bottom of page")

        # ✅ Wait a moment for all animations/images to load
        page.wait_for_timeout(10000)
        
        img = self.result_dir / f"ChatGPT_{int(time.time()*1000)}.png"
        page.screenshot(path=str(img), full_page=True)

        logger.info(f"📸 Screenshot saved as {img}")
        print(f"📸 Screenshot saved as {img}")
        
        if not response_element:
            print("No ChatGPT response found")
            return None
        
        response_text = response_element.text_content()
        
        # print("✅ ChatGPT response received (${responseText.length} characters")
        print(f"✅ ChatGPT response received ({len(response_text)} characters)")
        
        final_response = {
            "text": response_text,
            "clean_text": response_text,
            "html": response_text,
            "links": citations,
            "data_mcpr_values": "",
            "selector": "",
            "boundingBox": "",
            "wordCount": len((response_text or "").split()),
            "characterCount": len(response_text or ""),
            "images": res_image_name,
        }

        print("\n=== 🎉 ChatGPT Response FOUND ===")
        print(f"📍 Selector used: {response_element}")
        print(f"📝 Clean text length: {len(final_response['clean_text'])} characters")
        print(f"🔗 Links found: {len(final_response['links'])}")
        preview = final_response["clean_text"][:300]
        if len(final_response["clean_text"]) > 300:
            preview += "..."
        print(f"📄 Content preview:\n{preview}")

        return final_response
                
        
    def scrape_with_scraping_browser_perplexity(self, keyword, options, location="mumbai"):
        print("🌐 Using Scraping Browser method")
        print("🤖 Perplexity with Scraping Browser (Rotated)")
        
        browser = None
        
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                PROXY_USER = os.getenv("BRIGHT_DATA_USERNAME")
                PROXY_PASS = os.getenv("BRIGHT_DATA_PASSWORD")
                PROXY_HOST = os.getenv("BRIGHT_DATA_HOST", "brd.superproxy.io")
                PROXY_PORT = os.getenv("BRIGHT_DATA_PORT", "9222")
                
                proxy_url = f"wss://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
                
                browser = p.chromium.connect_over_cdp(proxy_url)
                user_agent = random.choice(self.user_agents)
                viewport = random.choice(self.viewports)
                
                context = browser.new_context(
                    viewport=viewport,
                    user_agent= user_agent,
                    locale="en-US",
                    timezone_id="America/New_York",
                    ignore_https_errors=True,
                )
                
                page = context.new_page()
                
                self._test_connection_perplexity(page, "Scraping Browser")
                
                page.wait_for_timeout(3000)
                
                result = self._perform_scraping_perplexity(page, keyword, options)
                
                # Mark proxy as healthy if successful
                # Add proxy info to result
                
                return result
                
            except Exception as e:
                # mark unhealthy
                # self.proxy_rotation.update_proxy_health("scrapingBrowser", proxy_config["id"], False, str(e))
                print(f"Error in scrape with scraping browser: {e}")
            finally:
                try:
                    if browser:
                        browser.close()
                except Exception:
                    pass
                
    def _test_connection_perplexity(self, page, method):
        try:
            page.goto("https://www.perplexity.ai/", timeout=self.config["timeouts"]["test"], wait_until="domcontentloaded")
            print(f"✅ Connection successful with {method}")
            
        except Exception as e:
            print(f"❌ Connection failed with {method}: {e}")
            raise ConnectionError
    
    def _perform_scraping_perplexity(self, page, keyword, options):
        try:
            print(f"🔍 Performing scraping for keyword: {keyword}")
            
            res_image_name = self._perform_search_perplexity(page, keyword)
             
            response = self._get_perplexity_response(page, options, res_image_name)
            
            if not response:
                print(f"No Perplexity response found for keyword: {keyword}")
                return None
            
            return {
                "keyword": keyword,
                "response": response,
                "extractedAt": datetime.utcnow().isoformat(),
                "success": True,
                "tool_type": "perplexity",      
            }
            
        except Exception as e:
            print(f"❌ Scraping performance failed:{e}")

            
    def _perform_search_perplexity(self, page, keyword):
        try:
            page.wait_for_timeout(2000)
            
            search_selectors = ["#ask-input"]
            
            used_selector = None
            search_box = None
            
            for selector in search_selectors:
                try:
                    search_box = page.wait_for_selector(selector, timeout=self.config["timeouts"]["element"], state= "visible")
                    if search_box:
                        used_selector=selector
                        print(f"✅ Found search box with selector: {selector}")
                        print(f"search box: {search_box}")
                        break
                except Exception as e:
                    continue
                
            if not search_box:
                img = self.error_dir / f"debug_no_searchbox_{int(time.time()*1000)}.png"
                page.screenshot(path=str(img), full_page=True)
                raise RuntimeError("search box not found")
                
            # Clear and type search query
            search_box.click()
            print("✅ Clicked on search box")
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            page.wait_for_timeout(500)
            
            for ch in keyword:
                page.type(used_selector, ch, delay=80 + int(random.random() * 120))
                
            print("✅ Finished typing the prompt")    
            page.wait_for_timeout(2000 + int(random.random() * 500))
            page.keyboard.press("Enter")
            
            print("✅ Perplexity prompt sent")
            
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(10000 + int(random.random() * 2000))
            
            img = self.result_dir / f"Perplexity_{int(time.time()*1000)}.png"
            page.screenshot(path=str(img), full_page=True)
            
            print("✅ Perplexity Search completed successfully")
            
            return str(img)
        except Exception as error:
            print(f"Failed to send perplexity prompt: {error}")
            raise error    
            
    
    def _get_perplexity_response(self, page, options, res_image_name):
        print("⏳ Waiting for Perplexity response...")
        
        page.wait_for_timeout(10000)
        
        attempts = 0 
        max_attemps = 60
        
        while attempts < max_attemps:
            stop_btn = page.query_selector('button[aria-label="Stop generating response"]')
    
            if not stop_btn:
                print(f"{stop_btn}, stop btn not visible")
                break
            
            page.wait_for_timeout(1000)
            attempts+=1
            
        response_selectors = ['div[id^="markdown-content-"]']
        response_element = None
        
        for selector in response_selectors:
            try:
                elements = page.query_selector_all(selector)
                if elements:
                    response_element = elements[-1]
                    break
                  
            except Exception as e:
                continue
            
        resultimg = self.result_dir / f"Perplexity_{int(time.time()*1000)}.png"
        page.screenshot(path=str(resultimg), full_page=True)
        # res_image_name = str(resultimg)
        
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        print("⬇️ Scrolled to bottom of page")
        
        page.wait_for_timeout(2000)
        
        timestamp = int(time.time() * 1000)
        image = self.result_dir / f"Perplexity_response_{int(time.time()*1000)}.png"
        page.screenshot(path=str(image), full_page=True)
        
        print(f"screenshot save as {image}")
        
        if not response_element:
            print("No perplexity response found.")
            return None
        
        response_text = response_element.text_content()
        
        print(f"✅ Perplexity response received ({len(response_text)} characters)")
        
        page.wait_for_timeout(5000)
        
        source_btn = None
        citation = []
        
        try:
           citation = page.eval_on_selector_all(
               'a[href^="http"]',
                """links => links.map(a => ({
                    href: a.href,
                    title: a.querySelector("div.font-semibold")?.textContent.trim() || "Untitled"
                }))"""
           )
           
           print(f"🔗 Found {len(citation)} citations.")
           for c in citation:
               print(f" - {c['title']}: {c['href']}")
        except Exception as e:
            print("source button not found error: ", e.message)
            print("❌ Sources button not found or citation section failed to load.")
            
        final_response = {
            "markdown": response_text,
            "rawText": response_text,
            "html": response_text,
            "links": citation,
            "data_mcpr_values": "",
            "selector": "",
            "boundingBox": "",
            "wordCount": len((response_text or "").split()), 
            "characterCount": len(response_text or ""),
            "image": res_image_name
        }
        
        print("\n=== Perplexity Response FOUND ===")
        print(f"📍 Selector used: ${response_element}")
        print(f"📝 Clean text length: {len(final_response['rawText'])} characters")
        print(f"🔗 Links found: {len(final_response['links'])}")

        preview = final_response["rawText"][:300]
        if len(final_response["rawText"]) > 300:
            preview += "..."
        print(f"📄 Content preview:\n{preview}")
        
        return final_response
    
    def scrape_batch(self, keywords, method="auto", options={}, jobid=None, tool_type=None):
        results = {}
        errors = {}
        delay = options.get("delay", 30000) / 1000
        max_concurrent = options.get("maxConcurrent", 1)
        processed = 0
        successful = 0
        failed = 0
        
        try:
            if jobid:
                self.job_service.update_job(jobid, updates={
                    "status": "running",
                    "started_at": timezone.utcnow(),
                    "progress": 0,
                })
                
                print(f"Starting batch scrape for {len(keywords)} keywords")
                
                for i in range(0, len(keywords), max_concurrent):
                    chunk = keywords[i:i +  max_concurrent]
                    
                    for index, keyword in enumerate(chunk):
                        try: 
                            print(f'Processing keyword {processed + index + 1}/{len(keywords)}: "{keyword}"')
                            result =  self.scrape_keyword(
                            keyword,
                            method,
                            tool_type,
                            {**options, "saveResults": False},
                            job_id=None,
                            )
                            
                            results[keyword] = result
                            succesful += 1
                            print(f'✅ Success for "{keyword}"')
                
                        except Exception as e:
                            print(f'❌ Failed for keyword "{keyword}": {str(e)}')
                            errors[keyword] = {
                                "error": str(e),
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                            faild += 1
                            
                    processed += len(chunk)    
                    
                    if jobid:
                        progress = round((processed / len(keywords)) * 100)
                        self.job_service.update_job(jobid, {
                        "progress": progress,
                        "processedItems": processed,
                        "results": {
                            "results": results,
                            "errors": errors,
                            "stats": {"successful": successful, "failed": failed, "total": len(keywords)},
                        },
                    })    
                    
                    print(f"Progress: {processed}/{len(keywords)} keywords processed "
                    f"({successful} successful, {failed} failed)")
                    
                    # Delay before next chunk
                    if i + max_concurrent < len(keywords):
                        logger.info(f"Waiting {delay}s before next batch...")
                        time.sleep(delay)
                        
                    # Save batch results
                    if options.get("saveResults", True):
                        for keyword, result in results.items():
                            self.result_service.save_result({
                                "keyword": keyword,
                                "method": result.get("method"),
                                "data": result,
                                "jobId": jobid,
                                "createdAt": datetime.utcnow(),
                            })
                            
                    final_results = {
                    "results": results,
                    "errors": errors,
                    "stats": {
                        "total": len(keywords),
                        "successful": successful,
                        "failed": failed,
                        "successRate": round((successful / len(keywords)) * 100) if keywords else 0,
                        },
                    }
                    
                    # Mark job as completed
                    if jobid:
                        self.job_service.update_job(jobid, {
                            "status": "completed",
                            "results": final_results,
                            "completedAt": datetime.utcnow(),
                            "progress": 100,
                            "processedItems": processed,
                        })

                    print(
                        f"Batch scraping completed. Results: {successful}/{len(keywords)} successful"
                    )
                    return final_results
        except Exception as e:
            print("Batch scraping failed:", exc_info=True)
            
            if jobid:
                self.job_service.update_job(jobid, {
                    "status": "failed",
                    "error": str(e),
                    "results": {
                        "results": results,
                        "errors": errors,
                        "stats": {"successful": successful, "failed": failed, "total": len(keywords)},
                    },
                    "completedAt": datetime.utcnow(),
                    "processedItems": processed,
                })

            raise e
         
        
        
            
       