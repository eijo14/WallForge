# Contributing to WallForge

Thank you for your interest in contributing to WallForge! WallForge is an open-source, cross-platform wallpaper engine and desktop background manager built with Python, GTK4, and Libadwaita.

## Development Setup

### System Prerequisites

- **Python 3.10+**
- **GTK4** (`libgtk-4-dev` or `gtk4-devel`)
- **Libadwaita 1.0+** (`libadwaita-1-dev` or `libadwaita-devel`)
- **GObject Introspection** and **PyGObject**

### Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/eijofrancis/wallforge.git
cd wallforge
pip install -e .[dev]
```

To run the application locally:

```bash
python3 -m wallpaper_engine.ui.app
```

## Architecture Overview

- `wallpaper_engine/core/`: Core engines including `CacheManager`, `SourceManager`, `SearchAggregator`, and `RotationService`.
- `wallpaper_engine/providers/`: Modular wallpaper providers implementing `WallpaperProvider`.
- `wallpaper_engine/setters/`: Desktop environment wallpaper setters implementing `WallpaperSetter`.
- `wallpaper_engine/ui/`: GTK4 / Libadwaita user interface components and views.

## Adding a Wallpaper Provider

1. Inherit from `WallpaperProvider` in `wallpaper_engine/core/provider_base.py`.
2. Implement required properties: `provider_id`, `provider_name`, `homepage_url`, and `capabilities`.
3. Implement `get_featured(page: int)` and optional `search(filters: SearchFilter)`.
4. Return normalized `Wallpaper` dataclass instances with valid metadata, artist attribution, and license details.
5. If the provider API requires download tracking (e.g. Unsplash), preserve `download_location` and implement tracking hooks.
6. Register the provider in `wallpaper_engine/core/source_manager.py`.

## Adding a Wallpaper Setter

1. Inherit from `WallpaperSetter` in `wallpaper_engine/setters/base.py`.
2. Implement `is_available()`, `apply_wallpaper(image_path, mode, monitor)`, and `capabilities()`.
3. Never use unsanitized string interpolation in shell or interpreter commands:
   - Always pass arguments as parameter lists or positional `argv`.
   - Always specify explicit timeouts (`timeout=5`) on `subprocess.run` calls.
   - Guard against control characters (`\n`, `\r`) in file paths.

## Testing Guidelines

Ensure all tests pass before opening a Pull Request:

```bash
python3 -m unittest discover tests
```

When introducing new functionality or fixing security issues, add corresponding regression test cases in `tests/`.

## Code Style & Standards

- Follow PEP 8 guidelines.
- Use explicit type annotations where practical.
- Keep UI responsiveness intact: never perform synchronous network requests or heavy image processing on the GTK main thread.
- Avoid committing API secrets, tokens, or personal configuration files.
