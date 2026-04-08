import httpx
import time

n = 10

start_time = time.perf_counter()
for i in range(n):
    client = httpx.AsyncClient()
print(f"create {n} httpx client time: {time.perf_counter() - start_time}")
print(
    f"create {n} httpx client speed: {n / (time.perf_counter() - start_time)} client/s"
)
