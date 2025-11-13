# Anthropologie Catalog Extraction Fix

**Date**: November 13, 2024  
**Issue**: Baseline scanner only extracting URLs, no titles or prices  
**Status**: ✅ RESOLVED  
**Propagation**: ✅ AUTO-PROPAGATED to all workflows

---

## **Problem**

Catalog baseline scan extracted 71 products but:
- ❌ 0% had titles (all "MISSING")
- ❌ 100% had placeholder prices ($1000.00)
- ✅ 100% had URLs

**Root Cause**: Generic parent-traversal DOM extraction wasn't finding Anthropologie's specific HTML structure.

---

## **Solution: Specialized Anthropologie Extractor**

Created `_extract_anthropologie_from_containers()` method in `PatchrightCatalogExtractor` class, similar to the Revolve specialized extractor.

### **Key Changes**

#### **1. PWA Container Selector**
```python
# ❌ OLD: Generic selector (found 0 containers)
containers = await self.page.query_selector_all('article.product-tile')

# ✅ NEW: Anthropologie PWA selector
containers = await self.page.query_selector_all('.o-pwa-product-tile')
```

**Why**: Anthropologie uses Progressive Web App (PWA) structure with different class naming conventions.

#### **2. PWA Title Selector**
```python
# ✅ Primary: PWA-specific heading
title_el = await container.query_selector('.o-pwa-product-tile__heading')

# Fallbacks:
# - img[alt]
# - a[aria-label]
```

#### **3. PWA Price Selector**
```python
price_selectors = [
    '.c-pwa-product-price__current',  # Anthropologie PWA (primary)
    '.s-pwa-product-price__current',  # Anthropologie PWA (alternative)
    # ... generic fallbacks
]
```

#### **4. textContent vs inner_text**
```python
# ❌ OLD: inner_text() returned entire page content
title_text = await title_el.inner_text()
# Result: "Skip to main content... [entire page text]"

# ✅ NEW: textContent gets ONLY element's text
title_text = await title_el.evaluate('el => el.textContent')
# Result: "The Bettina Velvet Tiered Mini Shirt Dress by Maeve"
```

**Critical Fix**: `inner_text()` was traversing the entire DOM tree, returning all page content. `textContent` via JS evaluation gets only the element's direct text.

---

## **Implementation**

### **File Modified**
`Extraction/Patchright/patchright_catalog_extractor.py`

### **Method Added**
```python
async def _extract_anthropologie_from_containers(
    self, 
    retailer: str, 
    strategy: Dict
) -> List[Dict]:
    """
    Specialized extraction for Anthropologie
    Uses PWA structure: .o-pwa-product-tile containers
    """
    containers = await self.page.query_selector_all('.o-pwa-product-tile')
    
    for container in containers[:150]:
        # Extract URL
        url = await container.query_selector('a[href*="/shop/"]')
        
        # Extract title (PWA heading)
        title_el = await container.query_selector('.o-pwa-product-tile__heading')
        title_text = await title_el.evaluate('el => el.textContent')
        
        # Extract price (PWA price)
        price_el = await container.query_selector('.c-pwa-product-price__current')
        price_text = await price_el.evaluate('el => el.textContent')
        
        # ... validation and deduplication
```

### **Integration Point**
```python
async def _extract_catalog_product_links_from_dom(self, retailer, strategy):
    # ... 
    if retailer.lower() == 'anthropologie':
        return await self._extract_anthropologie_from_containers(retailer, strategy)
    # ...
```

---

## **Results**

### **Baseline #22 (Final)**
- **Products**: 71
- **URLs**: 71/71 (100%) ✅
- **Titles**: 71/71 (100%) ✅
- **Prices**: 71/71 (100%) ✅

### **Sample Products**
1. The Bettina Velvet Tiered Mini Shirt Dress by Maeve - $168
2. The Caroline Tie-Neck Mini Dress by Maeve - $198
3. Maeve Cap-Sleeve V-Neck Smocked Midi Dress - $158
4. Lovaan Adeline Linen-Silk Puff-Sleeve Midi Dress - $575

