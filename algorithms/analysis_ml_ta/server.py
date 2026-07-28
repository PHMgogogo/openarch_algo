import sys, os
os.environ["BASE_PATH"]=os.path.abspath(__file__)
sys.path.append(
    os.path.abspath(os.path.dirname(__file__) + "/../../algorithms")
)
from framework.server import create_app

# uvicorn server:create_app --factory --port 0
