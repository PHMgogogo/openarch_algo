import config
import os

os.environ["PROCESS_MANAGER_URL"] = "http://127.0.0.1:8000/"
import client

path = os.path.join(
    config.Config.algorithm_root_path,
    "ez_agent",
    ".env",
)
print(open(path).read())
yn = input(f"I have confirmed that the content at {path} is valid (y/n): ")
if yn not in ["y", "", "Y"]:
    print("Exit.")
    exit()
try:
    print(client.process.instances.delete("gateway"))
except:
    pass
try:
    print(client.process.instances.delete("agent"))
except:
    pass
print(client.process.instances.create("gateway", "gateway"))
print(client.process.instances.create("agent", "agent"))
print(f"Visit {client.RULE_MANAGER_URL}/index.html to get started")
print("Done.")
