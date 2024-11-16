import traceback
from fastapi import Request
from fastapi.responses import JSONResponse

from public.const import API


async def log500Error(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception as e:
        error_message = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        API.LOGGER.value.error(
            "HTTP 500\n"
            f"Path: {request.url.path}\n"
            f"Method: {request.method}\n"
            f"Error: {error_message}"
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error"}
        )

    return response
