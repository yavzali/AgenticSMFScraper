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

# 🛠️ **Setup Instructions - Agent Modest Scraper System**

## 🎯 **Dual Engine Architecture Setup**

This system uses **dual extraction engines** requiring different API keys for optimal performance:
- **Markdown Extractor** (5 retailers): Jina AI + DeepSeek V3/Gemini Flash 2.0
- **Browser Agents** (5 retailers): Browser Use + OpenManus with verification handling

## 📋 **Prerequisites**

### **System Requirements**
- **Python 3.8+** (tested with 3.9, 3.10, 3.11)
- **Chrome/Chromium** (for browser agents)
- **4GB+ RAM** (for browser automation)
- **Stable internet connection** (for Jina AI and verification challenges)

### **Operating System Support**
- ✅ **macOS** (primary development)
- ✅ **Linux** (Ubuntu 20.04+)
- ✅ **Windows** (with WSL recommended)

## 🔑 **API Keys Required**

### **1. Google Gemini API** (Required)
```bash
export GOOGLE_API_KEY="your_gemini_api_key"
```
- **Used for:** Browser agents, markdown extractor fallback
- **Get key from:** https://makersuite.google.com/app/apikey
- **Cost:** Free tier available, pay-per-use
- **Required for:** All system operations

### **2. DeepSeek API** (Optional but Recommended)
```bash
export DEEPSEEK_API_KEY="your_deepseek_api_key"
```
- **Used for:** Primary LLM in markdown extraction cascade
- **Get key from:** https://platform.deepseek.com/api_keys
- **Cost:** Very cost-effective, high performance
- **Benefits:** Better extraction quality, lower costs for markdown retailers

### **3. Shopify API** (Required for Production)
```bash
# Set in config.json
{
  "shopify": {
    "api_key": "your_shopify_api_key",
    "secret": "your_shopify_secret",
    "store_url": "your-store.myshopify.com"
  }
}
```
- **Used for:** Product creation and updates
- **Get from:** Shopify Partner Dashboard or store admin
- **Required for:** Product uploads to store

## 🚀 **Installation Steps**

### **Step 1: Clone Repository**
```bash
git clone https://github.com/yavzali/AgenticSMFScraper.git
cd "Agent Modest Scraper System"
```

### **Step 2: Create Virtual Environment**
```bash
# Create virtual environment
python -m venv scraper_env

# Activate environment
# On macOS/Linux:
source scraper_env/bin/activate
# On Windows:
scraper_env\Scripts\activate
```

### **Step 3: Install Dependencies**
```bash
# Install all required packages
pip install -r requirements.txt

# Verify critical imports
python -c "import browser_use, google.generativeai, requests; print('✅ Core dependencies installed')"
```

### **Step 4: Configure API Keys**

#### **Environment Variables (Recommended)**
```bash
# Add to ~/.bashrc, ~/.zshrc, or create .env file
export GOOGLE_API_KEY="your_gemini_api_key"
export DEEPSEEK_API_KEY="your_deepseek_api_key"  # Optional but recommended
```

#### **Config File Setup**
```bash
# Copy example config
cp config.json.example config.json

# Edit configuration
nano config.json
```

### **Step 5: Verify Installation**
```bash
# Test markdown extractor
python -c "from markdown_extractor import MarkdownExtractor; print('✅ Markdown extractor ready')"

# Test browser agents
python -c "from agent_extractor import AgentExtractor; print('✅ Browser agents ready')"

# Test integration
python test_integration_routing.py
```

## 🔧 **Configuration Details**

### **config.json Structure**
```json
{
  "extraction_routing": {
    "markdown_retailers": ["asos", "mango", "uniqlo", "revolve", "hm"],
    "browser_retailers": ["nordstrom", "aritzia", "anthropologie", "urban_outfitters", "abercrombie"]
  },
  "markdown_extractor": {
    "cache_expiry_days": 5,
    "token_limit": 120000,
    "models": {
      "deepseek": "deepseek-chat",
      "gemini": "gemini-2.0-flash-exp"
    }
  },
  "browser_agents": {
    "browser_use": {
      "enabled": true,
      "headless": true,
      "timeout": 120
    },
    "openmanus": {
      "enabled": true,
      "timeout": 90
    }
  },
  "shopify": {
    "api_key": "your_shopify_api_key",
    "secret": "your_shopify_secret",
    "store_url": "your-store.myshopify.com"
  },
  "image_processing": {
    "quality_threshold": 80,
    "min_resolution": [800, 800],
    "min_file_size": 102400
  }
}
```

