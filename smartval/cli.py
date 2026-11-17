import os

import uvicorn


def api() -> None:
    uvicorn.run("smartval.api:app", host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")))
