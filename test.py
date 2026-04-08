import client

# print(client.process.templates.get())
# print(
#     client.process.templates.create(
#         algorithm_id_or_prefix="openarch_gateway",
#         id="gateway",
#         entry="uvicorn main:app --host 0.0.0.0 --port 8001",
#         restart_always=True,
#         volume=True,
#         is_temporary=False,
#         restart_interval_seconds=10,
#         rules=[],
#     )
# )
print(client.process.templates.info("gateway"))
print(client.process.instances.create("gateway", "gateway"))