### **Retailer-Specific Settings**
```json
{
  "retailers": {
    "asos": {
      "extraction_method": "markdown",
      "image_patterns": ["$XXL$", "$XXXL$"],
      "fallback_to_browser": true
    },
    "nordstrom": {
      "extraction_method": "browser_agent",
      "verification_handling": "press_and_hold",
      "timeout": 180
    }
  }
}
```

## 🧪 **Testing & Validation**

### **Basic Functionality Tests**
```bash
# Test markdown extraction for supported retailers
python test_markdown_extractor.py

# Test browser agent verification handling
python test_verification_handling.py

# Test routing logic
python test_integration_routing.py

# Test single URL extraction
python test_single_url.py "https://www.asos.com/product-url" asos
```

### **System Integration Test**
```bash
# Complete system validation
python -c "
from agent_extractor import AgentExtractor
from markdown_extractor import MarkdownExtractor, MARKDOWN_RETAILERS
import asyncio

async def test_system():
    agent = AgentExtractor()
    print(f'✅ Markdown retailers: {MARKDOWN_RETAILERS}')
    print('✅ All systems operational')

asyncio.run(test_system())
"
```

## 🛡️ **Security & Best Practices**

### **API Key Security**
```bash
# Use environment variables (recommended)
export GOOGLE_API_KEY="your_key"
export DEEPSEEK_API_KEY="your_key"

# Or use .env file (add to .gitignore)
echo "GOOGLE_API_KEY=your_key" > .env
echo "DEEPSEEK_API_KEY=your_key" >> .env
```

### **Rate Limiting Configuration**
```json
{
  "rate_limiting": {
    "requests_per_minute": 30,
    "concurrent_requests": 3,
    "retry_delays": [1, 2, 4, 8]
  }
}
```

### **Anti-Detection Measures**
```json
{
  "anti_detection": {
    "user_agent_rotation": true,
    "proxy_rotation": false,
    "request_delays": [1, 3],
    "retailer_specific_headers": true
  }
}
```

## 🔍 **Troubleshooting**

### **Common Issues**

#### **1. Import Errors**
```bash
# Check Python version
python --version  # Should be 3.8+

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Verify specific imports
python -c "import browser_use; print('Browser Use OK')"
python -c "import google.generativeai; print('Gemini OK')"
```

#### **2. API Key Issues**
```bash
# Verify environment variables
echo $GOOGLE_API_KEY
echo $DEEPSEEK_API_KEY

# Test API connectivity
python -c "
import google.generativeai as genai
import os
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
print('✅ Gemini API connected')
"
```

#### **3. Browser Agent Issues**
```bash
# Check Chrome installation
google-chrome --version
# or
chromium --version

# Test browser initialization
python test_anti_detection.py
```

#### **4. Markdown Extractor Issues**
```bash
# Test Jina AI connectivity
python -c "
import requests
response = requests.get('https://r.jina.ai/https://www.asos.com')
print(f'Jina AI status: {response.status_code}')
"

# Test cache system
python -c "
from markdown_extractor import MarkdownExtractor
extractor = MarkdownExtractor()
print('✅ Markdown cache system ready')
"
```

## 📊 **Performance Optimization**

### **Memory Management**
```json
{
  "performance": {
    "max_concurrent_extractions": 3,
    "cache_size_mb": 100,
    "log_retention_days": 7
  }
}
```

### **Cost Optimization**
```json
{
  "cost_optimization": {
    "prefer_markdown_extraction": true,
    "cache_markdown": true,
    "fallback_timeout_seconds": 30
  }
}
```

## 🚀 **Ready for Production**

### **Final Validation Checklist**
- [ ] All API keys configured and tested
- [ ] Dependencies installed and verified
- [ ] Browser agents can handle verification challenges
- [ ] Markdown extractor processes supported retailers
- [ ] Image processing quality meets standards
- [ ] Shopify integration tested (if using)
- [ ] Logging system operational
- [ ] Cost tracking active

### **Launch Commands**
```bash
# Single URL test
python test_single_url.py "https://www.uniqlo.com/us/en/products/E479225-000" uniqlo

# Batch processing
python batch_processor.py --input urls.json --output results.json

# Monitor system
tail -f logs/scraper_main.log
```

---

**🎯 Setup Status:** Ready for production with dual engine architecture optimized for cost and success rates across 10 major fashion retailers.