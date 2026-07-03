import dotenv
import os
import subprocess

dotenv.load_dotenv()
from codex_relay import _find_binary

env = os.environ.copy()
subprocess.run(
    [
        str(_find_binary()),
        "--port",
        os.environ["CODEX_RELAY_PORT"],
        "--upstream",
        os.environ["CODEX_RELAY_UPSTREAM"],
        "--api-key",
        os.environ["CODEX_RELAY_API_KEY"]
    ],
)
