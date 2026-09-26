"""Application entry point: sets up Libadwaita application, styles, and services."""

import sys
from typing import Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.rotation_service import RotationService
from wallpaper_engine.core.search_service import SearchAggregator
from wallpaper_engine.core.source_manager import SourceManager
from wallpaper_engine.core.theme_manager import ThemeManager
from wallpaper_engine.providers.archimg import ArchimgProvider
from wallpaper_engine.providers.bing import BingProvider
from wallpaper_engine.providers.github_walls import GitHubWallsProvider
from wallpaper_engine.providers.local_provider import LocalProvider
from wallpaper_engine.providers.nasa import NasaApodProvider
from wallpaper_engine.providers.openverse import OpenverseProvider
from wallpaper_engine.providers.pexels import PexelsProvider
from wallpaper_engine.providers.pixabay import PixabayProvider
from wallpaper_engine.providers.unsplash import UnsplashProvider
from wallpaper_engine.providers.wallhaven import WallhavenProvider
from wallpaper_engine.providers.wikimedia import WikimediaProvider
from wallpaper_engine.setters.detector import get_best_setter
from wallpaper_engine.ui.main_window import MainWindow


class WallpaperEngineApp(Adw.Application):
    """Personal Wallpaper Engine Libadwaita Application."""

    def __init__(self) -> None:
        super().__init__(
            application_id="org.wallforge.app",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.cache_manager = CacheManager()
        self.source_manager = SourceManager()
        self.theme_manager = ThemeManager(config_dir=self.source_manager.config_dir)

        # Register providers
        self.source_manager.register_provider(ArchimgProvider(cache_manager=self.cache_manager))
        self.source_manager.register_provider(WallhavenProvider(cache_manager=self.cache_manager))
        self.source_manager.register_provider(BingProvider(cache_manager=self.cache_manager))
        self.source_manager.register_provider(NasaApodProvider(cache_manager=self.cache_manager))
        self.source_manager.register_provider(OpenverseProvider(cache_manager=self.cache_manager))
        self.source_manager.register_provider(WikimediaProvider(cache_manager=self.cache_manager))
        self.source_manager.register_provider(GitHubWallsProvider(cache_manager=self.cache_manager))
        self.source_manager.register_provider(UnsplashProvider(cache_manager=self.cache_manager))
        self.source_manager.register_provider(PexelsProvider(cache_manager=self.cache_manager))
        self.source_manager.register_provider(PixabayProvider(cache_manager=self.cache_manager))
        self.source_manager.register_provider(LocalProvider(cache_manager=self.cache_manager))

        self.search_aggregator = SearchAggregator(self.source_manager, cache_manager=self.cache_manager)
        self.wallpaper_setter = get_best_setter()
        self.rotation_service = RotationService(
            source_manager=self.source_manager,
            search_aggregator=self.search_aggregator,
            cache_manager=self.cache_manager,
            wallpaper_setter=self.wallpaper_setter,
        )

        self.window: Optional[MainWindow] = None

    def do_startup(self) -> None:
        from gi.repository import GLib
        GLib.set_application_name("WallForge")
        GLib.set_prgname("wallforge")
        Adw.Application.do_startup(self)
        self.theme_manager.apply_theme()

    def do_activate(self) -> None:
        if not self.window:
            self.window = MainWindow(
                app=self,
                source_manager=self.source_manager,
                search_aggregator=self.search_aggregator,
                cache_manager=self.cache_manager,
                rotation_service=self.rotation_service,
                wallpaper_setter=self.wallpaper_setter,
                theme_manager=self.theme_manager,
            )
        self.window.present()


def main():
    app = WallpaperEngineApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
