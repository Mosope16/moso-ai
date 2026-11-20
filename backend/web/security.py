"""
Moso AI — Web Security and Safe URL Validator
Provides SSRF (Server-Side Request Forgery) protection, private/reserved IP blocking,
DNS resolution checks, redirect revalidation, and response size limits.
"""

import socket
import ipaddress
import urllib.parse
from typing import Tuple, Optional, Set
import httpx


# Forbidden special hostnames
FORBIDDEN_HOSTS: Set[str] = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "metadata.google.internal",
    "instance-data",
    "local",
}

# Forbidden hostname suffixes
FORBIDDEN_SUFFIXES = (
    ".local",
    ".localhost",
    ".internal",
    ".lan",
    ".corp",
    ".home",
    ".arpa",
)

MAX_RESPONSE_SIZE = 2 * 1024 * 1024  # 2 MB limit for web page fetches
DEFAULT_FETCH_TIMEOUT = 12.0          # 12s total timeout
CONNECT_TIMEOUT = 8.0                 # 8s connection timeout


def validate_safe_url(url: str) -> Tuple[bool, str, Optional[str]]:
    """
    Validates that a URL is safe to retrieve from an external web server.
    Enforces:
    1. HTTP or HTTPS scheme only
    2. Valid hostname present
    3. Rejection of localhost, loopback, private RFC1918, link-local, multicast,
       cloud metadata (169.254.169.254), carrier-grade NAT (100.64.0.0/10),
       and internal domain names.
    4. DNS resolution validation: verifies that the resolved IPs are public.

    Returns:
        (is_safe: bool, reason: str, normalized_url: Optional[str])
    """
    if not url or not isinstance(url, str):
        return False, "URL cannot be empty", None

    cleaned_url = url.strip()
    try:
        parsed = urllib.parse.urlparse(cleaned_url)
    except Exception as e:
        return False, f"Malformed URL: {e}", None

    # 1. Scheme check
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        return False, f"Unsupported URL scheme '{scheme}'. Only HTTP and HTTPS are permitted.", None

    # 2. Hostname check
    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname in URL.", None

    hostname_lower = hostname.lower()

    if hostname_lower in FORBIDDEN_HOSTS:
        return False, f"Access to internal host '{hostname}' is blocked for security.", None

    for suffix in FORBIDDEN_SUFFIXES:
        if hostname_lower.endswith(suffix):
            return False, f"Access to internal network domain '{hostname}' is blocked.", None

    # 3. Direct IP address check if hostname is an IP literal
    try:
        ip = ipaddress.ip_address(hostname_lower)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            return False, f"Access to private/reserved IP address {ip} is blocked for security.", None
        # Check carrier-grade NAT range (100.64.0.0/10)
        if isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("100.64.0.0/10"):
            return False, f"Access to carrier-grade NAT address {ip} is blocked.", None
    except ValueError:
        # Not a raw IP literal, proceed to DNS resolution
        pass

    # 4. DNS Resolution & IP verification (prevents DNS rebinding and internal IP masking)
    port = parsed.port or (443 if scheme == "https" else 80)
    try:
        addr_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        if not addr_info:
            return False, f"Could not resolve host '{hostname}'.", None

        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
                if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
                    return False, f"Host '{hostname}' resolved to blocked private/reserved IP {ip_str}.", None
                if isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("100.64.0.0/10"):
                    return False, f"Host '{hostname}' resolved to blocked CGNAT IP {ip_str}.", None
            except ValueError:
                return False, f"Host resolved to invalid IP address: {ip_str}", None

    except socket.gaierror as e:
        return False, f"DNS resolution failed for '{hostname}': {e}", None
    except Exception as e:
        return False, f"Host validation error for '{hostname}': {e}", None

    # Return normalized URL
    return True, "URL is safe", cleaned_url


async def safe_fetch_http(url: str, max_size: int = MAX_RESPONSE_SIZE, timeout_sec: float = DEFAULT_FETCH_TIMEOUT) -> Tuple[int, bytes, str, dict]:
    """
    Safely fetches an external URL over HTTP/HTTPS with:
    - SSRF pre-check on initial URL and on every redirect destination
    - Maximum content size enforcement (streams bytes and aborts if exceeded)
    - Custom modern User-Agent
    - Strict timeout

    Returns:
        (status_code: int, content_bytes: bytes, content_type: str, headers: dict)
    """
    is_safe, reason, normalized_url = validate_safe_url(url)
    if not is_safe:
        raise ValueError(f"Security check failed: {reason}")

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0 (compatible; MosoAI/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,application/pdf;q=0.7,*/*;q=0.5",
        "Accept-Language": "en-US,en;q=0.9",
    }

    current_url = normalized_url
    max_redirects = 5
    redirect_count = 0

    timeout = httpx.Timeout(connect=CONNECT_TIMEOUT, read=timeout_sec, write=timeout_sec, pool=timeout_sec)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, headers=headers) as client:
        while redirect_count <= max_redirects:
            async with client.stream("GET", current_url) as resp:
                # Handle Redirects safely by re-validating the destination URL
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location")
                    if not location:
                        raise ValueError(f"Redirect status {resp.status_code} received with no Location header")

                    # Handle relative redirect locations
                    next_url = urllib.parse.urljoin(current_url, location)
                    is_safe_next, next_reason, norm_next_url = validate_safe_url(next_url)
                    if not is_safe_next:
                        raise ValueError(f"Redirect destination blocked: {next_reason}")

                    current_url = norm_next_url
                    redirect_count += 1
                    continue

                # Not a redirect - download content with size cap
                content_type = resp.headers.get("content-type", "").lower()
                collected = bytearray()

                async for chunk in resp.aiter_bytes():
                    collected.extend(chunk)
                    if len(collected) > max_size:
                        raise ValueError(f"Page response exceeds maximum allowable size of {max_size // (1024 * 1024)} MB")

                return resp.status_code, bytes(collected), content_type, dict(resp.headers)

        raise ValueError(f"Exceeded maximum redirect limit of {max_redirects}")
