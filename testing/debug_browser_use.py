import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from agent_extractor import AgentExtractor

# Set debug logging
logging.basicConfig(level=logging.DEBUG)

async def test_browser_use():
    extractor = AgentExtractor()
    result = await extractor.extract_product_data(
        'https://www.uniqlo.com/us/en/products/E479225-000/00?colorDisplayCode=00&sizeDisplayCode=003', 
        'uniqlo'
    )
    print('\n' + '='*50)
    print('FINAL RESULT DATA:')
    print(result.data)
    print('='*50)

if __name__ == "__main__":
    asyncio.run(test_browser_use()) 