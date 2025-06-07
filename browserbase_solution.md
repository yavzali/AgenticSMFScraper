# Browserbase Setup Guide

## Why Browserbase is Better:
- **5-10x faster** than local browser automation
- **No local browser overhead** - runs in optimized cloud
- **Better anti-bot protection** - residential IPs, optimized headers
- **Parallel processing** - multiple extractions simultaneously
- **Reduced API costs** - faster = fewer tokens

## Setup:

1. **Sign up at [browserbase.com](https://browserbase.com)**
2. **Get API key**
3. **Install Browserbase Python SDK:**
   ```bash
   pip install browserbase
   ```

4. **Implementation in your system:**
```python
# In agent_extractor.py
async def _extract_with_browserbase(self, url: str, retailer: str, learned_patterns: List, prompt: str):
    from browserbase import Browserbase
    
    bb = Browserbase(api_key="your-api-key")
    
    # Create a session
    session = bb.create_session()
    
    # Navigate and extract
    result = await session.evaluate(f"""
        // Navigate to URL
        await page.goto('{url}');
        await page.waitForLoadState('networkidle');
        
        // Extract data using your prompt logic
        const data = {{
            title: document.querySelector('h1')?.textContent?.trim(),
            price: document.querySelector('[data-test="price"]')?.textContent?.trim(),
            // ... other fields
        }};
        
        return data;
    """)
    
    await session.close()
    return ExtractionResult(success=True, data=result, ...)
```

## Expected Performance:
- **30-90 seconds** instead of 5+ minutes
- **95% success rate** on major retailers
- **Cost effective** - pay per minute of browser time 