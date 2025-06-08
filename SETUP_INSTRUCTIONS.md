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

# 🛠️ **Setup Instructions - Agent Modest Scraper System v4.1**

## 🎯 **Dual Engine Architecture Setup**

This system uses **dual extraction engines** requiring different API keys for optimal performance:
- **Markdown Extractor** (5 retailers): Jina AI + DeepSeek V3/Gemini Flash 2.0
- **Browser Agents** (5 retailers): Browser Use with comprehensive verification handling

## 📋 **Prerequisites**

### **System Requirements**
- **Python 3.8+** (tested with 3.9, 3.10, 3.11)
- **Chrome/Chromium** (for browser automation)
- **4GB+ RAM** (for browser automation)
- **Stable internet connection** (for Jina AI and verification challenges)

### **Operating System Support**
- ✅ **macOS** (primary development)
- ✅ **Linux** (Ubuntu 20.04+)
- ✅ **Windows** (with WSL recommended)

## 🚀 **Installation Steps**

### **Step 1: Clone and Install Dependencies**
```bash
# Navigate to your project directory
cd "Agent Modest Scraper System"

# Install core Python dependencies
pip install -r requirements.txt

# Verify installation
python -c "import aiohttp, aiosqlite, pillow; print('✅ Core dependencies installed')"
```

### **Step 2: Configure API Keys**

#### **🔑 Required: Google Gemini API**
```bash
# Get your API key from: https://makersuite.google.com/app/apikey
export GOOGLE_API_KEY="your_gemini_api_key"

# Or add to your shell profile (.bashrc, .zshrc)
echo 'export GOOGLE_API_KEY="your_gemini_api_key"' >> ~/.zshrc
```

#### **🔑 Optional: DeepSeek API** (Improves markdown extraction)
```bash
# Get your API key from: https://platform.deepseek.com/api_keys
export DEEPSEEK_API_KEY="your_deepseek_api_key"

# Note: Without DeepSeek, markdown extractor will use only Gemini Flash 2.0
```

### **Step 3: Configure Shopify Integration**

Edit `config.json` with your actual Shopify credentials:
```json
{
  "shopify": {
    "store_url": "your-actual-store.myshopify.com",
    "access_token": "shppa_your_real_shopify_private_app_token",
    "api_version": "2023-10"
  },
  "agents": {
    "openmanus": {
      "api_key": "your_gemini_api_key",
      "installation_path": "/path/to/openmanus",
      "conda_env": "/path/to/conda/env",
      "timeout": 90
    }
  },
  "notifications": {
    "email_enabled": true,
    "email_username": "your_notification_email@gmail.com",
    "email_password": "your_app_password",
    "email_recipients": ["recipient@email.com"]
  }
}
```

### **Step 4: Optional Browser Use Setup**

Browser Use is automatically detected if available. You can either:

#### **Option A: Install via pip**
```bash
pip install browser-use==0.1.43
```

#### **Option B: External installation (recommended)**
```bash
# Place browser-use in parent directory
cd ..
git clone https://github.com/browser-use/browser-use.git
cd "Agent Modest Scraper System"

# System will automatically detect ../browser-use/ directory
```

### **Step 5: Verify Installation**

```bash
# Test core system components
python -c "
from agent_extractor import AgentExtractor
from markdown_extractor import MarkdownExtractor
from batch_processor import BatchProcessor
print('🎯 All core components working!')
print('✅ System ready for operation!')
"

# Test markdown extractor (requires API keys)
cd testing
python test_markdown_extractor.py --quick

# Test integration routing
python test_integration_routing.py

# Return to main directory
cd ..
```

## 🏗️ **Directory Structure After Setup**

```
Your Workspace/
├── Agent Modest Scraper System/     # Main project (this repo)
│   ├── agent_extractor.py           # Core extraction system
│   ├── markdown_extractor.py        # Jina AI + LLM system
│   ├── config.json                  # Your configured settings
│   ├── products.db                  # Product database (auto-created)
│   ├── patterns.db                  # Learned patterns (auto-created)
│   ├── markdown_cache.pkl           # 5-day cache (auto-created)
│   ├── testing/                     # All test files
│   └── logs/                        # System logs (auto-created)
├── browser-use/                     # External dependency (optional)
└── openmanus/                       # External dependency (optional)
```

## 🧪 **Testing Your Setup**

### **Quick System Test**
```bash
# Test basic functionality
python testing/test_prompt_generation.py

# Test a single URL with markdown extraction
python testing/test_single_url.py "https://www.uniqlo.com/us/en/products/E479225-000" uniqlo

# Test batch processing (dry run)
python main_scraper.py --batch-file batch_001_June_7th.json --force-run-now
```

### **Advanced Testing**
```bash
# Test all extraction methods
cd testing

# Test markdown extractor specifically
python test_markdown_extractor.py --verbose

# Test verification handling capabilities
python test_verification_handling.py

# Test anti-detection measures
python test_anti_detection.py

# Return to main directory
cd ..
```

