"""URL and browser-search validation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import ip_address
from urllib.parse import quote_plus, urlparse, urlunparse

from visionai.core.errors import UrlValidationError
from visionai.core.events import contains_unsafe_characters


@dataclass(frozen=True, slots=True)
class UrlPolicy:
    """Allowlist-based URL policy for browser capabilities."""

    allowed_hosts: frozenset[str] = field(default_factory=frozenset)
    allowed_schemes: frozenset[str] = field(default_factory=lambda: frozenset({"https"}))
    allow_private_hosts: bool = False
    allowed_ports: frozenset[int] = field(default_factory=lambda: frozenset({443}))

    def normalize_url(self, raw_url: str) -> str:
        if contains_unsafe_characters(raw_url, allow_line_breaks=False):
            raise UrlValidationError("URL contains control characters")
        parsed = urlparse(raw_url.strip())
        if parsed.scheme.lower() not in self.allowed_schemes:
            raise UrlValidationError("URL scheme is not allowed")
        host = self._normalize_host(parsed.hostname)
        if parsed.username or parsed.password:
            raise UrlValidationError("URL credentials are not allowed")
        if parsed.port is not None and parsed.port not in self.allowed_ports:
            raise UrlValidationError("URL port is not allowed")
        normalized_path = quote_plus(parsed.path, safe="/%")
        normalized_query = quote_plus(parsed.query, safe="=&%")
        netloc = host if parsed.port is None else f"{host}:{parsed.port}"
        return urlunparse(
            (
                parsed.scheme.lower(),
                netloc,
                normalized_path or "/",
                "",
                normalized_query,
                "",
            )
        )

    def validate_redirect(self, original_url: str, redirect_url: str) -> str:
        """Normalize a redirect target only when both URLs satisfy this policy."""

        self.normalize_url(original_url)
        normalized_redirect = self.normalize_url(redirect_url)
        original_host = self._normalize_host(urlparse(original_url).hostname)
        redirect_host = self._normalize_host(urlparse(redirect_url).hostname)
        if original_host != redirect_host:
            raise UrlValidationError("redirect host changed")
        return normalized_redirect

    def build_search_url(self, query: str, *, host: str = "www.google.com") -> str:
        if contains_unsafe_characters(query, allow_line_breaks=False):
            raise UrlValidationError("search query contains control characters")
        if len(query) > 500:
            raise UrlValidationError("search query is too long")
        host = self._normalize_host(host)
        encoded = quote_plus(query.strip())
        if not encoded:
            raise UrlValidationError("search query is empty")
        return f"https://{host}/search?q={encoded}"

    def _normalize_host(self, host: str | None) -> str:
        if not host:
            raise UrlValidationError("URL host is required")
        normalized = host.rstrip(".").lower()
        try:
            normalized = normalized.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise UrlValidationError("URL host is invalid") from exc
        if _is_private_host(normalized) and not self.allow_private_hosts:
            raise UrlValidationError("URL host is private or local")
        if normalized not in self.allowed_hosts:
            raise UrlValidationError("URL host is not allowlisted")
        return normalized


def _is_private_host(host: str) -> bool:
    normalized = host.rstrip(".").lower()
    if normalized in {"localhost", "localhost.localdomain"}:
        return True
    try:
        parsed_ip = ip_address(normalized)
    except ValueError:
        return False
    return (
        parsed_ip.is_private
        or parsed_ip.is_loopback
        or parsed_ip.is_link_local
        or parsed_ip.is_reserved
        or parsed_ip.is_multicast
    )
