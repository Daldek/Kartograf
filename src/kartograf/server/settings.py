"""
The settings of ``kartograf server`` (ADR-063 decision 8, DEV-18.1).

The limits and the trusted proxies are keys of ``[kartograf]`` of ``nogat.toml`` and
variables ``KARTOGRAF_<KEY>`` (``kartograf.config``); the files of the server are
under the shared directories: the metadata cache ``<cache_dir>/kartograf/metadata.db``
(its index cache), the logs ``<state_dir>/kartograf/logs`` (DEV-12.6) and the daily
totals ``<data_dir>/kartograf/stats.jsonl`` (DEV-15.11). No key of any source is read.
"""

from dataclasses import dataclass
from pathlib import Path

from kartograf import config
from kartograf.cache.defaults import default_cache_path
from kartograf.server.stats import STATS_FILE

__all__ = ["ServerSettings"]


@dataclass(frozen=True)
class ServerSettings:
    """What ``kartograf server`` limits and where it keeps its files.

    Attributes
    ----------
    index_max_age : int
        Seconds an index answer of the metadata cache is reused by a plan (the
        ``refresh_ttl_seconds`` of the server's cache, ADR-056).
    plan_limit, plan_window : int
        Plans (and scripts that plan) of one client per that many seconds.
    plan_max_units : int
        Units of one plan.
    request_limit, request_window : int
        Requests of one client per that many seconds (DEV-15.9).
    trusted_proxies : tuple of str
        The addresses and networks whose ``X-Forwarded-For`` counts (AGI-6.9).
    cache_path : Path
        The metadata cache, the server's index cache.
    log_dir : Path
        The directory of the logs ``nogat-log/1``.
    stats_path : Path
        The file of the daily totals.
    """

    index_max_age: int
    plan_limit: int
    plan_window: int
    plan_max_units: int
    request_limit: int
    request_window: int
    trusted_proxies: tuple[str, ...]
    cache_path: Path
    log_dir: Path
    stats_path: Path

    @classmethod
    def from_config(cls) -> "ServerSettings":
        """Return the settings in force (``kartograf.config``).

        An invalid value is the default, as everywhere (``check_config`` raises it).
        """
        return cls(
            index_max_age=config.limit("index_max_age"),
            plan_limit=config.limit("plan_limit"),
            plan_window=config.limit("plan_window"),
            plan_max_units=config.limit("plan_max_units"),
            request_limit=config.limit("request_limit"),
            request_window=config.limit("request_window"),
            trusted_proxies=config.trusted_proxies(),
            cache_path=default_cache_path(),
            log_dir=config.state_dir() / config.TOOL / "logs",
            stats_path=config.data_dir() / config.TOOL / STATS_FILE,
        )

    def summary(self) -> dict[str, object]:
        """Return the limits for the lifecycle record ``start``.

        No path, no key and no address (DEV-12.5): the trusted proxies stay out.
        """
        return {
            "index_max_age": self.index_max_age,
            "plan_limit": self.plan_limit,
            "plan_window": self.plan_window,
            "plan_max_units": self.plan_max_units,
            "request_limit": self.request_limit,
            "request_window": self.request_window,
        }
