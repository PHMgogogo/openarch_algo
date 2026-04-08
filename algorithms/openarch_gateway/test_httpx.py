import asyncio
import httpx
import time

BASE_URL = "http://127.0.0.1:8000"

TOTAL_REQUESTS = 20000
CONCURRENCY = 200


HIT_PATH = "/instances"

MISS_PATH = "/this_path_should_not_match_123456"


async def worker(client: httpx.AsyncClient, path, counter):
    url = BASE_URL + path
    response = await client.get(url)
    await response.aread()
    # await response.aclose() # something wrong
    counter.append(1)


async def run_test(path):
    counter = []

    limits = httpx.Limits(
        max_connections=None,
        max_keepalive_connections=None,
    )

    async with httpx.AsyncClient(limits=limits, timeout=None) as client:
        tasks = []

        start = time.perf_counter()

        for _ in range(TOTAL_REQUESTS):
            task = asyncio.create_task(worker(client, path, counter))
            tasks.append(task)

            if len(tasks) >= CONCURRENCY:
                await asyncio.gather(*tasks)
                tasks = []

        if tasks:
            await asyncio.gather(*tasks)

        end = time.perf_counter()

    duration = end - start
    qps = len(counter) / duration

    return duration, qps


async def main():
    print("=== 测试：命中代理 ===")
    duration, qps = await run_test(HIT_PATH)
    print(f"耗时: {duration:.2f}s, QPS: {qps:.2f}")

    print("\n=== 测试：未命中代理 ===")
    duration, qps = await run_test(MISS_PATH)
    print(f"耗时: {duration:.2f}s, QPS: {qps:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
