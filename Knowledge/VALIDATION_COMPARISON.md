# Validation Logic Comparison

## Current Validation (Less Strict)

```python
def _validate_extracted_data(self, data: Dict, retailer: str, url: str) -> List[str]:
    issues = []
    
    # Required fields
    if not data.get('title'):
        issues.append("Missing title")
    if not data.get('price'):
        issues.append("Missing price")
    if not data.get('image_urls') or len(data.get('image_urls', [])) == 0:
        issues.append("Missing images")  # ← REQUIRES ≥1 IMAGE
    
    # Price validation
    try:
        price = float(data.get('price', 0))
        if price <= 0:
            issues.append("Invalid price")
    except (ValueError, TypeError):
        issues.append("Price is not a number")
    
    return issues
```

**Criteria:**
- ✅ Title required
- ✅ Price required (must be positive number)
- ✅ **At least 1 image** required

---

## Old Architecture Validation (More Strict)

```python
def _validate_extracted_data(self, data: Dict[str, Any], retailer: str, url: str) -> List[str]:
    issues = []
    
    # Required fields validation
    required_fields = ["title", "price", "image_urls"]
    for field in required_fields:
        if not data.get(field):
            issues.append(f"Missing required field: {field}")
    
    # Title validation
    title = data.get("title", "")
    if title:
        if len(title) < 5 or len(title) > 200:
            issues.append(f"Title length suspicious: {len(title)} characters")
        if any(phrase in title.lower() for phrase in ["extracted by", "no title", "not found"]):
            issues.append("Title appears to be placeholder text")
    
    # Price validation  
    price = data.get("price", "")
    if price:
        if not re.search(r'[\$£€]?\d+([.,]\d{2})?', str(price)):
            issues.append(f"Invalid price format: '{price}'")
    
    # Image URLs validation
    image_urls = data.get("image_urls", [])
    if not image_urls:
        issues.append("No image URLs found")
    elif len(image_urls) < 2 and retailer != "hm":  # ← REQUIRES ≥2 IMAGES (except H&M)
        issues.append(f"Only {len(image_urls)} images found, expected multiple")
    
    return issues
```

**Criteria:**
- ✅ Title required (5-200 chars, no placeholders)
- ✅ Price required (regex format validation)
- ✅ **At least 2 images** required (except H&M gets ≥1)

---

## Comparison

| Validation | Current | Old Architecture | Difference |
|-----------|---------|------------------|------------|
| **Title** | Required | Required + length/content checks | Old is stricter |
| **Price** | Must be positive float | Must match regex pattern | Old is stricter |
| **Images** | ≥1 image | ≥2 images (except H&M) | **Old is stricter** |

---

## Recommendation

### **Option A: Keep Current (Looser)**
**Pros:**
- Allows more products through
- Some products legitimately have only 1 image
- Revolve products typically have 4+ images anyway

**Cons:**
- May allow lower-quality extractions
- Less validation catching errors

### **Option B: Revert to Old (Stricter)**
**Pros:**
- More rigorous validation
- Catches incomplete extractions
- Aligns with old working system

**Cons:**
- May fail valid products with only 1 image
- Stricter title/price validation may be unnecessary

### **Option C: Hybrid (Recommended)**
Use strict validation but with retailer exceptions:

```python
def _validate_extracted_data(self, data: Dict, retailer: str, url: str) -> List[str]:
    issues = []
    
    # Required fields
    if not data.get('title'):
        issues.append("Missing title")
    if not data.get('price'):
        issues.append("Missing price")
    if not data.get('image_urls') or len(data.get('image_urls', [])) == 0:
        issues.append("Missing images")
    
    # Title validation (like old)
    title = data.get("title", "")
    if title:
        if len(title) < 5 or len(title) > 200:
            issues.append(f"Title length suspicious: {len(title)} characters")
        if any(phrase in title.lower() for phrase in ["extracted by", "no title", "not found"]):
            issues.append("Title appears to be placeholder text")
    
    # Price validation
    try:
        price = float(data.get('price', 0))
        if price <= 0:
            issues.append("Invalid price")
    except (ValueError, TypeError):
        issues.append("Price is not a number")
    
    # Image URLs validation (stricter like old)
    image_urls = data.get("image_urls", [])
    if not image_urls:
        issues.append("No image URLs found")
    elif len(image_urls) < 2 and retailer not in ["hm", "uniqlo"]:  # ← REQUIRES ≥2 (except H&M, Uniqlo)
        issues.append(f"Only {len(image_urls)} images found, expected multiple")
    
    return issues
```

**Changes:**
- ✅ Add title length/content checks (like old)
- ✅ Require ≥2 images for most retailers (like old)
- ✅ Keep H&M exception, add Uniqlo exception
- ✅ Keep simpler price validation (float check works fine)

This gives us the best of both: strict validation with reasonable exceptions.

