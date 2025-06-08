# 🚀 **Quick Reference Guide - Agent Modest Scraper System v4.1**

## 📋 **System Status Overview**

| Component | Status | Method | Success Rate | Cost/URL |
|-----------|--------|--------|--------------|----------|
| **Markdown Extractor** | ✅ Active | Jina AI + LLM | 80-95% | $0.02-0.05 |
| **Browser Agents** | ✅ Active | Browser Use | 70-85% | $0.10-0.30 |
| **Verification Handling** | ✅ Active | Auto-detect | 75-90% | Variable |
| **Image Processing** | ✅ Active | 4-layer system | 85/100 avg | Included |
| **Database System** | ✅ Active | SQLite async | 99.9% | Free |

## 🎯 **Retailer Routing Matrix**

### **Markdown Extraction (Fast & Cheap)**
| Retailer | Success Rate | Speed | Special Notes |
|----------|--------------|-------|---------------|
| **ASOS** | 90-95% | 5-8s | Most reliable, high-res images |
| **Mango** | 85-90% | 6-10s | Consistent, good for bulk |
| **Uniqlo** | 80-90% | 8-12s | Complex image patterns |
| **Revolve** | 85-95% | 5-10s | Designer brands, premium |
| **H&M** | 60-75% | 5-15s | Inconsistent, fast when works |

### **Browser Automation (Anti-bot Handling)**
| Retailer | Verification Type | Success Rate | Speed |
|----------|-------------------|--------------|-------|
| **Nordstrom** | Advanced anti-bot | 75-85% | 45-90s |
| **Aritzia** | Checkbox + Cloudflare | 70-80% | 60-120s |
| **Anthropologie** | Press & Hold (4-6s) | 75-85% | 90-150s |
| **Urban Outfitters** | Press & Hold (4-6s) | 70-80% | 90-150s |
| **Abercrombie** | Multi-step verification | 65-75% | 120-180s |

## ⚡ **Essential Commands**

### **🧪 Testing & Validation**
```bash
# Quick system check
python -c "from agent_extractor import AgentExtractor; print('✅ System ready!')"

# Test single URL with routing
cd testing
python test_single_url.py "URL_HERE" retailer_name

# Test markdown extractor (fast test)
python test_markdown_extractor.py --quick

# Test all routing logic
python test_integration_routing.py

# Test verification handling
python test_verification_handling.py

# Test anti-detection measures  
python test_anti_detection.py

# Return to main directory
cd ..
```

### **🚀 Production Commands**
```bash
# Run batch with scheduling
python main_scraper.py --batch-file batch_001_June_7th.json

# Force immediate run (bypass scheduling)
python main_scraper.py --batch-file batch_001_June_7th.json --force-run-now

# Resume interrupted batch
python main_scraper.py --batch-file batch_001_June_7th.json --resume

# Dry run (test without actual extraction)
python main_scraper.py --batch-file batch_001_June_7th.json --dry-run
```

### **🔧 Maintenance Commands**
```bash
# Clear markdown cache (force fresh extraction)
rm markdown_cache.pkl

# Reset pattern learning database
rm patterns.db

# Clear product database (treat all as new)
rm products.db

# Full system reset (keeps config)
rm *.db *.pkl

# Check logs
tail -f logs/scraper_main.log
tail -f logs/errors.log

# Monitor system
watch -n 5 "ls -lh *.db *.pkl"
```

## 🎚️ **Configuration Quick Setup**

### **🔑 Essential API Keys**
```bash
# Required: Google Gemini
export GOOGLE_API_KEY="your_gemini_api_key"

# Optional: DeepSeek (improves markdown quality)
export DEEPSEEK_API_KEY="your_deepseek_api_key"

# Verify keys
echo $GOOGLE_API_KEY | cut -c1-20  # Show first 20 chars
```

### **⚙️ Config.json Essentials**
```json
{
  "shopify": {
    "store_url": "your-store.myshopify.com",
    "access_token": "shppa_your_shopify_token"
  },
  "extraction_routing": {
    "markdown_retailers": ["asos", "mango", "uniqlo", "revolve", "hm"],
    "browser_retailers": ["nordstrom", "aritzia", "anthropologie", "urban_outfitters", "abercrombie"]
  }
}
```

## 📊 **System Performance Metrics**

### **⚡ Speed Benchmarks**
- **Markdown Extraction**: 5-15 seconds per URL
- **Browser Agent**: 30-180 seconds per URL  
- **Image Processing**: 2-5 seconds (included in above)
- **Database Operations**: <1 second

### **💰 Cost Analysis**
| Method | Cost/URL | Monthly (1000 URLs) | Best For |
|--------|----------|---------------------|----------|
| **Markdown** | $0.02-0.05 | $20-50 | High volume, supported retailers |
| **Browser** | $0.10-0.30 | $100-300 | Anti-bot sites, verification |
| **Combined** | $0.04-0.15 | $40-150 | Optimal routing (60% savings) |

