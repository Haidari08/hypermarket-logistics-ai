from typing import Any
from fastapi.responses import JSONResponse

class SafariFriendlyJSONResponse(JSONResponse):
    def __init__(self, content: Any, *args, **kwargs):
        headers = kwargs.pop("headers", {})
        headers["Content-Type"] = "application/json; charset=utf-8"
        super().__init__(content, *args, headers=headers, **kwargs)
