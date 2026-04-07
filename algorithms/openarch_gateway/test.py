import asyncio
import aiohttp
import time

BASE_URL = "http://127.0.0.1:8000"

TOTAL_REQUESTS = 20000
CONCURRENCY = 200


HIT_PATH = "/pmgr/rules"

MISS_PATH = "/this_path_should_not_match_123456"


async def worker(session, path, counter):
    url = BASE_URL + path
    async with session.get(url) as resp:
        await resp.read()
        counter.append(1)


async def run_test(path):
    counter = []

    connector = aiohttp.TCPConnector(limit=0)
    timeout = aiohttp.ClientTimeout(total=10)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []

        start = time.perf_counter()

        for _ in range(TOTAL_REQUESTS):
            task = asyncio.create_task(worker(session, path, counter))
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
    import time
    asyncio.run(main())
