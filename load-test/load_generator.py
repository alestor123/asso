"""
ASSO Load Generator — Creates REAL traffic against demo apps for live demos.

Supports configurable patterns: steady, ramp, spike, wave
Purely uses stdlib + requests — no external dependencies.

Usage:
    python load_generator.py --target http://localhost:6001/work --pattern spike --duration 60 --max-rps 100
    python load_generator.py --target http://localhost:6002/compute --pattern ramp --duration 90 --max-rps 200
"""
import argparse
import time
import math
import sys
import threading
import json
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


class LoadGenerator:
    """Generates configurable HTTP traffic patterns against target endpoints"""

    def __init__(self, target: str, pattern: str, duration: int,
                 max_rps: int, intensity: int = 5, ramp_time: int = 15):
        self.target = target
        self.pattern = pattern
        self.duration = duration
        self.max_rps = max_rps
        self.intensity = intensity
        self.ramp_time = ramp_time

        # Stats
        self.total_sent = 0
        self.total_success = 0
        self.total_errors = 0
        self.total_rate_limited = 0
        self.latencies = deque(maxlen=1000)
        self.start_time = None
        self.running = False
        self._lock = threading.Lock()

    def get_target_rps(self, elapsed: float) -> float:
        """Calculate target RPS based on pattern and elapsed time"""
        progress = elapsed / self.duration  # 0.0 to 1.0

        if self.pattern == "steady":
            return self.max_rps

        elif self.pattern == "ramp":
            # Linear ramp from 10% to 100%
            return self.max_rps * (0.1 + 0.9 * progress)

        elif self.pattern == "spike":
            # Low baseline with sharp spike at 30-60%
            if progress < 0.25:
                return self.max_rps * 0.1  # Baseline
            elif progress < 0.35:
                # Rapid ramp up
                spike_progress = (progress - 0.25) / 0.10
                return self.max_rps * (0.1 + 0.9 * spike_progress)
            elif progress < 0.65:
                return self.max_rps  # Full spike
            elif progress < 0.75:
                # Ramp down
                down_progress = (progress - 0.65) / 0.10
                return self.max_rps * (1.0 - 0.7 * down_progress)
            else:
                return self.max_rps * 0.3  # Recovery baseline

        elif self.pattern == "wave":
            # Sinusoidal wave between 20% and 100%
            wave = (math.sin(progress * math.pi * 4) + 1) / 2  # 0.0 to 1.0
            return self.max_rps * (0.2 + 0.8 * wave)

        elif self.pattern == "stress":
            # Continuous ramp that exceeds capacity
            return self.max_rps * (0.5 + 1.5 * progress)

        return self.max_rps * 0.5

    def send_request(self):
        """Send a single HTTP request to the target"""
        url = f"{self.target}?intensity={self.intensity}&duration_ms=50"
        start = time.time()
        try:
            req = Request(url, method="POST" if "/work" in self.target or "/compute" in self.target else "GET")
            req.add_header("Content-Type", "application/json")
            with urlopen(req, timeout=5) as resp:
                resp.read()
                latency = (time.time() - start) * 1000
                status = resp.status

                with self._lock:
                    self.total_sent += 1
                    self.latencies.append(latency)
                    if status < 400:
                        self.total_success += 1
                    elif status == 429:
                        self.total_rate_limited += 1
                    else:
                        self.total_errors += 1
        except HTTPError as e:
            latency = (time.time() - start) * 1000
            with self._lock:
                self.total_sent += 1
                self.latencies.append(latency)
                if e.code == 429:
                    self.total_rate_limited += 1
                else:
                    self.total_errors += 1
        except Exception:
            with self._lock:
                self.total_sent += 1
                self.total_errors += 1

    def print_stats(self, elapsed: float, target_rps: float):
        """Print real-time statistics"""
        with self._lock:
            avg_lat = sum(self.latencies) / len(self.latencies) if self.latencies else 0
            p99_lat = sorted(self.latencies)[int(len(self.latencies) * 0.99)] if len(self.latencies) > 10 else avg_lat

        actual_rps = self.total_sent / max(1, elapsed)
        bar_len = int(min(target_rps / max(1, self.max_rps) * 30, 30))
        bar = "█" * bar_len + "░" * (30 - bar_len)

        sys.stdout.write(
            f"\r⏱ {elapsed:5.1f}s │ {bar} │ "
            f"Target: {target_rps:5.0f} rps │ "
            f"Actual: {actual_rps:5.1f} rps │ "
            f"✓{self.total_success} ✗{self.total_errors} ⊘{self.total_rate_limited} │ "
            f"Lat: {avg_lat:5.0f}ms (p99: {p99_lat:5.0f}ms)   "
        )
        sys.stdout.flush()

    def run(self):
        """Run the load generation pattern"""
        print(f"\n{'═' * 80}")
        print(f"  ASSO Load Generator")
        print(f"  Target:   {self.target}")
        print(f"  Pattern:  {self.pattern}")
        print(f"  Duration: {self.duration}s")
        print(f"  Max RPS:  {self.max_rps}")
        print(f"  Intensity:{self.intensity}")
        print(f"{'═' * 80}\n")

        self.running = True
        self.start_time = time.time()

        with ThreadPoolExecutor(max_workers=min(200, self.max_rps * 2)) as executor:
            while self.running:
                elapsed = time.time() - self.start_time
                if elapsed >= self.duration:
                    break

                target_rps = self.get_target_rps(elapsed)
                interval = 1.0 / max(1, target_rps)

                # Submit requests for this interval
                batch_start = time.time()
                requests_this_second = 0

                while time.time() - batch_start < 1.0 and self.running:
                    if elapsed + (time.time() - batch_start) >= self.duration:
                        break
                    executor.submit(self.send_request)
                    requests_this_second += 1
                    if requests_this_second >= target_rps:
                        remaining = 1.0 - (time.time() - batch_start)
                        if remaining > 0:
                            time.sleep(remaining)
                        break
                    time.sleep(interval)

                self.print_stats(time.time() - self.start_time, target_rps)

        self.running = False
        self._print_summary()

    def _print_summary(self):
        """Print final summary"""
        elapsed = time.time() - self.start_time
        with self._lock:
            avg_lat = sum(self.latencies) / len(self.latencies) if self.latencies else 0

        print(f"\n\n{'═' * 80}")
        print(f"  Load Test Complete")
        print(f"{'─' * 80}")
        print(f"  Duration:       {elapsed:.1f}s")
        print(f"  Total Requests: {self.total_sent}")
        print(f"  Successful:     {self.total_success}")
        print(f"  Errors:         {self.total_errors}")
        print(f"  Rate Limited:   {self.total_rate_limited}")
        print(f"  Avg Latency:    {avg_lat:.1f}ms")
        print(f"  Throughput:     {self.total_sent / max(1, elapsed):.1f} req/s")
        print(f"{'═' * 80}\n")


def main():
    parser = argparse.ArgumentParser(description="ASSO Load Generator")
    parser.add_argument("--target", default="http://localhost:6001/work",
                        help="Target URL (default: http://localhost:6001/work)")
    parser.add_argument("--pattern", choices=["steady", "ramp", "spike", "wave", "stress"],
                        default="spike", help="Traffic pattern (default: spike)")
    parser.add_argument("--duration", type=int, default=60,
                        help="Test duration in seconds (default: 60)")
    parser.add_argument("--max-rps", type=int, default=100,
                        help="Maximum requests per second (default: 100)")
    parser.add_argument("--intensity", type=int, default=5,
                        help="Work intensity 1-10 (default: 5)")

    args = parser.parse_args()

    generator = LoadGenerator(
        target=args.target,
        pattern=args.pattern,
        duration=args.duration,
        max_rps=args.max_rps,
        intensity=args.intensity,
    )

    try:
        generator.run()
    except KeyboardInterrupt:
        generator.running = False
        print("\n\nLoad generation interrupted.")
        generator._print_summary()


if __name__ == "__main__":
    main()