### **🎯 Success Rate Optimization**
- **Smart Routing**: Choose optimal method per retailer
- **Fallback Strategy**: Markdown → Browser → Manual review
- **Cache Hit**: 65% cache rate reduces costs
- **Quality Validation**: 85/100 average image score

## 🛠️ **Troubleshooting Quick Fixes**

### **❌ Common Issues**

#### **Import Errors**
```bash
# Fix: Reinstall dependencies
pip install --upgrade -r requirements.txt

# Check specific module
python -c "import browser_use; print('✅ Browser Use available')"
```

#### **API Key Issues**  
```bash
# Check environment
env | grep API_KEY

# Test Gemini connection
python -c "
from langchain_google_genai import ChatGoogleGenerativeAI
import os
llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash-exp', google_api_key=os.getenv('GOOGLE_API_KEY'))
print('✅ Gemini working')
"
```

#### **Database Issues**
```bash
# Reset databases (auto-recreate)
rm *.db *.pkl

# Test database creation
python -c "
from duplicate_detector import DuplicateDetector
import asyncio
asyncio.run(DuplicateDetector().get_statistics())
print('✅ Database working')
"
```

#### **Browser Use Issues**
```bash
# Check installation
python -c "
try:
    from browser_use import Browser
    print('✅ Browser Use found')
except ImportError:
    print('⚠️ Install: pip install browser-use or place in ../browser-use/')
"
```

## 📁 **Directory Structure Reference**

```
Agent Modest Scraper System/
├── 🎯 **Core System**
│   ├── main_scraper.py          # Entry point
│   ├── batch_processor.py       # Workflow manager
│   ├── agent_extractor.py       # Browser agents + routing
│   └── markdown_extractor.py    # Jina AI + LLM system
├── 🖼️ **Image Processing**
│   ├── image_processor_factory.py
│   ├── *_image_processor.py     # Retailer-specific
│   └── base_image_processor.py
├── 💾 **Data & Config**
│   ├── config.json              # Configuration
│   ├── products.db              # Product database
│   ├── patterns.db              # Learned patterns
│   └── markdown_cache.pkl       # 5-day cache
├── 🧪 **Testing**
│   └── testing/                 # All test files
└── 📚 **Documentation**
    ├── README.md
    ├── SETUP_INSTRUCTIONS.md
    └── QUICK_REFERENCE.md       # This file
```

## 🔍 **Debugging & Monitoring**

### **📊 Real-time Monitoring**
```bash
# Watch log files
tail -f logs/scraper_main.log | grep -E "(SUCCESS|ERROR|WARNING)"

# Monitor extraction progress
watch -n 10 "grep -c 'extracted successfully' logs/scraper_main.log"

# Check database growth
watch -n 30 "ls -lh *.db *.pkl"

# Monitor API usage/costs
grep "API cost" logs/scraper_main.log | tail -10
```

### **🐛 Debug Commands**
```bash
# Enable debug mode
DEBUG=1 python main_scraper.py --batch-file your_batch.json --force-run-now

# Test specific retailer
cd testing
python test_single_url.py "https://www.asos.com/product/..." asos

# Check verification handling
python test_verification_handling.py --retailer aritzia

# Test markdown extraction
python test_markdown_extractor.py --retailer uniqlo --verbose
```

## 🚀 **Development Commands**

### **📝 Creating Test Batches**
```json
// Create test_batch.json
{
  "batch_id": "test_2024",
  "modesty_level": "modest",
  "urls": [
    "https://www.uniqlo.com/us/en/products/E479225-000",
    "https://www.asos.com/asos-design/product/12345",
    "https://www.nordstrom.com/browse/product/xyz"
  ]
}
```

### **🔄 System Refresh**
```bash
# Soft reset (keep learned patterns)
rm products.db markdown_cache.pkl

# Hard reset (start fresh)
rm *.db *.pkl

# Update system
git pull
pip install --upgrade -r requirements.txt
```

## ⚡ **Performance Optimization**

### **🎯 Speed Optimization**
- **Use markdown retailers** when possible (5x faster)
- **Enable caching** (65% hit rate)
- **Parallel processing** for batches
- **Smart timeouts** to avoid hangs

### **💰 Cost Optimization**  
- **Prefer markdown extraction** (75% cost savings)
- **Cache markdown results** (5-day expiry)
- **Smart fallback timing** (avoid unnecessary browser usage)
- **Batch processing** (reduced overhead)

### **🎪 Quality Optimization**
- **4-layer image processing** for maximum quality
- **Validation scoring** (reject low quality)
- **Retailer-specific patterns** for accuracy
- **Fallback detection** (avoid dummy data)

---

## 📈 **System Status: Production Ready v4.1**

✅ **All systems operational** with intelligent routing and comprehensive anti-bot protection  
✅ **External dependencies managed** (Browser Use auto-detection)  
✅ **Clean GitHub structure** with proper data protection  
✅ **Cost-optimized** dual engine architecture  

**Ready for 24/7 automated operation!** 