import threading
import math
import json
import time
from queue import Empty, Queue
import requests

from client import IntkeyClient

TPS = 30
TRANSACTIONS = 10000
WORKERS = 16
APIS = 32


def worker(api, start, n, tps, out_queue: Queue, stats_queue: Queue):
    cli = IntkeyClient(f"http://rest-api-{api}:8008")
    print(f"Sending to: http://rest-api-{api}:8008")
    status_urls = []
    for k in range(start, start + n):
        while True:
            resp = cli.set(k, 1)
            try:
                status_urls.append(json.loads(resp)["link"])
            except KeyError:
                time.sleep(0.25)
            else:
                time.sleep(1 / tps)
                break

        stats_queue.put(1)

    stats_queue.put("end")
    out_queue.put(status_urls)


def stats(queue: Queue):
    end = 0
    calls = 0
    t0 = time.time()
    while True:
        try:
            msg = queue.get(timeout=0.025)
        except Empty:
            pass
        else:
            if msg == "end":
                end += 1
            else:
                calls += msg

                if calls % 50 == 0:
                    now = time.time()
                    tps = 50 // (now - t0)
                    t0 = now
                    print(f"Total requests: {calls}\t| Requests per second: {tps}")

        if end == WORKERS:
            break


if __name__ == "__main__":
    tps_per_worker = TPS / WORKERS
    per_worker = math.floor(TRANSACTIONS / WORKERS)

    queue = Queue()
    stats_queue = Queue()
    threads = [
        threading.Thread(
            target=stats,
            args=(stats_queue,),
        )
    ]
    for i in range(WORKERS):
        t = threading.Thread(
            target=worker,
            args=(
                i % APIS,
                i * per_worker,
                per_worker,
                tps_per_worker,
                queue,
                stats_queue,
            ),
        )
        threads.append(t)

    t0 = time.time()

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    t = int(time.time() - t0)
    m = t // 60
    s = t % 60
    print(f"Did {per_worker*WORKERS} api requests using {WORKERS} workers in {m}m {s}s")

    print("\nwaiting 40s before checking status of requests..\n")
    time.sleep(40)

    statuses = {"COMMITTED": 0, "PENDING": 0, "INVALID": 0}
    while True:
        try:
            res = queue.get(timeout=0.1)
            for link in res:
                r = requests.get(link, timeout=0.2)
                status = json.loads(r.text)["data"][0]["status"]
                statuses[status] += 1
        except Empty:
            break

    print(json.dumps(statuses, indent=2))
