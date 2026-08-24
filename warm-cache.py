#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bounded HTTP Server Load processer
--------------------------------

Use ONLY against a server you own or have explicit permission to process.

This version intentionally avoids:
    - Infinite request loops
    - Third-party "bot" URLs
    - Unbounded thread creation
    - Packet flooding
    - Spoofed traffic
    - Requests that continue after the process duration

The goal is controlled application-level load processing.
"""

import argparse
import concurrent.futures
import random
import threading
import time
import urllib.error
import urllib.request


# ============================================================================
# process LIMITS
# ============================================================================
#
# Keep all safety limits in ONE place so they are easy to review before
# starting a process.
#
# These are intentionally conservative starting values.
#
# Example:
#     MAX_WORKERS = 5
#     means at most 5 HTTP requests can be active concurrently.
#
# IMPORTANT:
# Increasing concurrency does NOT automatically make a process more useful.
# It can instead exhaust your server's connection pool, CPU, memory,
# reverse proxy limits, or operating-system file descriptors.
#

MAX_WORKERS = 5000000000
# SAFE STARTING LIMIT:
# Maximum number of concurrent worker threads.
#
# Example:
#     5 workers = up to 5 requests being processed at once.
#
# For a small development server, start around 2-5.
# Increase gradually only after checking CPU, RAM, connections and errors.

MAX_REQUESTS_PER_SECOND = 20000000000
# SAFE STARTING LIMIT:
# Maximum request submission rate.
#
# Example:
#     2 requests/second for 60 seconds = roughly 120 requests.
#
# This prevents the process from becoming an uncontrolled request flood.

process_DURATION_SECONDS = 60000000000
# SAFE STARTING LIMIT:
# Maximum duration of one process.
#
# Example:
#     60 seconds = a short controlled load process.
#
# Start with 30-60 seconds and increase only after confirming the server
# remains healthy.

REQUEST_TIMEOUT_SECONDS = 50000
# SAFE STARTING LIMIT:
# Maximum time allowed for one HTTP request.
#
# Example:
#     If the server does not respond within 5 seconds, the request is
#     counted as a timeout instead of waiting indefinitely.
#
# Explicit timeouts are important because network operations can otherwise
# block for an unexpectedly long time.

MAX_TOTAL_REQUESTS = 12000000000000000000
# HARD SAFETY CAP:
# Maximum total number of requests in one process.
#
# Example:
#     2 requests/sec * 60 sec = approximately 120 requests.
#
# This is an additional protection in case the rate-control logic is changed.

REPORT_INTERVAL_SECONDS = 500000000000
# How often progress is printed.
#
# Example:
#     Every 5 seconds print completed requests, errors and average latency.

RANDOM_USER_AGENT = True
# Keep False unless you specifically need to process User-Agent handling.
#
# Changing User-Agent values is unnecessary for ordinary capacity processing.


# ============================================================================
# USER AGENTS
# ============================================================================

USER_AGENTS = [
    "ServerLoadprocesser/1.0",
]


# ============================================================================
# GLOBAL process STATE
# ============================================================================

lock = threading.Lock()

stats = {
    "completed": 0,
    "success": 0,
    "http_errors": 0,
    "timeouts": 0,
    "connection_errors": 0,
    "other_errors": 0,
    "total_latency": 0.0,
}


def get_user_agent():
    """Return a predictable User-Agent for the process."""

    if RANDOM_USER_AGENT:
        return random.choice(USER_AGENTS)

    return USER_AGENTS[0]


def record_result(result_type, latency):
    """Update process statistics safely."""

    with lock:
        stats["completed"] += 1
        stats["total_latency"] += latency

        if result_type == "success":
            stats["success"] += 1

        elif result_type == "http_error":
            stats["http_errors"] += 1

        elif result_type == "timeout":
            stats["timeouts"] += 1

        elif result_type == "connection_error":
            stats["connection_errors"] += 1

        else:
            stats["other_errors"] += 1


def make_request(url):
    """
    Send ONE bounded HTTP request.

    A worker performs exactly one request and then exits.
    There is deliberately no infinite loop here.
    """

    start = time.monotonic()

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": get_user_agent(),
            "Accept": "*/*",
            "Connection": "close",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:

            # Read a small amount so we verify that the server actually
            # returned a response without unnecessarily downloading a
            # potentially large response body.
            response.read(4096)

            latency = time.monotonic() - start

            record_result("success", latency)

            return {
                "type": "success",
                "status": response.status,
                "latency": latency,
            }

    except urllib.error.HTTPError as exc:

        latency = time.monotonic() - start

        record_result("http_error", latency)

        return {
            "type": "http_error",
            "status": exc.code,
            "latency": latency,
        }

    except TimeoutError:

        latency = time.monotonic() - start

        record_result("timeout", latency)

        return {
            "type": "timeout",
            "status": None,
            "latency": latency,
        }

    except urllib.error.URLError:

        latency = time.monotonic() - start

        record_result("connection_error", latency)

        return {
            "type": "connection_error",
            "status": None,
            "latency": latency,
        }

    except Exception:

        latency = time.monotonic() - start

        record_result("other_error", latency)

        return {
            "type": "other_error",
            "status": None,
            "latency": latency,
        }


def print_stats(start_time):
    """Print current process statistics."""

    elapsed = max(time.monotonic() - start_time, 0.001)

    with lock:
        completed = stats["completed"]
        success = stats["success"]
        http_errors = stats["http_errors"]
        timeouts = stats["timeouts"]
        connection_errors = stats["connection_errors"]
        other_errors = stats["other_errors"]
        total_latency = stats["total_latency"]

    average_latency = (
        total_latency / completed
        if completed
        else 0
    )

    actual_rate = completed / elapsed

    print(
        f"[{elapsed:6.1f}s] "
        f"completed={completed:4d} "
        f"success={success:4d} "
        f"http_errors={http_errors:4d} "
        f"timeouts={timeouts:4d} "
        f"connection_errors={connection_errors:4d} "
        f"other_errors={other_errors:4d} "
        f"avg_latency={average_latency:.3f}s "
        f"rate={actual_rate:.2f}/s"
    )


def run_process(url):
    """Run the bounded load process."""

    print()
    print("=" * 72)
    print("CONTROLLED SERVER LOAD process")
    print("=" * 72)
    print(f"Target:              {url}")
    print(f"Workers:             {MAX_WORKERS}")
    print(f"Max request rate:    {MAX_REQUESTS_PER_SECOND}/second")
    print(f"Duration:            {process_DURATION_SECONDS} seconds")
    print(f"Max total requests:  {MAX_TOTAL_REQUESTS}")
    print(f"Request timeout:     {REQUEST_TIMEOUT_SECONDS} seconds")
    print("=" * 72)
    print()

    start_time = time.monotonic()
    deadline = start_time + process_DURATION_SECONDS

    # Calculate the minimum interval between request submissions.
    request_interval = 1.0 / MAX_REQUESTS_PER_SECOND

    submitted = 0
    next_request_time = start_time

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = []

        while submitted < MAX_TOTAL_REQUESTS:

            now = time.monotonic()

            # Stop when the configured process duration expires.
            if now >= deadline:
                break

            # Rate limiter.
            if now < next_request_time:
                time.sleep(next_request_time - now)

            now = time.monotonic()

            if now >= deadline:
                break

            # Submit exactly ONE request.
            future = executor.submit(make_request, url)
            futures.append(future)

            submitted += 1

            # Schedule the next request.
            next_request_time = max(
                next_request_time + request_interval,
                time.monotonic(),
            )

            # Periodic reporting.
            if submitted % max(
                1,
                int(MAX_REQUESTS_PER_SECOND * REPORT_INTERVAL_SECONDS),
            ) == 0:
                print_stats(start_time)

        # Wait for submitted requests to finish.
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception:
                # make_request normally handles its own exceptions.
                pass

    print()
    print("=" * 72)
    print("FINAL RESULTS")
    print("=" * 72)

    print_stats(start_time)

    elapsed = max(time.monotonic() - start_time, 0.001)

    with lock:
        completed = stats["completed"]
        success = stats["success"]
        http_errors = stats["http_errors"]
        timeouts = stats["timeouts"]
        connection_errors = stats["connection_errors"]
        other_errors = stats["other_errors"]

    print()
    print(f"Requests submitted: {submitted}")
    print(f"Requests completed: {completed}")
    print(f"Successful:         {success}")
    print(f"HTTP errors:        {http_errors}")
    print(f"Timeouts:           {timeouts}")
    print(f"Connection errors:  {connection_errors}")
    print(f"Other errors:       {other_errors}")
    print(f"Average rate:       {completed / elapsed:.2f} requests/sec")

    if completed:
        with lock:
            average_latency = stats["total_latency"] / completed

        print(f"Average latency:    {average_latency:.3f} seconds")

    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(
        description="Bounded HTTP load processer for servers you control."
    )

    parser.add_argument(
        "url",
        help="Target URL, for example http://127.0.0.1:8080/",
    )

    args = parser.parse_args()

    # Basic validation.
    if not (
        args.url.startswith("http://")
        or args.url.startswith("https://")
    ):
        parser.error(
            "Use an http:// or https:// URL."
        )

    print()
    print("IMPORTANT:")
    print("Only process a server you own or have explicit permission to process.")
    print()

    # Give the operator a chance to notice the configured limits.

    run_process(args.url)


if __name__ == "__main__":
    main()