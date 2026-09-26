"""Source manager: registers, monitors, configures, and tests providers."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wallpaper_engine.core.models import SourceStatus
from wallpaper_engine.core.provider_base import WallpaperProvider


class SourceManager:
    """Central registry and lifecycle manager for all wallpaper providers.
    
    Persists enable/disable state and provider-specific configurations
    in ~/.config/wallpaper-engine/config.json with strict permissions (0600).
    """

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        from wallpaper_engine.core.paths import PathManager

        path_mgr = PathManager(override_config_dir=config_dir)
        self.config_dir = path_mgr.config_dir
        self.config_file = path_mgr.config_file
        self._providers: Dict[str, WallpaperProvider] = {}
        self._enabled_sources: Dict[str, bool] = {}
        self._provider_configs: Dict[str, Dict[str, Any]] = {}
        self._custom_source_configs: Dict[str, Dict[str, Any]] = {}

        path_mgr.ensure_directories()
        self.load_config()

    def register_provider(self, provider: WallpaperProvider) -> None:
        """Register a wallpaper provider instance."""
        pid = provider.provider_id
        self._providers[pid] = provider

        # Default enabled unless explicitly disabled in config
        if pid not in self._enabled_sources:
            self._enabled_sources[pid] = True

        # Apply saved provider configuration
        if pid in self._provider_configs:
            provider.configure(self._provider_configs[pid])

        # Update initial status
        if not self._enabled_sources[pid]:
            provider.status = SourceStatus.DISABLED

    def get_provider(self, provider_id: str) -> Optional[WallpaperProvider]:
        """Retrieve registered provider by ID."""
        return self._providers.get(provider_id)

    def get_all_providers(self) -> List[WallpaperProvider]:
        """Return all registered providers in registration order."""
        return list(self._providers.values())

    def get_enabled_providers(self) -> List[WallpaperProvider]:
        """Return list of enabled providers."""
        return [
            p for pid, p in self._providers.items()
            if self._enabled_sources.get(pid, True) and p.status != SourceStatus.DISABLED
        ]

    def is_enabled(self, provider_id: str) -> bool:
        """Check if provider is enabled."""
        return self._enabled_sources.get(provider_id, True)

    def set_enabled(self, provider_id: str, enabled: bool) -> None:
        """Enable or disable a provider."""
        self._enabled_sources[provider_id] = enabled
        provider = self._providers.get(provider_id)
        if provider:
            if not enabled:
                provider.status = SourceStatus.DISABLED
            else:
                provider.status = SourceStatus.ONLINE
        self.save_config()

    def get_provider_config(self, provider_id: str) -> Dict[str, Any]:
        """Get configuration dictionary for a provider."""
        return self._provider_configs.get(provider_id, {})

    def save_provider_config(self, provider_id: str, config: Dict[str, Any]) -> None:
        """Update and persist configuration for a provider."""
        self._provider_configs[provider_id] = config
        provider = self._providers.get(provider_id)
        if provider:
            provider.configure(config)
        self.save_config()

    def add_custom_source(self, config: Dict[str, Any]) -> WallpaperProvider:
        """Create, register, and persist a new custom wallpaper provider."""
        from wallpaper_engine.providers.custom import CustomWallpaperProvider
        pid = config.get("id") or f"custom_{abs(hash(config.get('url', '') + config.get('name', '')))}"
        if not pid.startswith("custom_"):
            pid = f"custom_{pid}"
        config["id"] = pid
        self._custom_source_configs[pid] = config
        provider = CustomWallpaperProvider(config)
        self.register_provider(provider)
        self.save_config()
        return provider

    def remove_custom_source(self, provider_id: str) -> bool:
        """Remove a custom wallpaper provider."""
        if provider_id in self._custom_source_configs:
            del self._custom_source_configs[provider_id]
            if provider_id in self._providers:
                del self._providers[provider_id]
            if provider_id in self._enabled_sources:
                del self._enabled_sources[provider_id]
            self.save_config()
            return True
        return False

    def get_custom_sources(self) -> List[Dict[str, Any]]:
        """Return list of saved custom source configurations."""
        return list(self._custom_source_configs.values())

    def test_provider(self, provider_id: str) -> Tuple[bool, str]:
        """Run connectivity test on a specific provider."""
        provider = self._providers.get(provider_id)
        if not provider:
            return False, f"Provider '{provider_id}' not found."
        return provider.test_connection()

    def load_config(self) -> None:
        """Load configuration from disk."""
        if not self.config_file.is_file():
            return
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._enabled_sources = data.get("enabled_sources", {})
            self._provider_configs = data.get("provider_configs", {})
            self._custom_source_configs = data.get("custom_sources", {})

            # Instantiate loaded custom sources
            from wallpaper_engine.providers.custom import CustomWallpaperProvider
            for pid, cfg in self._custom_source_configs.items():
                try:
                    p = CustomWallpaperProvider(cfg)
                    self.register_provider(p)
                except Exception:
                    pass
        except Exception:
            pass

    def save_config(self) -> None:
        """Persist configuration with 0600 file permissions."""
        data = {
            "enabled_sources": self._enabled_sources,
            "provider_configs": self._provider_configs,
            "custom_sources": getattr(self, "_custom_source_configs", {}),
        }
        part = self.config_dir / "config.json.tmp"
        try:
            with open(part, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            # Restrict permissions before moving
            os.chmod(part, 0o600)
            part.replace(self.config_file)
        except Exception:
            if part.exists():
                part.unlink(missing_ok=True)
