from setuptools import setup, find_packages

setup(
    name="wallforge",
    version="1.0.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "wallforge = wallpaper_engine.ui.app:main",
            "personal-wallpaper-engine = wallpaper_engine.ui.app:main",
        ],
    },
)
