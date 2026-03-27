"""Plugin route discovery via entry_points.

External modules register API routes via pyproject.toml:

    [project.entry-points."set_core.api_routes"]
    voice = "set_project_voice.api:register_routes"

Each plugin provides a register_routes(router: APIRouter) function.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "set_core.api_routes"


def discover_and_register(parent_router: APIRouter) -> int:
    """Discover and register plugin API routes. Returns count of registered plugins."""
    try:
        from importlib.metadata import entry_points
    except ImportError:
        return 0

    eps = entry_points()
    # Python 3.12+ returns SelectableGroups, older returns dict
    if hasattr(eps, "select"):
        plugin_eps = eps.select(group=ENTRY_POINT_GROUP)
    elif isinstance(eps, dict):
        plugin_eps = eps.get(ENTRY_POINT_GROUP, [])
    else:
        plugin_eps = [ep for ep in eps if ep.group == ENTRY_POINT_GROUP]

    count = 0
    for ep in plugin_eps:
        try:
            register_fn = ep.load()
            plugin_router = APIRouter()
            register_fn(plugin_router)
            parent_router.include_router(plugin_router)
            route_count = len(plugin_router.routes)
            logger.info("Plugin '%s' registered %d routes", ep.name, route_count)
            count += 1
        except Exception as e:
            logger.warning("Failed to load plugin '%s': %s", ep.name, e)

    if count:
        logger.info("Loaded %d API plugins", count)
    return count
