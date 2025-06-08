# 🚨 CRITICAL SETUP INSTRUCTIONS

## Immediate Actions Required

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Update Config.json
**CRITICAL**: Replace placeholder values with real credentials:

```json
{
  "shopify": {
    "store_url": "YOUR-ACTUAL-STORE.myshopify.com",
    "access_token": "YOUR_REAL_SHOPIFY_TOKEN"
  },
  "agents": {
    "openmanus": {
      "api_key": "YOUR_REAL_OPENMANUS_KEY"
    }
  },
  "notifications": {
    "email_username": "your_real_email@gmail.com",
    "email_password": "your_app_password",
    "email_recipients": ["recipient@email.com"]
  }
}
```

### 3. Create Missing Image Processors
**Copy `aritzia_image_processor.py` and modify for each retailer:**

```bash
# Create the 9 missing image processors
cp aritzia_image_processor.py asos_image_processor.py
cp aritzia_image_processor.py hm_image_processor.py
cp aritzia_image_processor.py uniqlo_image_processor.py
cp aritzia_image_processor.py revolve_image_processor.py
cp aritzia_image_processor.py mango_image_processor.py
cp aritzia_image_processor.py anthropologie_image_processor.py
cp aritzia_image_processor.py abercrombie_image_processor.py
cp aritzia_image_processor.py nordstrom_image_processor.py
cp aritzia_image_processor.py urban_outfitters_image_processor.py
```

**Then modify each file:**
- Change class name: `class AsosImageProcessor` (not AritziaImageProcessor)
- Update retailer-specific URL transformations
- Modify headers and referrer requirements

### 4. Replace Mock Agent Implementations

In `agent_extractor.py`, the agent calls are currently mocked:

```python
# REPLACE THIS MOCK CODE:
mock_data = {
    "retailer": retailer,
    "brand": "Example Brand",
    # ... rest of mock data
}

# WITH REAL OPENMANUS INTEGRATION:
response = await self.openmanus.extract(prompt)
extracted_data = response.get('data', {})
```

### 5. Test Database Connectivity

```python
# Test async database
import asyncio
from duplicate_detector import DuplicateDetector

async def test_db():
    detector = DuplicateDetector()
    stats = await detector.get_statistics()
    print(f"Database connection successful: {stats}")

asyncio.run(test_db())
```

## Known Issues Still Present

### 1. Pattern Learner Database (pattern_learner.py)
**Issue**: Still uses synchronous sqlite3
**Fix**: Apply same async conversion as duplicate_detector.py

### 2. Agent API Integration
**Issue**: All agents are mocked
**Fix**: Implement real OpenManus, Skyvern, Browser Use APIs

### 3. Manual Review CSV Operations
**Issue**: Synchronous file I/O in async context
**Fix**: May need `aiofiles` for true async file operations

### 4. Email Notifications
**Issue**: `smtplib` is synchronous
**Fix**: Consider `aiosmtplib` for async email sending

## Testing Before Full Deployment

### 1. Test Single URL
```bash
# Create minimal test file
echo '{"batch_id": "test", "modesty_level": "modest", "urls": ["https://aritzia.com/test-product"]}' > test.json

# Test with force-run to avoid scheduling
python main_scraper.py --batch-file test.json --force-run-now
```

### 2. Monitor Logs
```bash
# Watch logs in real-time
tail -f logs/scraper_main.log
tail -f logs/errors.log
```

### 3. Check Database
```python
import aiosqlite
import asyncio

async def check_products():
    async with aiosqlite.connect("products.db") as db:
        cursor = await db.execute("SELECT COUNT(*) FROM products")
        count = await cursor.fetchone()
        print(f"Products in database: {count[0]}")

asyncio.run(check_products())
```

## Performance Expectations

- **First Run**: May be slower due to pattern learning initialization
- **Database Creation**: Automatic on first use
- **Memory Usage**: 2-4 GB for large batches
- **Processing Speed**: 30-60 seconds per URL (varies by retailer)

## Emergency Debugging

If the system fails:

1. **Check requirements**: `pip install -r requirements.txt`
2. **Verify config**: Ensure all credentials are real
3. **Check logs**: `logs/errors.log` for specific errors  
4. **Test components**: Run individual scripts to isolate issues
5. **Database issues**: Delete `products.db` to recreate
6. **Resume capability**: Use `--resume` flag after interruptions

### API Keys Required

1. **Google Gemini API** (Primary LLM)
   ```bash
   export GOOGLE_API_KEY="your_gemini_api_key"
   ```

2. **OpenManus API** (if using OpenManus agent)
   ```bash
   export OPENMANUS_API_KEY="your_openmanus_api_key"
   ```

3. **Browser Use** (Uses Gemini API key)
   - No separate key needed, uses GOOGLE_API_KEY

4. **DeepSeek API** (For Markdown Extractor)
   ```bash
   export DEEPSEEK_API_KEY="your_deepseek_api_key"
   ```
   - Get your API key from: https://platform.deepseek.com/api_keys
   - Optional: If not provided, markdown extractor will use only Gemini Flash 2.0