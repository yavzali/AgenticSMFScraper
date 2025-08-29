#!/usr/bin/env python3
"""
Patchright Update Verification Script
====================================

Verifies that the Patchright update from 1.50.0 to 1.52.5 is successful
and maintains compatibility with the AgenticScraper tripartite system.

This script tests:
- Patchright import and version compatibility
- PlaywrightAgent stealth capabilities
- Browser profiles directory status
- Persistent context functionality

Usage:
    cd Shared && python verify_patchright_update.py
"""

import sys
import os
import asyncio
import json
from pathlib import Path
from typing import Dict, Any

# Add shared path for imports
sys.path.append(os.path.dirname(__file__))

def print_header(title: str):
    """Print formatted section header"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def print_test(test_name: str, status: str, details: str = ""):
    """Print formatted test result"""
    status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"{status_icon} {test_name}: {status}")
    if details:
        print(f"   {details}")

async def test_patchright_import():
    """Test basic Patchright import and version"""
    print_header("Patchright Import & Version Test")
    
    try:
        import patchright
        print_test("Patchright Import", "PASS", f"Successfully imported patchright")
        
        # Try to get version info
        try:
            version = patchright.__version__
            print_test("Version Detection", "PASS", f"Version: {version}")
            
            # Check if version is 1.52.5 or higher
            version_parts = version.split('.')
            major, minor, patch = int(version_parts[0]), int(version_parts[1]), int(version_parts[2])
            
            if major > 1 or (major == 1 and minor > 52) or (major == 1 and minor == 52 and patch >= 5):
                print_test("Version Check", "PASS", f"Version {version} >= 1.52.5")
                return True
            else:
                print_test("Version Check", "FAIL", f"Version {version} < 1.52.5")
                return False
                
        except AttributeError:
            print_test("Version Detection", "WARN", "Version info not available")
            return True  # Continue testing even if version not detectable
            
    except ImportError as e:
        print_test("Patchright Import", "FAIL", f"Import error: {e}")
        return False

async def test_playwright_agent_compatibility():
    """Test PlaywrightAgent compatibility"""
    print_header("PlaywrightAgent Compatibility Test")
    
    try:
        from playwright_agent import PlaywrightMultiScreenshotAgent
        print_test("PlaywrightAgent Import", "PASS", "Successfully imported PlaywrightMultiScreenshotAgent")
        
        # Check if required methods exist
        agent = PlaywrightMultiScreenshotAgent()
        
        # Check for stealth setup method
        if hasattr(agent, '_setup_stealth_browser'):
            print_test("Stealth Method", "PASS", "_setup_stealth_browser method exists")
        else:
            print_test("Stealth Method", "FAIL", "_setup_stealth_browser method missing")
            return False
            
        # Check for async playwright usage
        from patchright.async_api import async_playwright
        print_test("Async Playwright", "PASS", "async_playwright available")
        
        return True
        
    except ImportError as e:
        print_test("PlaywrightAgent Import", "FAIL", f"Import error: {e}")
        return False
    except Exception as e:
        print_test("PlaywrightAgent Test", "FAIL", f"Error: {e}")
        return False

def test_browser_profiles_directory():
    """Test browser_profiles directory status"""
    print_header("Browser Profiles Directory Test")
    
    browser_profiles_path = Path(__file__).parent / "browser_profiles"
    
    if browser_profiles_path.exists():
        if browser_profiles_path.is_dir():
            profile_count = len(list(browser_profiles_path.iterdir()))
            print_test("Browser Profiles Dir", "PASS", f"Directory exists with {profile_count} profiles")
        else:
            print_test("Browser Profiles Dir", "FAIL", "Path exists but is not a directory")
            return False
    else:
        print_test("Browser Profiles Dir", "PASS", "Directory doesn't exist yet (will be created on first run)")
    
    return True

async def test_basic_browser_launch():
    """Test basic browser launch with persistent context"""
    print_header("Basic Browser Launch Test")
    
    try:
        from patchright.async_api import async_playwright
        
        async with async_playwright() as p:
            # Test basic browser launch
            browser_profiles_dir = Path(__file__).parent / "browser_profiles" / "test_profile"
            browser_profiles_dir.mkdir(parents=True, exist_ok=True)
            
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(browser_profiles_dir),
                channel="chrome",
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                ]
            )
            
            print_test("Browser Launch", "PASS", "Successfully launched Chrome with persistent context")
            
            # Test page creation
            page = await context.new_page()
            print_test("Page Creation", "PASS", "Successfully created new page")
            
            await context.close()
            print_test("Browser Cleanup", "PASS", "Successfully closed browser context")
            
            return True
            
    except Exception as e:
        print_test("Browser Launch", "FAIL", f"Error: {e}")
        return False

def test_requirements_file():
    """Test requirements.txt file for correct patchright version"""
    print_header("Requirements File Test")
    
    requirements_path = Path(__file__).parent / "requirements.txt"
    
    if not requirements_path.exists():
        print_test("Requirements File", "FAIL", "requirements.txt not found")
        return False
    
    with open(requirements_path, 'r') as f:
        content = f.read()
    
    # Check for single patchright line with correct version
    patchright_lines = [line.strip() for line in content.split('\n') if 'patchright' in line and not line.strip().startswith('#')]
    
    if len(patchright_lines) == 1:
        line = patchright_lines[0]
        if ">=1.52.5" in line:
            print_test("Requirements Version", "PASS", f"Found: {line}")
            return True
        else:
            print_test("Requirements Version", "FAIL", f"Wrong version in: {line}")
            return False
    elif len(patchright_lines) > 1:
        print_test("Requirements Duplicates", "FAIL", f"Found {len(patchright_lines)} patchright lines")
        return False
    else:
        print_test("Requirements Missing", "FAIL", "No patchright line found")
        return False

async def main():
    """Run all verification tests"""
    print_header("🔍 Patchright Update Verification v1.52.5")
    print("Testing AgenticScraper tripartite system compatibility...")
    
    results = []
    
    # Run all tests
    results.append(await test_patchright_import())
    results.append(await test_playwright_agent_compatibility())
    results.append(test_browser_profiles_directory())
    results.append(test_requirements_file())
    results.append(await test_basic_browser_launch())
    
    # Summary
    print_header("📊 Verification Summary")
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ Tests Passed: {passed}/{total}")
    print(f"❌ Tests Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Patchright 1.52.5 update successful")
        print("✅ AgenticScraper tripartite system compatibility maintained")
        print("✅ Ready for existing validation commands")
        
        print("\nNext steps:")
        print("1. pip install --upgrade patchright==1.52.5")
        print("2. cd '../New Product Importer' && python validate_import_system.py")
        print("3. cd '../Product Updater' && python validate_update_system.py") 
        print("4. cd '../Catalog Crawler' && python catalog_system_test.py --components-only")
        
        return True
    else:
        print("\n⚠️  SOME TESTS FAILED!")
        print("Please review the failed tests above and fix issues before proceeding.")
        return False

if __name__ == "__main__":
    asyncio.run(main())
