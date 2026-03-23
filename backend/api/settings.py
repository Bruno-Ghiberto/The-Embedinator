"""System settings endpoints -- read and partial update."""

from fastapi import APIRouter, HTTPException, Request

from backend.agent.schemas import SettingsResponse, SettingsUpdateRequest
from backend.config import settings as app_config

router = APIRouter()


def _parse_bool(value: str) -> bool:
    """Parse boolean from string stored in settings table."""
    return value.lower() in ("true", "1", "yes")


# Map of setting keys to their config defaults and type coercion functions
_SETTINGS_KEYS: dict[str, tuple[str, type]] = {
    "default_llm_model": ("default_llm_model", str),
    "default_embed_model": ("default_embed_model", str),
    "confidence_threshold": ("confidence_threshold", int),
    "groundedness_check_enabled": ("groundedness_check_enabled", _parse_bool),
    "citation_alignment_threshold": ("citation_alignment_threshold", float),
    "parent_chunk_size": ("parent_chunk_size", int),
    "child_chunk_size": ("child_chunk_size", int),
}


def _build_settings_response(db_settings: dict[str, str]) -> SettingsResponse:
    """Merge DB settings with config defaults, coerce types."""
    values = {}
    for key, (config_attr, type_fn) in _SETTINGS_KEYS.items():
        if key in db_settings:
            try:
                values[key] = type_fn(db_settings[key])
            except (ValueError, TypeError):
                values[key] = getattr(app_config, config_attr)
        else:
            values[key] = getattr(app_config, config_attr)
    return SettingsResponse(**values)


@router.get("/api/settings")
async def get_settings(request: Request):
    """Get current system-wide settings (DB overrides + config defaults)."""
    db = request.app.state.db
    db_settings = await db.list_settings()
    return _build_settings_response(db_settings)


@router.put("/api/settings")
async def update_settings(body: SettingsUpdateRequest, request: Request):
    """Partially update settings. Only non-None fields are changed."""
    db = request.app.state.db
    trace_id = getattr(request.state, "trace_id", "")

    # Validate confidence_threshold range explicitly for clear error code
    if body.confidence_threshold is not None:
        if body.confidence_threshold < 0 or body.confidence_threshold > 100:
            raise HTTPException(status_code=400, detail={
                "error": {
                    "code": "SETTINGS_VALIDATION_ERROR",
                    "message": "confidence_threshold must be between 0 and 100",
                    "details": {"field": "confidence_threshold", "value": body.confidence_threshold},
                },
                "trace_id": trace_id,
            })

    # Persist each non-None field
    update_dict = body.model_dump(exclude_none=True)
    for key, value in update_dict.items():
        await db.set_setting(key, str(value))

    # Return full settings after update
    db_settings = await db.list_settings()
    return _build_settings_response(db_settings)
