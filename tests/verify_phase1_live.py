"""Live connectivity and normalization verification for Phase 1 providers."""

from pathlib import Path
import shutil
import tempfile
import time

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.source_manager import SourceManager
from wallpaper_engine.providers.archimg import ArchimgProvider
from wallpaper_engine.providers.bing import BingProvider
from wallpaper_engine.providers.local_provider import LocalProvider
from wallpaper_engine.providers.nasa import NasaApodProvider
from wallpaper_engine.providers.wallhaven import WallhavenProvider


def run_live_verification():
    temp_dir = Path(tempfile.mkdtemp(prefix="wp_live_verify_"))
    cache_mgr = CacheManager(
        base_cache_dir=temp_dir / "cache",
        base_data_dir=temp_dir / "data",
    )
    src_mgr = SourceManager(config_dir=temp_dir / "config")

    providers = [
        ArchimgProvider(cache_manager=cache_mgr),
        WallhavenProvider(cache_manager=cache_mgr),
        BingProvider(cache_manager=cache_mgr),
        NasaApodProvider(cache_manager=cache_mgr),
        LocalProvider(cache_manager=cache_mgr),
    ]

    for p in providers:
        src_mgr.register_provider(p)

    print("==================================================")
    print("PHASE 1 LIVE PROVIDER VERIFICATION")
    print("==================================================")

    results = {}
    sample_wallpapers = {}

    for p in providers:
        print(f"\nTesting provider: {p.provider_name} [{p.provider_id}]...")
        start_t = time.time()
        try:
            items = p.get_featured(page=1)
            duration = round(time.time() - start_t, 2)
            if items:
                wp = items[0]
                sample_wallpapers[p.provider_id] = wp
                results[p.provider_id] = (True, f"{len(items)} items ({duration}s)")
                print(f"  ✓ SUCCESS: Received {len(items)} items in {duration}s")
                print(f"    Sample: [{wp.id}] {wp.title}")
                print(f"    Resolution: {wp.resolution_str} ({wp.aspect_ratio})")
                print(f"    License: {wp.license}")
                print(f"    URL: {wp.image_url[:60]}...")
            else:
                results[p.provider_id] = (True, f"0 items returned ({duration}s)")
                print(f"  ✓ SUCCESS: 0 items returned (empty feed)")
        except Exception as exc:
            duration = round(time.time() - start_t, 2)
            results[p.provider_id] = (False, f"Error: {exc} ({duration}s)")
            print(f"  ✗ FAILED: {exc}")

    # Test downloading and caching one real thumbnail from ArchImg
    archimg_wp = sample_wallpapers.get("archimg")
    if archimg_wp:
        print("\nTesting thumbnail generation & caching on ArchImg asset...")
        thumb_path = cache_mgr.fetch_and_cache_thumbnail(archimg_wp.thumbnail_url)
        if thumb_path and thumb_path.is_file():
            print(f"  ✓ Thumbnail cached at: {thumb_path} ({thumb_path.stat().st_size} bytes)")
        else:
            print("  ✗ Thumbnail caching failed")

    shutil.rmtree(temp_dir, ignore_errors=True)

    print("\n==================================================")
    print("SUMMARY")
    print("==================================================")
    all_passed = True
    for pid, (ok, msg) in results.items():
        status_sym = "✓ PASS" if ok else "✗ FAIL"
        if not ok:
            all_passed = False
        print(f"{pid:12} : {status_sym} - {msg}")

    return all_passed


if __name__ == "__main__":
    success = run_live_verification()
    exit(0 if success else 1)
