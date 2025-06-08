# 🚀 **Quick Reference Guide**

## 🎯 **Dual Engine Architecture (v4.0)**

### **🚀 Markdown Extraction (5 Retailers)**
- **ASOS, Mango, Uniqlo, Revolve, H&M**
- **Method:** Jina AI + DeepSeek V3/Gemini Flash 2.0
- **Speed:** 5-10 seconds per product
- **Cost:** $0.02-0.05 per extraction
- **Success Rate:** 80-95%

### **🤖 Browser Agents (5 Retailers)**
- **Nordstrom, Aritzia, Anthropologie, Urban Outfitters, Abercrombie**
- **Method:** Browser Use + OpenManus with verification handling
- **Speed:** 30-120 seconds per product
- **Cost:** $0.10-0.30 per extraction
- **Success Rate:** 70-85%

## 📁 **Core System Files**

### **🚀 Markdown Extraction Engine**
- `markdown_extractor.py` - Jina AI + LLM cascade (690 lines)
- `test_markdown_extractor.py` - Comprehensive validation (442 lines)
- `markdown_cache.pkl` - 5-day cache system (auto-managed)

### **🤖 Browser Agent System**
- `agent_extractor.py` - Smart routing + verification (1512 lines)
- `test_verification_handling.py` - Anti-bot testing (231 lines)
- `test_integration_routing.py` - Routing validation (105 lines)
- `VERIFICATION_HANDLING_GUIDE.md` - Documentation (274 lines)

### **🖼️ Image Processing Factory**
- `image_processor_factory.py` - Central routing (114 lines)
- `base_image_processor.py` - 4-layer architecture (317 lines)
- `uniqlo_image_processor.py` - Complex reconstruction (181 lines)
- `aritzia_image_processor.py` - Resolution enhancement (108 lines)
- `simple_transform_image_processor.py` - 8 retailers transformation (176 lines)

### **💼 Business Logic**
- `batch_processor.py` - Workflow orchestration (440 lines)
- `shopify_manager.py` - Product creation (529 lines)
- `url_processor.py` - Retailer detection (261 lines)
- `cost_tracker.py` - API optimization (322 lines)

## ⚡ **Quick Commands**

### **🧪 Testing Commands**
```bash
# Test markdown extraction system
python test_markdown_extractor.py

# Test routing logic (markdown vs browser)
python test_integration_routing.py

# Test verification handling for anti-bot sites
python test_verification_handling.py

# Test single URL with automatic routing
python test_single_url.py "https://www.asos.com/product/..." asos

# Test anti-detection measures
python test_anti_detection.py
```

### **🔍 System Validation**
```bash
# Verify all imports work
python -c "from agent_extractor import AgentExtractor; from markdown_extractor import MarkdownExtractor; print('✅ All systems operational')"

# Check markdown extractor setup
python -c "from markdown_extractor import MARKDOWN_RETAILERS; print(f'Markdown retailers: {MARKDOWN_RETAILERS}')"

# Test browser agent initialization
python -c "from agent_extractor import AgentExtractor; agent = AgentExtractor(); print('✅ Browser agents ready')"
```

### **📊 Monitoring Commands**
```bash
# View main extraction logs
tail -f logs/scraper_main.log

# Monitor markdown extractor activity
tail -f logs/scraper_main.log | grep "markdown"

# Track verification challenges
tail -f logs/scraper_main.log | grep "verification"

# Monitor routing decisions
tail -f logs/scraper_main.log | grep "routing"

# Check cost optimization
tail -f logs/performance.log | grep "cost"
```

## 🛍️ **Retailer Routing Matrix**

### **🚀 Markdown Extraction**
| Retailer | Success Rate | Speed | Cost | Fallback |
|----------|--------------|-------|------|----------|
| **ASOS** | 90-95% | 5-8s | $0.02-0.05 | Browser Agent |
| **Mango** | 85-90% | 6-10s | $0.02-0.05 | Browser Agent |
| **Uniqlo** | 80-90% | 5-8s | $0.02-0.05 | Browser Agent |
| **Revolve** | 85-95% | 6-10s | $0.02-0.05 | Browser Agent |
| **H&M** | 60-80% | 5-8s | $0.02-0.05 | Browser Agent |

