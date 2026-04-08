from fastapi import Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from typing import Optional
from url_normalize import url_normalize
from aiohttp import ClientSession

EXCLUDED_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


async def proxy_pass(
    request: Request,
    host: str,
    path: Optional[str] = None,
    forward_query: bool = True,
    additional_headers: Optional[dict] = None,
    override_headers: Optional[dict] = None,
    override_body: Optional[bytes] = None,
    method: Optional[str] = None,
):
    if path is None:
        path = request.url.path
    url = url_normalize(host + path, default_scheme="http")
    if forward_query and request.url.query:
        url = (
            f"{url}?{request.url.query}"
            if "?" not in url
            else f"{url}&{request.url.query}"
        )
    url = url_normalize(url, default_scheme="http")

    final_method = method or request.method

    if override_headers is not None:
        headers = dict(override_headers)
    else:
        headers = dict(request.headers)
        # Identify the client's real IP and forward it
        client_host = request.client.host if request.client else "unknown"
        headers["X-Real-IP"] = client_host
        if "X-Forwarded-For" in headers:
            headers["X-Forwarded-For"] = f"{headers['X-Forwarded-For']}, {client_host}"
        else:
            headers["X-Forwarded-For"] = client_host

        headers["X-Forwarded-Proto"] = request.url.scheme
        headers["X-Forwarded-Host"] = headers.get("host", request.url.netloc)

    # Apply additional headers
    if additional_headers:
        headers.update(additional_headers)

    # Let httpx handle the host header and connection management
    headers.pop("host", None)
    headers.pop("connection", None)

    client: ClientSession = None
    try:
        client = request.app.state.client
        is_global_client = True
    except:
        client = ClientSession()
        is_global_client = False
    try:
        if override_body is not None:
            data = override_body
        else:

            async def request_generator():
                async for chunk in request.stream():
                    yield chunk

            data = (
                request_generator()
                if final_method in ("POST", "PUT", "PATCH", "DELETE")
                else None
            )
        rp_resp = await client.request(
            method=final_method, url=url, headers=headers, data=data
        )
        try:
            resp_headers = {}
            for k, v in rp_resp.headers.items():
                if k.lower() in EXCLUDED_HEADERS:
                    continue
                if k.lower() in ("content-encoding", "content-length"):
                    continue
                resp_headers[k] = v
            resp_headers["X-Accel-Buffering"] = "no"
            resp_headers["Cache-Control"] = "no-cache"

            async def response_generator():
                async for chunk in rp_resp.content.iter_any():
                    yield chunk

            async def cleanup():
                await rp_resp.wait_for_close()
                if not is_global_client:
                    await client.close()

            return StreamingResponse(
                response_generator(),
                status_code=rp_resp.status,
                headers=resp_headers,
                background=BackgroundTask(cleanup),
            )
        except BaseException as e:
            await rp_resp.wait_for_close()
            raise e
    except BaseException:
        if not is_global_client and client:
            await client.close()
        raise
