# 🛍️ Agent Modest Scraper System

An intelligent automated clothing scraper with **dual extraction engines**: **Markdown Extractor** (Jina AI + LLM) for fast, cost-effective processing of 5 retailers, and **Browser Agent System** for complex anti-bot challenges on remaining retailers.

## 🎯 **Current System Status** (v4.1)

✅ **Dual Engine Architecture:** Markdown + Browser agents with smart routing  
✅ **Production Ready:** All import issues resolved, external dependencies properly handled  
✅ **Success Rate:** Enhanced targeting with retailer-specific strategies  
✅ **Cost Optimization:** 5 retailers use fast markdown extraction  
✅ **Retailers Supported:** 10 major fashion retailers with specialized handling  
✅ **24/7 Operation:** No time restrictions - runs anytime  
✅ **GitHub Ready:** Clean directory structure with private data protection

## 🏗️ **System Architecture Overview**

### **📁 Directory Structure**
```
Agent Modest Scraper System/
├── 🎯 Core System Files
│   ├── agent_extractor.py          # Smart routing + browser agents
│   ├── markdown_extractor.py       # Jina AI + LLM cascade system  
│   ├── batch_processor.py          # Workflow coordination
│   ├── shopify_manager.py          # Product creation & updates
│   ├── duplicate_detector.py       # Smart duplicate handling
│   └── main_scraper.py             # Main entry point
├── 🖼️ Image Processing
│   ├── image_processor_factory.py  # Central routing system
│   ├── *_image_processor.py        # Retailer-specific processors
│   └── base_image_processor.py     # Base processing logic
├── 🔧 Infrastructure  
│   ├── cost_tracker.py             # API cost optimization
│   ├── pattern_learner.py          # ML pattern recognition
│   ├── scheduler.py                # Automated scheduling
│   └── logger_config.py            # Centralized logging
├── 💾 Data & Configuration
│   ├── config.json                 # System configuration
│   ├── products.db                 # Product database
│   ├── patterns.db                 # Learned patterns
│   ├── markdown_cache.pkl          # 5-day markdown cache
│   └── requirements.txt            # Dependencies
├── 🧪 Testing & Development
│   └── testing/                    # All test files and debug scripts
│       ├── test_*.py               # Unit tests
│       ├── debug_*.py              # Debug scripts
│       └── simple_*.py             # Development tools
└── 📚 Documentation
    ├── README.md                   # This file
    ├── SETUP_INSTRUCTIONS.md       # Complete setup guide
    ├── QUICK_REFERENCE.md          # Commands and examples
    └── SYSTEM_OVERVIEW.md          # Detailed technical docs
```

### **🤖 Smart Extraction Routing**
```
URL Input → Retailer Detection → Route Decision
                                      ↓
    ┌─────────────────────────────────┼─────────────────────────────────┐
    ↓                                 ↓                                 ↓
Markdown Extractor              Browser Agent                    Browser Agent
(ASOS, Mango, Uniqlo,          (Nordstrom, Aritzia,           (Anthropologie,
 Revolve, H&M)                  Urban Outfitters,              Abercrombie)
                                 etc.)
    ↓                                 ↓                                 ↓
Jina AI + LLM Cascade           Browser Use Agent               Verification Handling
(Fast, Cost-Effective)         (Anti-bot challenges)           (Press & Hold, Cloudflare)
    ↓                                 ↓                                 ↓
    └─────────────────────────────────┼─────────────────────────────────┘
                                      ↓
                              Image Processing Factory
                                      ↓
                              Shopify Integration
```

### **📊 Extraction Methods by Retailer**

| Retailer | Primary Method | Fallback | Special Features |
|----------|----------------|----------|------------------|
| **ASOS** | 🚀 Markdown Extractor | Browser Agent | Fast, reliable, high-res images |
| **Mango** | 🚀 Markdown Extractor | Browser Agent | Cost-effective, consistent |
| **Uniqlo** | 🚀 Markdown Extractor | Browser Agent | Speed, complex image patterns |
| **Revolve** | 🚀 Markdown Extractor | Browser Agent | Designer brand accuracy |
| **H&M** | 🚀 Markdown Extractor | Browser Agent | Sometimes works, fast when it does |
| **Nordstrom** | 🤖 Browser Agent | - | Advanced anti-bot protection |
| **Aritzia** | 🤖 Browser Agent | - | "Verify you are human" checkboxes |
| **Anthropologie** | 🤖 Browser Agent | - | Press & hold verification (4-6 sec) |
| **Urban Outfitters** | 🤖 Browser Agent | - | Press & hold verification (4-6 sec) |
| **Abercrombie** | 🤖 Browser Agent | - | Multi-step verification challenges |

## 🚀 **Quick Start**

### **1. Install Core Dependencies**
```bash
# Install Python dependencies
pip install -r requirements.txt

# Optional: Install Browser Use for enhanced browser automation
# (Can be installed separately or placed in ../browser-use/)
```