### **Quality Metrics**
- ✅ All products have real titles (not "MISSING")
- ✅ All products have real prices (not $1000 placeholder)
- ✅ Price range: $158-$575 (reasonable for Anthropologie)
- ✅ No duplicates in baseline

---

## **Automatic Propagation**

### **Shared Code Path**
Both workflows use the same `PatchrightCatalogExtractor` class:

```
catalog_baseline_scanner.py → PatchrightCatalogExtractor.extract_catalog()
                                       ↓
                          _extract_catalog_product_links_from_dom()
                                       ↓
                          _extract_anthropologie_from_containers()

catalog_monitor.py → PatchrightCatalogExtractor.extract_catalog()
                                       ↓
                          _extract_catalog_product_links_from_dom()
                                       ↓
                          _extract_anthropologie_from_containers()
```

### **Workflows Benefiting**
✅ **Catalog Baseline Scanner** - Tested, 100% quality  
✅ **Catalog Monitor** - Auto-propagated (same extractor)

**No additional code changes needed!**

---

## **Lessons Learned**

### **1. Retailer-Specific Structures**
- Don't assume generic selectors will work for all retailers
- Each retailer may have unique HTML structures (PWA, SPA, etc.)
- Create specialized extractors when generic approach fails

### **2. textContent vs inner_text**
- `inner_text()` can traverse entire DOM (including parent elements)
- `textContent` via JS evaluation is more reliable
- Always scope to specific elements/containers

### **3. PWA (Progressive Web App) Structures**
- Modern retailers increasingly use PWA frameworks
- PWA class naming conventions differ from traditional HTML
- Look for patterns like `o-pwa-*`, `c-pwa-*`, `s-pwa-*`

### **4. Testing Methodology**
- Test extraction on actual catalog pages
- Verify database contents (not just logs)
- Check for entire-page-content bug in titles

### **5. Shared Extractor Benefits**
- Fix once, benefit everywhere
- Both baseline and monitor workflows updated
- Reduces maintenance burden

---

## **Related Fixes**

### **Revolve Catalog Extraction**
- Similar issue: Generic extraction didn't work
- Solution: `_extract_revolve_from_containers()` method
- Used `textContent` to avoid entire-page extraction
- File: `Knowledge/REVOLVE_EXTRACTION_FIX_SUMMARY.md`

### **DOM-First Configuration**
- All Patchright retailers now use `dom_first` for catalogs
- Configuration properly checked before Gemini fallback
- File: `Knowledge/DOM_FIRST_EXTRACTION_IMPLEMENTATION.md`

---

## **Testing Checklist**

When adding new Patchright retailers for catalog extraction:

- [ ] Identify product container class (inspect HTML)
- [ ] Identify title selector (heading, img[alt], aria-label)
- [ ] Identify price selector (look for price classes)
- [ ] Use `textContent` (not `inner_text`) for extraction
- [ ] Test on actual catalog page (not just product pages)
- [ ] Verify database contents (check titles aren't "MISSING")
- [ ] Verify prices aren't placeholder values ($1000)
- [ ] Check for entire-page-content in extracted titles
- [ ] Test deduplication (URL normalization)
- [ ] Verify extraction quality logs (X/X have titles, Y/Y have prices)

---

## **Future Enhancements**

### **Potential Improvements**
1. **Generic PWA Detector**: Auto-detect PWA structures
2. **Fallback Chain**: Try multiple selectors automatically
3. **Extraction Validation**: Warn if titles > 200 chars (likely entire page)
4. **Selector Library**: Build library of known retailer selectors

### **Other Retailers to Check**
- Urban Outfitters (also PWA?)
- Other Anthropologie brands (BHLDN, etc.)
- Any retailer with 0% title extraction

---

## **Commits**

1. `8caa60d` - "FIX: Anthropologie baseline extraction - add specialized container extractor"
2. `b768ebb` - "FIX: Anthropologie PWA selectors for baseline extraction"
3. `3185408` - "FIX: Use textContent instead of inner_text for Anthropologie"

---

## **Status**

✅ **Issue**: RESOLVED  
✅ **Testing**: COMPLETE (71 products, 100% quality)  
✅ **Propagation**: AUTOMATIC (shared extractor class)  
✅ **Documentation**: COMPLETE  

**Ready for production catalog monitoring!** 🚀

