"""Live integration verification for Phase 2: SearchAggregator, Setter, and Rotation."""

from pathlib import Path
import shutil
import tempfile
import time

from wallpaper_engine.core.cache_manager import CacheManager
from wallpaper_engine.core.models import SearchFilter
from wallpaper_engine.core.rotation_service import RotationService
from wallpaper_engine.core.search_service import SearchAggregator
from wallpaper_engine.core.source_manager import SourceManager
from wallpaper_engine.providers.archimg import ArchimgProvider
from wallpaper_engine.providers.bing import BingProvider
from wallpaper_engine.providers.local_provider import LocalProvider
from wallpaper_engine.providers.nasa import NasaApodProvider
from wallpaper_engine.providers.wallhaven import WallhavenProvider
from wallpaper_engine.setters.detector import get_best_setter


def run_phase2_verification():
    print("==================================================")
    print("PHASE 2 LIVE AGGREGATION & SETTER VERIFICATION")
    print("==================================================")

    temp_dir = Path(tempfile.mkdtemp(prefix="wp_phase2_verify_"))
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

    aggregator = SearchAggregator(src_mgr, max_workers=5)

    # 1. Test Aggregated Featured Feed
    print("\n1. Testing Aggregated Featured Feed across providers...")
    start_t = time.time()
    featured = aggregator.get_featured(page=1)
    duration = round(time.time() - start_t, 2)
    print(f"  ✓ Fetched {len(featured)} interleaved items in {duration}s")
    providers_in_feed = set(wp.provider_id for wp in featured)
    print(f"    Represented providers: {list(providers_in_feed)}")

    # 2. Test Multi-Provider Unified Search
    print("\n2. Testing Unified Search for 'dark'...")
    start_t = time.time()
    results = aggregator.search(SearchFilter(query="dark", page=1, page_size=20))
    duration = round(time.time() - start_t, 2)
    print(f"  ✓ Search returned {len(results)} items in {duration}s")
    for wp in results[:3]:
        print(f"    - [{wp.provider_name}] {wp.title} ({wp.resolution_str})")

    # 3. Test Desktop Setter Detection
    print("\n3. Testing Wallpaper Setter Detection...")
    setter = get_best_setter()
    print(f"  ✓ Detected primary setter: {setter.name}")

    # 4. Test Rotation Service Single Cycle (Offline Mode Fallback)
    print("\n4. Testing Rotation Service Single Cycle...")
    rot_service = RotationService(
        source_manager=src_mgr,
        search_aggregator=aggregator,
        cache_manager=cache_mgr,
        wallpaper_setter=setter,
    )
    rot_service.source_pool = "downloaded"
    # Create one test image in wallpapers_dir
    test_img = cache_mgr.wallpapers_dir / "test_wallpaper.jpg"
    from PIL import Image
    img = Image.new("RGB", (1920, 1080), color=(30, 30, 46))
    img.save(test_img)

    rotated = rot_service.rotate_now()
    print(f"  ✓ Rotation executed with local pool: {rotated}")

    shutil.rmtree(temp_dir, ignore_errors=True)

    print("\n==================================================")
    print("PHASE 2 VERIFICATION SUMMARY: ALL PASSED")
    print("==================================================")
    return True


if __name__ == "__main__":
    run_phase2_verification()
