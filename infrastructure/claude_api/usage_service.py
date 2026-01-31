"""
Claude.ai Usage API Service

Fetches subscription usage limits from Claude.ai internal API.
Works only with OAuth credentials (Claude Account mode).
"""

import logging
import aiohttp
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

CLAUDE_API_BASE = "https://api.claude.ai/api"


@dataclass
class UsageLimits:
    """Claude.ai subscription usage limits"""
    # Session limits
    session_used_percent: Optional[float] = None
    session_resets_in: Optional[str] = None

    # Weekly limits
    weekly_used_percent: Optional[float] = None
    weekly_resets_at: Optional[str] = None

    # Sonnet-specific limits
    sonnet_used_percent: Optional[float] = None
    sonnet_resets_at: Optional[str] = None

    # Subscription info
    subscription_type: Optional[str] = None
    rate_limit_tier: Optional[str] = None

    # Raw data for debugging
    raw_data: Optional[dict] = None
    error: Optional[str] = None


class ClaudeUsageService:
    """Service to fetch usage limits from Claude.ai API"""

    def __init__(self, account_service=None):
        self.account_service = account_service

    async def get_usage_limits(self) -> UsageLimits:
        """
        Fetch current usage limits from Claude.ai API.

        Returns:
            UsageLimits with current usage data or error
        """
        if not self.account_service:
            return UsageLimits(error="Account service not available")

        # Get access token
        access_token = self.account_service.get_access_token_from_credentials()
        if not access_token:
            return UsageLimits(error="No access token. Login with Claude Account first.")

        try:
            return await self._fetch_usage(access_token)
        except Exception as e:
            logger.error(f"Error fetching usage limits: {e}")
            return UsageLimits(error=str(e))

    async def _fetch_usage(self, access_token: str) -> UsageLimits:
        """Fetch usage data from Claude.ai API"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "Claude-Telegram-Bot/1.0",
        }

        async with aiohttp.ClientSession() as session:
            # Try different endpoints
            endpoints = [
                "/bootstrap",  # Main bootstrap endpoint with user info
                "/account",
                "/settings",
            ]

            for endpoint in endpoints:
                try:
                    url = f"{CLAUDE_API_BASE}{endpoint}"
                    logger.debug(f"Trying endpoint: {url}")

                    async with session.get(url, headers=headers, timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            logger.debug(f"Got data from {endpoint}: {list(data.keys()) if isinstance(data, dict) else type(data)}")

                            # Try to extract usage info
                            limits = self._parse_usage_data(data)
                            if limits.session_used_percent is not None or limits.weekly_used_percent is not None:
                                return limits

                            # Store raw data even if we couldn't parse usage
                            limits.raw_data = data

                        elif resp.status == 401:
                            return UsageLimits(error="Token expired. Re-login required.")
                        else:
                            logger.debug(f"Endpoint {endpoint} returned {resp.status}")

                except aiohttp.ClientError as e:
                    logger.debug(f"Error fetching {endpoint}: {e}")
                    continue

            # If no endpoint worked, try the organizations endpoint
            return await self._try_organizations_endpoint(session, headers)

    async def _try_organizations_endpoint(self, session: aiohttp.ClientSession, headers: dict) -> UsageLimits:
        """Try to fetch from organizations endpoint"""
        try:
            # First get organization ID
            async with session.get(f"{CLAUDE_API_BASE}/organizations", headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    return UsageLimits(error=f"Cannot access Claude.ai API (status {resp.status})")

                orgs = await resp.json()
                if not orgs:
                    return UsageLimits(error="No organizations found")

                org_id = orgs[0].get("uuid") or orgs[0].get("id")
                if not org_id:
                    return UsageLimits(error="Cannot find organization ID", raw_data=orgs)

                # Try to get usage for this org
                usage_url = f"{CLAUDE_API_BASE}/organizations/{org_id}/usage"
                async with session.get(usage_url, headers=headers, timeout=10) as usage_resp:
                    if usage_resp.status == 200:
                        data = await usage_resp.json()
                        return self._parse_usage_data(data)
                    else:
                        # Return org info at least
                        return UsageLimits(
                            subscription_type=orgs[0].get("subscription_type"),
                            rate_limit_tier=orgs[0].get("rate_limit_tier"),
                            raw_data=orgs[0]
                        )

        except Exception as e:
            logger.error(f"Error in organizations endpoint: {e}")
            return UsageLimits(error=str(e))

    def _parse_usage_data(self, data: dict) -> UsageLimits:
        """Parse usage data from API response"""
        limits = UsageLimits(raw_data=data)

        if not isinstance(data, dict):
            return limits

        # Try to find usage info in various locations
        usage = data.get("usage") or data.get("rate_limits") or data.get("limits") or {}
        account = data.get("account") or data.get("user") or {}

        # Session/hourly limits
        if "session" in usage:
            session_data = usage["session"]
            limits.session_used_percent = session_data.get("used_percent") or session_data.get("percentage")
            limits.session_resets_in = session_data.get("resets_in") or session_data.get("reset_time")

        # Weekly limits
        if "weekly" in usage:
            weekly_data = usage["weekly"]
            limits.weekly_used_percent = weekly_data.get("used_percent") or weekly_data.get("percentage")
            limits.weekly_resets_at = weekly_data.get("resets_at") or weekly_data.get("reset_time")

        # Model-specific limits (Sonnet)
        if "sonnet" in usage:
            sonnet_data = usage["sonnet"]
            limits.sonnet_used_percent = sonnet_data.get("used_percent") or sonnet_data.get("percentage")
            limits.sonnet_resets_at = sonnet_data.get("resets_at")

        # Subscription info
        limits.subscription_type = (
            account.get("subscription_type") or
            data.get("subscription_type") or
            data.get("plan")
        )
        limits.rate_limit_tier = (
            account.get("rate_limit_tier") or
            data.get("rate_limit_tier") or
            data.get("tier")
        )

        return limits

    def format_usage_for_telegram(self, limits: UsageLimits) -> str:
        """Format usage limits for Telegram display"""
        if limits.error:
            return f"❌ <b>Ошибка:</b> {limits.error}"

        lines = ["📊 <b>Лимиты Claude.ai</b>\n"]

        # Session limits
        if limits.session_used_percent is not None:
            bar = self._make_progress_bar(limits.session_used_percent)
            lines.append(f"<b>Сессия:</b> {bar} {limits.session_used_percent:.0f}%")
            if limits.session_resets_in:
                lines.append(f"   Сброс через: {limits.session_resets_in}")
            lines.append("")

        # Weekly limits
        if limits.weekly_used_percent is not None:
            bar = self._make_progress_bar(limits.weekly_used_percent)
            lines.append(f"<b>Неделя:</b> {bar} {limits.weekly_used_percent:.0f}%")
            if limits.weekly_resets_at:
                lines.append(f"   Сброс: {limits.weekly_resets_at}")
            lines.append("")

        # Sonnet limits
        if limits.sonnet_used_percent is not None:
            bar = self._make_progress_bar(limits.sonnet_used_percent)
            lines.append(f"<b>Sonnet:</b> {bar} {limits.sonnet_used_percent:.0f}%")
            if limits.sonnet_resets_at:
                lines.append(f"   Сброс: {limits.sonnet_resets_at}")
            lines.append("")

        # Subscription info
        if limits.subscription_type:
            lines.append(f"📋 Подписка: <code>{limits.subscription_type}</code>")
        if limits.rate_limit_tier:
            lines.append(f"⚡ Tier: <code>{limits.rate_limit_tier}</code>")

        # If we have raw data but couldn't parse usage
        if not any([limits.session_used_percent, limits.weekly_used_percent, limits.sonnet_used_percent]):
            if limits.raw_data:
                lines.append("\n<i>API вернул данные, но формат отличается от ожидаемого.</i>")
                # Show some raw data for debugging
                if isinstance(limits.raw_data, dict):
                    keys = list(limits.raw_data.keys())[:5]
                    lines.append(f"<i>Ключи: {', '.join(keys)}</i>")
            else:
                lines.append("\n<i>Не удалось получить данные о лимитах.</i>")

        return "\n".join(lines)

    def _make_progress_bar(self, percent: float, width: int = 10) -> str:
        """Create a text progress bar"""
        filled = int(percent / 100 * width)
        empty = width - filled

        if percent >= 80:
            fill_char = "🟥"
        elif percent >= 50:
            fill_char = "🟨"
        else:
            fill_char = "🟩"

        return fill_char * filled + "⬜" * empty
