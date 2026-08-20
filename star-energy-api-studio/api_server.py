from __future__ import annotations

import os

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "api_layer.server:api",
        host="127.0.0.1",
        port=int(os.getenv("ENERJI_API_PORT", "8091")),
        reload=False,
        access_log=False,
    )