### **🤖 Browser Agent Extraction**
| Retailer | Verification | Speed | Cost | Success Rate |
|----------|--------------|-------|------|--------------|
| **Nordstrom** | Press & Hold | 60-120s | $0.15-0.30 | 70-80% |
| **Aritzia** | Checkbox + Tabs | 30-90s | $0.10-0.25 | 80-90% |
| **Anthropologie** | Press & Hold | 45-120s | $0.15-0.30 | 75-85% |
| **Urban Outfitters** | Press & Hold | 45-120s | $0.15-0.30 | 70-80% |
| **Abercrombie** | Multi-Step | 45-120s | $0.15-0.30 | 70-80% |

## 🔧 **Key Features**

### **✅ Smart Routing**
- **Automatic Detection:** URL → Retailer → Method selection
- **Fallback Hierarchy:** Markdown → Browser → Manual
- **Quality Validation:** Rigorous quality scoring (0-10 scale)
- **Cost Optimization:** 60% cost reduction with markdown routing

### **✅ Verification Handling**
- **Press & Hold:** 4-6 second duration for human simulation
- **Checkbox Clicking:** Immediate response for Cloudflare
- **Tab Management:** Automatic cleanup of verification tabs
- **Retry Logic:** Intelligent retry with timeout handling

### **✅ Quality Assurance**
- **Extraction Validation:** Required fields + content verification
- **Fallback Detection:** Identify dummy/placeholder data
- **Processing Time:** Real extraction vs timeout validation
- **Image Enhancement:** High-res pattern detection and quality scoring

## 📊 **Current Status**

### **✅ Production Ready (v4.0)**
- **Dual Engine Architecture:** Markdown + Browser agents operational
- **10 Retailers Supported:** 5 markdown + 5 browser agent
- **Comprehensive Testing:** 5 test suites covering all components
- **Documentation:** Complete guides and API references

### **✅ Performance Metrics**
- **Combined Success Rate:** 80-90%
- **Cost Reduction:** 60% savings with smart routing
- **Processing Speed:** 5-120 seconds depending on method
- **Quality Standards:** 85/100 average image quality score

### **✅ Recent Major Updates (January 2025)**
- **🚀 Markdown Extractor:** Jina AI + LLM cascade implementation
- **🤖 Browser Use Integration:** Fixed initialization and verification
- **🧪 Test Framework:** Comprehensive validation and quality assurance
- **📚 Documentation:** Complete overhaul and consolidation
- **🔧 Configuration:** Enhanced retailer-specific settings

## 🛠️ **Development Setup**

### **API Keys Required**
```bash
# Required for all operations
export GOOGLE_API_KEY="your_gemini_api_key"

# Optional for enhanced markdown extraction
export DEEPSEEK_API_KEY="your_deepseek_api_key"
```

### **Quick Development Test**
```bash
# Install dependencies
pip install -r requirements.txt

# Test core functionality
python test_integration_routing.py

# Test markdown extraction
python test_markdown_extractor.py

# Verify browser agents
python test_verification_handling.py
```

## 📚 **Documentation Hierarchy**

### **📖 Main Documentation**
- **`README.md`** - System overview and quick start
- **`SYSTEM_OVERVIEW.md`** - Complete technical architecture
- **`QUICK_REFERENCE.md`** - This command reference guide

### **🔧 Setup & Configuration**
- **`SETUP_INSTRUCTIONS.md`** - Detailed installation guide
- **`VERIFICATION_HANDLING_GUIDE.md`** - Anti-bot documentation
- **`config.json`** - System configuration

### **🏗️ Architecture Documentation**
- **`PHASE_3_DOCUMENTATION.md`** - Image processing architecture
- **`PHASE_1_2_IMPLEMENTATION_SUMMARY.md`** - Historical reference

---

**🎯 System Status:** Production-ready dual engine architecture with 60% cost reduction and 80-90% success rates across 10 major fashion retailers.

**⚡ Quick Start:** `python test_integration_routing.py` to validate full system functionality. 