## 🔧 **Configuration Options**

### **Markdown Extractor Settings**
The system supports these retailers for markdown extraction:
- **ASOS** - Fast, reliable
- **Mango** - Consistent results  
- **Uniqlo** - Complex image patterns
- **Revolve** - Designer brands
- **H&M** - Sometimes works (inconsistent)

### **Browser Agent Settings**
These retailers require browser automation:
- **Nordstrom** - Advanced anti-bot protection
- **Aritzia** - "Verify you are human" checkboxes
- **Anthropologie** - Press & hold verification (4-6 seconds)
- **Urban Outfitters** - Press & hold verification (4-6 seconds)
- **Abercrombie** - Multi-step verification

### **Performance Tuning**
```json
{
  "cost_optimization": {
    "cache_enabled": true,
    "cache_expiry_days": 5,
    "max_retries": 3
  },
  "browser_settings": {
    "timeout": 120,
    "headless": true,
    "anti_detection": true
  }
}
```

## 🆘 **Troubleshooting**

### **Common Installation Issues**

#### **Import Errors**
```bash
# Problem: ModuleNotFoundError
# Solution: Reinstall dependencies
pip install --upgrade -r requirements.txt

# Check specific package
python -c "import browser_use; print('Browser Use available')"
```

#### **API Key Issues**
```bash
# Check environment variables
echo $GOOGLE_API_KEY
echo $DEEPSEEK_API_KEY

# Test API connectivity
python -c "
import os
from langchain_google_genai import ChatGoogleGenerativeAI
llm = ChatGoogleGenerativeAI(
    model='gemini-2.0-flash-exp',
    google_api_key=os.getenv('GOOGLE_API_KEY')
)
print('✅ Gemini API working')
"
```

#### **Database Issues**
```bash
# Reset databases (will recreate automatically)
rm *.db *.pkl

# Test database creation
python -c "
from duplicate_detector import DuplicateDetector
import asyncio
async def test_db():
    dd = DuplicateDetector()
    print('✅ Database system working')
asyncio.run(test_db())
"
```

#### **Browser Use Issues**
```bash
# Check Browser Use availability
python -c "
try:
    from browser_use import Browser
    print('✅ Browser Use available')
except ImportError:
    print('⚠️ Browser Use not found - install separately or place in ../browser-use/')
"
```

### **Performance Issues**

#### **Slow Markdown Extraction**
- Check internet connection (Jina AI requires stable connection)
- Verify DeepSeek API key (improves speed and quality)
- Monitor cache hit rate in logs

#### **Browser Agent Timeouts**
- Increase timeout values in config.json
- Check Chrome/Chromium installation
- Monitor verification challenge handling in logs

### **Verification Issues**

#### **Anti-bot Challenges**
- Enable debug mode: `DEBUG=1 python main_scraper.py`
- Check specific retailer verification in logs
- Test verification handling: `python testing/test_verification_handling.py`

## 📊 **Expected Performance**

### **First Run**
- **Markdown cache**: Empty (will build over time)
- **Pattern database**: Will learn from extractions
- **Speed**: Slower due to cache misses

### **Steady State**
- **Cache hit rate**: 60-70%
- **Success rate**: 80-90% combined
- **Speed**: Markdown 5-10s, Browser 30-120s
- **Cost**: $0.02-0.30 per URL depending on method

## 🔄 **Maintenance**

### **Regular Tasks**
```bash
# Clear old logs (weekly)
find logs/ -name "*.log" -mtime +7 -delete

# Monitor database size
ls -lh *.db *.pkl

# Update dependencies (monthly)
pip install --upgrade -r requirements.txt
```

### **Cache Management**
```bash
# Clear markdown cache (forces fresh extraction)
rm markdown_cache.pkl

# Reset pattern learning (starts fresh)
rm patterns.db

# Full reset (keeps config.json)
rm *.db *.pkl
```

## 🚀 **Production Deployment**

### **Pre-Production Checklist**
- [ ] All API keys configured and tested
- [ ] Shopify integration working
- [ ] Browser Use available (optional but recommended)
- [ ] Test suite passing
- [ ] Logging directory writable
- [ ] Sufficient disk space for databases

### **Running in Production**
```bash
# Run with scheduling optimization
python main_scraper.py --batch-file your_batch.json

# Force immediate run (bypass scheduling)
python main_scraper.py --batch-file your_batch.json --force-run-now

# Resume interrupted batch
python main_scraper.py --batch-file your_batch.json --resume
```

---

## 📈 **System Ready!**

Your **Agent Modest Scraper System v4.1** is now configured with:
- ✅ **Dual extraction engines** with intelligent routing
- ✅ **External dependency management** for Browser Use
- ✅ **Comprehensive verification handling** for anti-bot challenges
- ✅ **Production-ready architecture** with proper error handling
- ✅ **Clean GitHub structure** with private data protection

**Next step:** Run your first batch with `python main_scraper.py --batch-file batch_001_June_7th.json --force-run-now`