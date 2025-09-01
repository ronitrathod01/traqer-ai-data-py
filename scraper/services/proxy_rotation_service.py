import os
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

class ProxyRotationService:
    """
    Python port of your Node ProxyRotationService.
    Reads env: SCRAPING_BROWSER_AUTHS = "user1:pass1,user2:pass2,..."
    Produces CDP endpoints: wss://<auth>@brd.superproxy.io:9222
    """
    def __init__(self):
        self.scraping_browser_auths = self._parse_scraping_browser_auths()
        self.residential_proxies = self._parse_residential_proxies()  # currently aliased to SB auths like your Node code

        # rotation indexes
        self.scraping_browser_index = 0
        self.residential_proxy_index = 0

        # health + usage
        self.health_status = {
            "scrapingBrowser": {},
            "residential": {}
        }
        self.usage_stats = {
            "scrapingBrowser": defaultdict(int),
            "residential": defaultdict(int),
        }

        self._initialize_health_status()

        logger.info("Initialized proxy rotation")
        logger.info(f"- Scraping Browser APIs: {len(self.scraping_browser_auths)}")
        logger.info(f"- Residential Proxies: {len(self.residential_proxies)}")

    # -------- Public: getters ----------

    def get_next_scraping_browser(self):
        if not self.scraping_browser_auths:
            raise RuntimeError("No Scraping Browser auths configured")

        auth = self.scraping_browser_auths[self.scraping_browser_index]
        self.scraping_browser_index = (self.scraping_browser_index + 1) % len(self.scraping_browser_auths)
        self._update_usage_stats("scrapingBrowser", auth["id"])

        logger.info(f"Using Scraping Browser: {auth['id']} ({auth.get('location', 'default')})")
        return {
            "id": auth["id"],
            "auth": auth["auth"],
            "endpoint": f"wss://{auth['auth']}@brd.superproxy.io:9222",
            "location": auth.get("location", "default"),
        }

    def get_least_used_scraping_browser(self):
        if not self.scraping_browser_auths:
            raise RuntimeError("No Scraping Browser auths configured")

        # find least used among all
        least = min(self.scraping_browser_auths,
                    key=lambda a: self.usage_stats["scrapingBrowser"][a["id"]])
        self._update_usage_stats("scrapingBrowser", least["id"])
        return {
            "id": least["id"],
            "auth": least["auth"],
            "endpoint": f"wss://{least['auth']}@brd.superproxy.io:9222",
            "location": least.get("location", "default"),
        }

    def get_healthy_scraping_browser(self):
        if not self.scraping_browser_auths:
            raise RuntimeError("No Scraping Browser auths configured")

        healthy = [a for a in self.scraping_browser_auths
                   if self.health_status["scrapingBrowser"].get(a["id"], "unknown") != "unhealthy"]

        if not healthy:
            logger.warning("No healthy Scraping Browser auths; falling back to next")
            return self.get_next_scraping_browser()

        least = min(healthy, key=lambda a: self.usage_stats["scrapingBrowser"][a["id"]])
        self._update_usage_stats("scrapingBrowser", least["id"])
        return {
            "id": least["id"],
            "auth": least["auth"],
            "endpoint": f"wss://{least['auth']}@brd.superproxy.io:9222",
            "location": least.get("location", "default"),
        }

    # Residential getters currently mirror scraping browser (like your Node code)
    def get_next_residential_proxy(self):
        return self.get_next_scraping_browser()

    def get_least_used_residential_proxy(self):
        return self.get_least_used_scraping_browser()

    def get_healthy_residential_proxy(self):
        return self.get_healthy_scraping_browser()

    # -------- Public: health / stats ----------

    def update_proxy_health(self, proxy_type: str, proxy_id: str, is_healthy: bool, error: str | None = None):
        status = "healthy" if is_healthy else "unhealthy"
        self.health_status[proxy_type][proxy_id] = status
        if not is_healthy and error:
            logger.warning(f"Proxy {proxy_id} marked unhealthy: {error}")
        elif is_healthy:
            logger.info(f"Proxy {proxy_id} marked healthy")

    def get_rotation_stats(self):
        return {
            "scrapingBrowser": {
                "total": len(self.scraping_browser_auths),
                "healthy": sum(1 for s in self.health_status["scrapingBrowser"].values() if s == "healthy"),
                "usage": dict(self.usage_stats["scrapingBrowser"]),
            },
            "residential": {
                "total": len(self.residential_proxies),
                "healthy": sum(1 for s in self.health_status["residential"].values() if s == "healthy"),
                "usage": dict(self.usage_stats["residential"]),
            }
        }

    def reset_usage_stats(self):
        self.usage_stats = {
            "scrapingBrowser": defaultdict(int),
            "residential": defaultdict(int),
        }
        logger.info("Usage statistics reset")

    # -------- Private helpers ----------

    def _parse_scraping_browser_auths(self):
        auths_string = os.environ.get("SCRAPING_BROWSER_AUTHS", "")
        if not auths_string:
            logger.warning("No SCRAPING_BROWSER_AUTHS configured")
            return []
        auths = []
        for idx, item in enumerate(auths_string.split(","), start=1):
            item = item.strip()
            if not item:
                continue
            auths.append({
                "id": f"sb_{idx}",
                "auth": item,
                "location": "default",
            })
        return auths

    def _parse_residential_proxies(self):
        # mirroring your Node code: just reuse SB auths for now
        return list(self._parse_scraping_browser_auths())

    def _initialize_health_status(self):
        for a in self.scraping_browser_auths:
            self.health_status["scrapingBrowser"][a["id"]] = "unknown"
            self.usage_stats["scrapingBrowser"][a["id"]] = 0
        for r in self.residential_proxies:
            self.health_status["residential"][r["id"]] = "unknown"
            self.usage_stats["residential"][r["id"]] = 0

    def _update_usage_stats(self, proxy_type: str, proxy_id: str):
        self.usage_stats[proxy_type][proxy_id] += 1
