import dotenv
import os
import subprocess
import signal
import sys

dotenv.load_dotenv()

from codex_relay import _find_binary


env = os.environ.copy()

proc = subprocess.Popen(
    [
        str(_find_binary()),
        "--port",
        os.environ["CODEX_RELAY_PORT"],
        "--upstream",
        os.environ["CODEX_RELAY_UPSTREAM"],
        "--api-key",
        os.environ["CODEX_RELAY_API_KEY"],
    ],
    stdout=sys.stdout,
    stderr=sys.stderr,
    start_new_session=True,
)


def forward_signal(signum, frame):
    print(f"Forwarding signal {signum} to child process")
    try:
        os.killpg(proc.pid, signum)
    except ProcessLookupError:
        pass


for sig in (
    signal.SIGINT,
    signal.SIGTERM,
    signal.SIGHUP,
):
    signal.signal(sig, forward_signal)


try:
    proc.wait()
except KeyboardInterrupt:
    forward_signal(signal.SIGINT, None)
    proc.wait()
