from typing import Any
from fastapi.responses import JSONResponse


class SafariFriendlyJSONResponse(JSONResponse):
    def __init__(self, content: Any, status_code: int = 200, *args, **kwargs):
        headers = kwargs.pop("headers", {})
        headers["Content-Type"] = "application/json; charset=utf-8"

        super().__init__(content, status_code=status_code, *args, headers=headers, **kwargs)
