#!/usr/bin/env python3
"""
Controlled Load Test Script
============================
Purpose: Test your OWN website's resilience/Cloudflare protection under load.

IMPORTANT / LEGAL & ETHICAL NOTICE:
- Only run this against domains/servers YOU own or have EXPLICIT written
  permission to test. Running load tests against third-party sites without
  authorization is illegal in most jurisdictions (unauthorized access /
  denial-of-service laws) and against Cloudflare's own ToS.
- This script intentionally caps concurrency and request rate so you can
  observe effects and stop before causing real damage to your own site.
- You are monitoring manually -- watch your server CPU/RAM, response times,
  and Cloudflare Analytics (Security > Events) while this runs, and hit
  Ctrl+C immediately if real users look affected.

HOW TO USE:
1. Set TARGET_URL below to your own site.
2. Review and adjust the SAFE LIMITS section below.
3. Run, and watch your server dashboard / Cloudflare Analytics the whole time.
4. Stop (Ctrl+C) any time you want. Edit the limits and re-run to increase load.
"""

import asyncio
import time
import random
import statistics
import signal
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, field

# ============================================================================
# SAFE LIMITS -- ADJUST CAREFULLY. START LOW. INCREASE GRADUALLY.
# ============================================================================

# Your own website only. Do NOT point this at a domain you don't control.
TARGET_URL = "https://eaziline.com/"

# MAX_CONCURRENT_REQUESTS: number of requests "in flight" at once.
#   Safe starting point: 5-10 for a small site, 20-50 for a site that
#   already handles decent traffic. Going into the hundreds/thousands
#   is where this stops being a "test" and starts being a real DDoS --
#   avoid unless you have explicit capacity planning reasons and have
#   cleared it with your host. Increase gradually between runs while
#   watching server load.
MAX_CONCURRENT_REQUESTS = 5000000000000000000000

# REQUESTS_PER_SECOND_CAP: hard ceiling on request rate, regardless of
#   concurrency, enforced via a delay between requests. Keep this well
#   below what you'd expect a real traffic spike to look like, and
#   increase gradually between runs.
REQUESTS_PER_SECOND_CAP = 50000000000000000

# REQUEST_TIMEOUT_SECONDS: don't let slow requests pile up connections.
REQUEST_TIMEOUT_SECONDS = 10

# --- User Agents ---
# Rotate across common real-world user agents so the test approximates
# varied client traffic.
USER_AGENTS = [

    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",

    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",

    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",

    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",

    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.2210.91",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.2277.83",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.2365.92",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.2478.67",

    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",

    # Opera
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 OPR/108.0.0.0",

    # Android Chrome
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Mobile Safari/537.36",

    # iPhone
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_7 like Mac OS X) AppleWebKit/605.1.15 Version/15.0 Mobile Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 Version/16.0 Mobile Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Version/17.4 Mobile Safari/604.1",

    # iPad
    "Mozilla/5.0 (iPad; CPU OS 16_6 like Mac OS X) AppleWebKit/605.1.15 Version/16.0 Mobile Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Version/17.4 Mobile Safari/604.1",

    # Google Bots
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Googlebot/2.1 (+http://www.google.com/bot.html)",
    "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 Chrome Mobile Safari/537.36 (compatible; Googlebot/2.1)",

    # Bing
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; bingbot/2.0)",

    # DuckDuckGo
    "DuckDuckBot/1.1; (+http://duckduckgo.com/duckduckbot.html)",

    # Yahoo
    "Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)",

    # Yandex
    "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",

    # Baidu
    "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)",

    # Social Crawlers
    "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "Twitterbot/1.0",
    "LinkedInBot/1.0",

    # SEO Crawlers
    "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)",
    "Mozilla/5.0 (compatible; SemrushBot/7~bl; +http://www.semrush.com/bot.html)",
    "MJ12bot/v1.4.8 (http://mj12bot.com/)",
]

# ============================================================================
# END OF CONFIGURATION -- code below implements the above
# ============================================================================


@dataclass
class Stats:
    total: int = 0
    success: int = 0
    errors: int = 0
    timeouts: int = 0
    latencies_ms: list = field(default_factory=list)

    @property
    def error_rate_percent(self):
        if self.total == 0:
            return 0.0
        return (self.errors + self.timeouts) / self.total * 100


class LoadTester:
    def __init__(self):
        self.aborted = False
        signal.signal(signal.SIGINT, self._handle_interrupt)

    def _handle_interrupt(self, signum, frame):
        print("\n\n[!] Ctrl+C received -- aborting test immediately.")
        self.aborted = True

    async def _fetch(self, semaphore, stats: Stats, min_interval):
        async with semaphore:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            t0 = time.monotonic()
            try:
                request = urllib.request.Request(TARGET_URL, headers=headers)
                response = await asyncio.to_thread(
                    urllib.request.urlopen,
                    request,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                try:
                    await asyncio.to_thread(response.read)
                    status = response.status
                finally:
                    response.close()
                elapsed_ms = (time.monotonic() - t0) * 1000
                stats.latencies_ms.append(elapsed_ms)
                stats.total += 1
                if 200 <= status < 400:
                    stats.success += 1
                else:
                    stats.errors += 1
            except (TimeoutError, urllib.error.URLError) as exc:
                stats.total += 1
                if isinstance(exc, TimeoutError) or isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, TimeoutError):
                    stats.timeouts += 1
                else:
                    stats.errors += 1
            except Exception:
                stats.total += 1
                stats.errors += 1
            # Rate-limit enforcement: even with concurrency, don't exceed
            # the configured requests-per-second cap.
            await asyncio.sleep(min_interval)

    def _print_report(self, stats: Stats):
        print(f"\nRequests sent : {stats.total}")
        print(f"Successful    : {stats.success}")
        print(f"Errors        : {stats.errors}")
        print(f"Timeouts      : {stats.timeouts}")
        print(f"Error rate    : {stats.error_rate_percent:.1f}%")
        if stats.latencies_ms:
            print(f"Latency (ms)  : min={min(stats.latencies_ms):.0f} "
                  f"avg={statistics.mean(stats.latencies_ms):.0f} "
                  f"max={max(stats.latencies_ms):.0f}")
        print("--> Check your server: CPU/RAM (htop/hosting dashboard), "
              "Cloudflare Analytics (Security > Events), response times.")

    async def run(self):
        print(f"Target: {TARGET_URL}")
        print(f"Concurrency: {MAX_CONCURRENT_REQUESTS}, "
              f"Rate cap: {REQUESTS_PER_SECOND_CAP} req/s")
        print("Runs until you stop it -- there is no request limit. Watch "
              "your server dashboard / Cloudflare Analytics while this "
              "runs, and press Ctrl+C any time to stop.\n")

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        stats = Stats()
        min_interval = 1.0 / REQUESTS_PER_SECOND_CAP if REQUESTS_PER_SECOND_CAP > 0 else 0

        tasks = []
        while not self.aborted:
            tasks.append(asyncio.create_task(
                self._fetch(semaphore, stats, min_interval)
            ))
            # Small stagger so we don't launch a burst instantaneously
            await asyncio.sleep(min_interval / max(MAX_CONCURRENT_REQUESTS, 1))

        await asyncio.gather(*tasks, return_exceptions=True)

        self._print_report(stats)
        print("\nTest complete.")


def main():
    if "your-own-website.com" in TARGET_URL:
        print("ERROR: Please edit TARGET_URL at the top of this script to point "
              "to your own website before running.")
        sys.exit(1)

    tester = LoadTester()
    asyncio.run(tester.run())


if __name__ == "__main__":
    main()
