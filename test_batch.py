import asyncio
import json
from batch_processor import BatchProcessor

async def main():
    # Load batch file
    with open('batch_001_June_7th.json', 'r') as f:
        batch_data = json.load(f)
    
    processor = BatchProcessor()
    result = await processor.process_batch(
        batch_data['urls'], 
        batch_data['modesty_level'], 
        batch_data['batch_id']
    )
    
    print('Batch processing completed!')
    print(f'Success rate: {result["success_rate"]:.1f}%')
    print(f'Successful: {result["successful_count"]}/{result["total_urls"]}')
    print(f'Method performance: {result["method_performance"]}')

if __name__ == "__main__":
    asyncio.run(main()) 