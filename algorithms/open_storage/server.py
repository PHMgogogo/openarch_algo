from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import FastAPI, File, Form, UploadFile, responses
import typing

app = FastAPI()

STORAGE_ROOT = Path(__file__).resolve().parent / "storage"


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    filename: typing.Optional[str] = Form(None),
):
    folder = STORAGE_ROOT / str(uuid4())
    folder.mkdir(parents=True, exist_ok=False)
    if filename is None:
        filename = file.filename
    file_path = folder / Path(filename).name

    async with aiofiles.open(file_path, "wb") as out_file:
        while chunk := await file.read(1024 * 1024):
            await out_file.write(chunk)

    await file.close()
    return responses.PlainTextResponse(str(file_path.resolve()))


# uvicorn server:app --host 0.0.0.0 --port 8006