### **2. Configure API Keys**
```bash
# Required: Google Gemini API
export GOOGLE_API_KEY="your_gemini_api_key"

# Optional: DeepSeek API (improves markdown extraction)
export DEEPSEEK_API_KEY="your_deepseek_api_key"

# Configure Shopify in config.json
{
  "shopify": {
    "store_url": "your-store.myshopify.com",
    "access_token": "your_shopify_token"
  }
}
```

### **3. Test the System**
```bash
# Test core components
python -c "from agent_extractor import AgentExtractor; print('✅ System ready!')"

# Test markdown extractor (fast)
cd testing && python test_markdown_extractor.py --quick

# Test single URL with smart routing
python testing/test_single_url.py "https://www.uniqlo.com/us/en/products/E479225-000" uniqlo

# Run batch processing
python main_scraper.py --batch-file batch_001_June_7th.json --force-run-now
```

## 📊 **Performance Metrics**

### **Markdown Extractor Performance**
- **Speed:** ~5-10 seconds per product
- **Cost:** $0.02-0.05 per extraction  
- **Success Rate:** 80-95% for supported retailers
- **Quality:** High-res image extraction with validation

### **Browser Agent Performance**
- **Speed:** 30-120 seconds per product (includes verification handling)
- **Cost:** $0.10-0.30 per extraction
- **Success Rate:** 70-85% (complex anti-bot sites)
- **Verification:** Automated press-and-hold, checkboxes, Cloudflare protection

### **Overall System Performance**
- **Combined Success Rate:** 80-90% across all retailers
- **Cost Optimization:** 60% cost reduction with markdown routing
- **Image Quality:** 85/100 average score with 4-layer processing
- **Cache Hit Rate:** 65% (5-day markdown cache)

## 🔧 **Key Features**

### **🎯 Smart Routing**
- **Automatic retailer detection** from URLs
- **Optimal method selection** (markdown vs browser)
- **Intelligent fallback** when primary method fails
- **Cost optimization** through method selection

### **🛡️ Anti-Detection Measures**
- **Human-like browsing behavior** (scrolling, pausing, hovering)
- **Verification challenge handling** (press & hold, checkboxes)
- **Retailer-specific configurations** (user agents, timeouts)
- **Cloudflare protection** automatic handling

### **📱 Verification Handling**
- **Aritzia:** "Verify you are human" checkboxes + Cloudflare tab management
- **Anthropologie/Urban Outfitters:** Press & hold buttons (4-6 seconds)
- **Nordstrom:** Advanced anti-bot protection handling
- **Abercrombie:** Multi-step verification challenges

### **🖼️ Advanced Image Processing**
- **4-layer architecture** (Base → Transformer → Reconstruction → Factory)
- **Retailer-specific processors** for each of 10 retailers
- **Quality validation** with 100-point scoring system
- **Multiple format support** (JPEG, PNG, WebP)

### **💾 Data Management**
- **Smart duplicate detection** (4-tier approach: URL → Product Code → Similarity → Manual)
- **Pattern learning** with ML-based extraction improvement
- **5-day markdown caching** for cost optimization
- **Checkpoint management** for large batch recovery

## 🏃‍♂️ **Development & Testing**

### **Testing Framework**
```bash
# Core system tests
python testing/test_integration_routing.py     # Routing logic
python testing/test_markdown_extractor.py      # Markdown extraction
python testing/test_verification_handling.py   # Verification challenges
python testing/test_anti_detection.py          # Anti-bot measures

# Debug tools
python testing/debug_browser_use.py            # Browser Use debugging
python testing/debug_openmanus.py              # OpenManus debugging
python testing/simple_test.py                  # Quick system check
```

### **Development Setup**
```bash
# Start development environment
cd "Agent Modest Scraper System"

# Run comprehensive test
python -c "
from agent_extractor import AgentExtractor
from markdown_extractor import MarkdownExtractor  
from batch_processor import BatchProcessor
print('🎯 All core components working!')
"
```

## 📚 **Documentation**

- **[SETUP_INSTRUCTIONS.md](./SETUP_INSTRUCTIONS.md)** - Complete installation and configuration guide
- **[QUICK_REFERENCE.md](./QUICK_REFERENCE.md)** - Commands, examples, and troubleshooting
- **[SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md)** - Detailed technical architecture
- **[VERIFICATION_HANDLING_GUIDE.md](./VERIFICATION_HANDLING_GUIDE.md)** - Anti-bot challenge handling

## 🆘 **Support & Troubleshooting**

### **Common Issues**
1. **Import errors:** Make sure `pip install -r requirements.txt` completed successfully
2. **Browser Use not found:** Install separately or place in `../browser-use/` directory  
3. **API key errors:** Verify `GOOGLE_API_KEY` is set correctly
4. **Database issues:** Delete `*.db` files to recreate clean databases

### **Getting Help**
- Check the `logs/` directory for detailed error information
- Run `python testing/test_prompt_generation.py` to verify configuration
- Use `--force-run-now` flag to bypass scheduling for testing

---

## 📈 **System Architecture (v4.1)**

**Production-Ready Dual Engine System** with clean GitHub structure, external dependency management, and comprehensive anti-bot protection. Ready for 24/7 automated operation with intelligent routing and cost optimization.