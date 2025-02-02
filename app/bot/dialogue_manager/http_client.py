import logging
import aiohttp
import asyncio
from typing import Dict, Any, Optional
from aiohttp import ClientTimeout

logger = logging.getLogger("http_client")


class APICallExcetion(Exception):
    pass


async def call_api(
    url: str,
    method: str,
    headers: Optional[Dict[str, str]] = None,
    parameters: Optional[Dict[str, Any]] = None,
    is_json: bool = False,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    Asynchronously call external API with improved error handling and timeout management

    Args:
        url: The API endpoint URL
        method: HTTP method (GET, POST, PUT, DELETE)
        headers: Optional request headers
        parameters: Optional request parameters or body
        is_json: Whether to send parameters as JSON body
        timeout: Request timeout in seconds

    Returns:
        Dict containing the API response

    Raises:
        aiohttp.ClientError: For HTTP-specific errors
        asyncio.TimeoutError: When request times out
        ValueError: For invalid method types
        Exception: For other unexpected errors
    """
    headers = headers or {}
    parameters = parameters or {}
    timeout_config = ClientTimeout(total=timeout)

    try:
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            method = method.upper()
            logger.debug(
                f"Initiating async API Call: url={url} \
                    method={method} payload={parameters}"
            )

            if method == "GET":
                async with session.get(
                    url, headers=headers, params=parameters
                ) as response:
                    result = await response.json()
            elif method in ["POST", "PUT"]:
                kwargs = {
                    "headers": headers,
                    "json" if is_json else "params": parameters,
                }
                async with getattr(session, method.lower())(url, **kwargs) as response:
                    result = await response.json()
            elif method == "DELETE":
                async with session.delete(
                    url, headers=headers, params=parameters
                ) as response:
                    result = await response.json()
            else:
                raise ValueError(f"Unsupported request method: {method}")

            response.raise_for_status()
            logger.debug(f"API response => {result}")
            return result

    except aiohttp.ClientError as e:
        logger.error(f"HTTP error occurred: {str(e)}")
        raise APICallExcetion(f"HTTP error occurred: {str(e)}")
    except asyncio.TimeoutError:
        logger.error(f"Request timed out after {timeout} seconds")
        raise APICallExcetion(f"Request timed out after {timeout} seconds")
    except Exception as e:
        logger.error(f"Unexpected error during API call: {str(e)}")
        raise
