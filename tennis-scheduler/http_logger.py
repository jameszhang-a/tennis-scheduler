import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from requests import Response

logger = logging.getLogger(__name__)


class HTTPLogger:
    """Utility class for logging HTTP requests and responses in a structured format similar to Datadog"""

    @staticmethod
    def _sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
        """Remove sensitive information from headers"""
        sanitized = dict(headers)
        sensitive_keys = ["authorization", "x-api-key", "cookie", "set-cookie"]

        for key in list(sanitized.keys()):
            if key.lower() in sensitive_keys:
                if key.lower() == "authorization" and sanitized[key].startswith(
                    "Bearer "
                ):
                    # Show just the type and first few chars
                    token = sanitized[key][7:]  # Remove 'Bearer '
                    sanitized[key] = f"Bearer {token[:8]}..."
                else:
                    sanitized[key] = "[REDACTED]"

        return sanitized

    @staticmethod
    def _sanitize_body(body: Any, content_type: str = "") -> Any:
        """Sanitize request/response body, removing sensitive data"""
        if not body:
            return body

        # For JSON bodies, remove sensitive fields
        if isinstance(body, dict):
            sanitized = dict(body)
            sensitive_fields = ["refresh_token", "access_token", "password", "secret"]

            for field in sensitive_fields:
                if field in sanitized:
                    value = sanitized[field]
                    if isinstance(value, str) and len(value) > 8:
                        sanitized[field] = f"{value[:8]}..."
                    else:
                        sanitized[field] = "[REDACTED]"

            return sanitized

        # For string bodies that might be JSON
        if isinstance(body, str) and "json" in content_type.lower():
            try:
                parsed = json.loads(body)
                return HTTPLogger._sanitize_body(parsed, content_type)
            except json.JSONDecodeError:
                pass

        return body

    @staticmethod
    def log_request_response(
        method: str,
        url: str,
        request_headers: Optional[Dict[str, str]] = None,
        request_body: Any = None,
        response: Optional[Response] = None,
        duration_ms: Optional[float] = None,
        correlation_id: Optional[str] = None,
        operation_name: str = "http_request",
        error: Optional[Exception] = None,
    ) -> None:
        """
        Log HTTP request and response in a structured format

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            request_headers: Request headers dict
            request_body: Request body (dict, string, etc.)
            response: Response object
            duration_ms: Request duration in milliseconds
            correlation_id: Unique ID to correlate request/response
            operation_name: Name of the operation for categorization
            error: Exception if request failed
        """
        if not correlation_id:
            correlation_id = str(uuid.uuid4())[:8]

        timestamp = datetime.utcnow().isoformat() + "Z"

        # Base log entry
        log_entry = {
            "timestamp": timestamp,
            "correlation_id": correlation_id,
            "operation": operation_name,
            "http": {
                "method": method.upper(),
                "url": url,
                "request": {},
                "response": {},
            },
            "duration_ms": duration_ms,
        }

        # Add request details
        if request_headers:
            log_entry["http"]["request"]["headers"] = HTTPLogger._sanitize_headers(
                request_headers
            )

        if request_body is not None:
            content_type = ""
            if request_headers:
                content_type = request_headers.get("Content-Type", "")
            log_entry["http"]["request"]["body"] = HTTPLogger._sanitize_body(
                request_body, content_type
            )

        # Add response details
        if response is not None:
            log_entry["http"]["response"]["status_code"] = response.status_code
            log_entry["http"]["response"]["headers"] = HTTPLogger._sanitize_headers(
                dict(response.headers)
            )

            # Try to parse response body
            try:
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                ):
                    response_body = response.json()
                    log_entry["http"]["response"]["body"] = HTTPLogger._sanitize_body(
                        response_body, response.headers.get("content-type", "")
                    )
                else:
                    # For non-JSON responses, just log the first 500 chars
                    body_text = response.text[:500]
                    if len(response.text) > 500:
                        body_text += "... [truncated]"
                    log_entry["http"]["response"]["body"] = body_text
            except Exception as e:
                log_entry["http"]["response"][
                    "body"
                ] = f"[Failed to parse response body: {e}]"

        # Add error details
        if error:
            log_entry["error"] = {
                "type": error.__class__.__name__,
                "message": str(error),
            }

            # Add response details from the error if available
            if hasattr(error, "response") and error.response is not None:
                log_entry["http"]["response"][
                    "status_code"
                ] = error.response.status_code
                log_entry["http"]["response"]["headers"] = HTTPLogger._sanitize_headers(
                    dict(error.response.headers)
                )
                try:
                    log_entry["http"]["response"]["body"] = error.response.text[:500]
                except:
                    log_entry["http"]["response"][
                        "body"
                    ] = "[Failed to read error response body]"

        # Determine log level
        if error:
            log_level = logging.ERROR
            log_message = f"HTTP {method.upper()} {url} failed"
        elif response and response.status_code >= 400:
            log_level = logging.WARNING
            log_message = f"HTTP {method.upper()} {url} returned {response.status_code}"
        else:
            log_level = logging.INFO
            log_message = f"HTTP {method.upper()} {url}"

        if duration_ms:
            log_message += f" ({duration_ms:.1f}ms)"

        # Log the structured entry
        logger.log(log_level, log_message, extra={"structured_log": log_entry})


def logged_request(
    method: str,
    url: str,
    operation_name: str = "http_request",
    correlation_id: Optional[str] = None,
    **kwargs,
) -> Response:
    """
    Wrapper around requests that automatically logs request/response details

    Args:
        method: HTTP method
        url: Request URL
        operation_name: Name for the operation (e.g., 'token_refresh', 'court_booking')
        correlation_id: Optional correlation ID
        **kwargs: Additional arguments passed to requests

    Returns:
        Response object

    Raises:
        All the same exceptions as requests
    """
    if not correlation_id:
        correlation_id = str(uuid.uuid4())[:8]

    start_time = time.time()
    response = None
    error = None

    try:
        # Make the request
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    except Exception as e:
        error = e
        raise

    finally:
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Extract request details
        request_headers = kwargs.get("headers", {})
        request_body = kwargs.get("json") or kwargs.get("data")

        # Log the request/response
        HTTPLogger.log_request_response(
            method=method,
            url=url,
            request_headers=request_headers,
            request_body=request_body,
            response=response,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
            operation_name=operation_name,
            error=error,
        )
