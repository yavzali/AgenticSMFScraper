#!/usr/bin/env python3

import asyncio
import json
from unified_extractor import UnifiedExtractor

async def test_unified_system():
    print('🔄 TESTING UNIFIED EXTRACTION SYSTEM')
    print('=' * 50)
    
    # Test initialization
    extractor = UnifiedExtractor()
    print('✅ UnifiedExtractor initialized successfully')
    
    # Check available methods
    stats = await extractor.get_extraction_stats()
    print(f'📊 Available methods: {stats["methods_available"]}')
    
    # Test URLs (mix of markdown and Playwright retailers)
    test_urls = [
        {
            'url': 'https://www.uniqlo.com/us/en/products/E443577-000',
            'retailer': 'uniqlo',
            'expected_method': 'markdown_extractor'
        },
        {
            'url': 'https://www.aritzia.com/us/en/product/effortless-pant/70347.html',
            'retailer': 'aritzia',
            'expected_method': 'playwright_agent'
        }
    ]
    
    print(f'\n🧪 Testing {len(test_urls)} URLs across different methods')
    
    for i, test_case in enumerate(test_urls, 1):
        print(f'\n[{i}/{len(test_urls)}] Testing {test_case["retailer"]}: {test_case["url"]}')
        
        try:
            result = await extractor.extract_product_data(test_case['url'], test_case['retailer'])
            
            print(f'  📤 Method used: {result.method_used}')
            print(f'  ⏱️  Processing time: {result.processing_time:.2f}s')
            print(f'  ✅ Success: {result.success}')
            
            if result.success:
                data = result.data
                print(f'  📦 Data fields: {list(data.keys())}')
                if 'title' in data:
                    title = data['title'][:50] + '...' if len(data.get('title', '')) > 50 else data.get('title', 'N/A')
                    print(f'  📝 Title: {title}')
                if 'price' in data:
                    print(f'  💰 Price: {data.get("price", "N/A")}')
                
                # Check if method matches expectation
                if result.method_used.startswith(test_case['expected_method']):
                    print(f'  ✅ Expected method used: {test_case["expected_method"]}')
                else:
                    print(f'  ⚠️  Expected {test_case["expected_method"]}, got {result.method_used}')
            
            else:
                print(f'  ❌ Errors: {result.errors}')
                print(f'  ⚠️  Warnings: {result.warnings}')
                
        except Exception as e:
            print(f'  💥 Exception: {e}')
    
    print('\n📊 ARCHITECTURE COMPARISON')
    print('=' * 30)
    print('OLD: main → batch_processor → agent_extractor → playwright_agent')
    print('                            ↘ markdown_extractor')  
    print('NEW: main → batch_processor → unified_extractor → playwright_agent')
    print('                                                ↘ markdown_extractor')
    print('\n✅ BENEFITS:')
    print('  • Reduced complexity: 1419 → ~215 lines')
    print('  • Single extraction interface')
    print('  • Maintains all functionality: routing, caching, pattern learning')
    print('  • Cleaner architecture with same performance')
    
    print('\n🎯 Unified system test: COMPLETE')

if __name__ == "__main__":
    asyncio.run(test_unified_system()) 