# Revolve CDN DNS Resolution Failure

**Date**: November 13, 2024  
**Priority**: Medium (P2) - Could indicate larger CDN/network issue  
**Status**: Under observation

---

## **Issue**

DNS resolution fails for Revolve's image CDN:
```
curl: (6) Could not resolve host: is4.revolveimages.com
```

**Affected Domain**: `is4.revolveimages.com`  
**Error Type**: DNS resolution failure (nodename nor servname provided, or not known)

---

## **Context**

**When Discovered**: During Revolve Tops catalog monitor verification run (Nov 13, 03:03 UTC)

**What Happened**:
1. System extracted 1 new product: L'AGENCE Dani Blouse
2. Image URLs correctly formatted (transformation logic working)
3. All 4 image downloads failed with DNS error
4. Product uploaded to Shopify with 0 images

**Previous Run (15 minutes earlier)**:
- ✅ 14 products successfully downloaded images
- ✅ Same URL pattern (`is4.revolveimages.com/images/p4/n/dp/...`)
- ✅ No DNS issues

---

## **Evidence URLs Are Correct**

**Extracted URLs**:
```
https://is4.revolveimages.com/images/p4/n/dp/LAGR_WS437_V1.jpg
https://is4.revolveimages.com/images/p4/n/dp/LAGR_WS437_V2.jpg
https://is4.revolveimages.com/images/p4/n/dp/LAGR_WS437_V3.jpg
https://is4.revolveimages.com/images/p4/n/dp/LAGR_WS437_V4.jpg
```

**URL Pattern Analysis**:
- ✅ Domain: `is4.revolveimages.com` (standard Revolve CDN)
- ✅ Path: `/images/p4/n/dp/` (correct structure)
- ✅ Filename: `LAGR_WS437_V{1-4}.jpg` (product code + angle suffix)
- ✅ Suffixes: `_V1`, `_V2`, `_V3`, `_V4` (preserved correctly)

**Conclusion**: URL transformation logic is working correctly. This is NOT a code bug.

---

## **Potential Root Causes**

### 1. Temporary DNS Outage (Most Likely)
- Revolve's CDN DNS temporarily unavailable
- Will resolve itself
- **Action**: Monitor future runs

### 2. DNS Cache Issue
- Local DNS cache corrupted
- Stale DNS entries
- **Action**: Flush DNS cache if persists

### 3. Revolve CDN Infrastructure Change
- Revolve migrating CDN providers
- Subdomain changes (`is4` → different subdomain)
- Old URLs still work for existing products
- New products getting different CDN domains
- **Action**: Check if future products use different domains

### 4. Network/ISP Blocking
- ISP blocking Revolve's CDN
- Firewall/VPN interfering
- **Action**: Test from different network

### 5. Rate Limiting at DNS Level
- Too many DNS lookups to `*.revolveimages.com`
- CDN provider blocking automated traffic
- **Action**: Implement DNS caching or use connection pooling

---

## **Why This Could Be a Bigger Bug**

**Concern**: If Revolve is changing CDN infrastructure, we might:
1. ❌ Fail to download images for all new products
2. ❌ Miss CDN domain pattern changes
3. ❌ Need to update image URL extraction logic

**Evidence Against**:
- ✅ Previous 14 products used same domain and worked
- ✅ Only 15 minutes between successful/failed runs
- ✅ Single subdomain failure (is4) suggests temporary issue

**Evidence For**:
- ⚠️ DNS failure, not HTTP failure (domain doesn't exist)
- ⚠️ Main site (`www.revolve.com`) also had HTTP/2 errors
- ⚠️ Could indicate broader Revolve infrastructure issues

---

## **Monitoring Plan**

### Short-term (Next 24 hours):
1. ✅ Run Revolve catalog monitor again
2. ✅ Check if DNS resolves
3. ✅ Verify images download successfully
4. ⚠️ If still failing → escalate priority to P1

### Medium-term (Next week):
1. Track which CDN subdomains are used:
   - `is4.revolveimages.com`
   - `is3.revolveimages.com`
   - Other patterns?
2. Check if different products use different subdomains
3. Implement CDN domain monitoring

### Long-term:
1. Add DNS resolution health checks
2. Implement retry logic with exponential backoff
3. Add fallback CDN domain patterns
4. Monitor Revolve's image URL patterns for changes

---

## **Current Status**

**Impact**: 
- 1 product uploaded with 0 images
- Product in assessment queue (can be re-extracted)
- Not blocking workflow

**Next Steps**:
1. Monitor next Revolve catalog run
2. Re-extract the affected product if DNS resolves
3. Escalate if issue persists beyond 24 hours

---

## **Related Issues**
- Previous image transformation bug (commit bb65469) - RESOLVED
- 25 Revolve dresses with 0 images (transformation bug) - RESOLVED
- This issue: Different root cause (network, not code)

---

## **Product Affected**

**Shopify ID**: 14836238647666  
**Title**: L'AGENCE Dani Blouse in Black  
**URL**: https://www.revolve.com/lagence-dani-blouse-in-black/dp/LAGR-WS437/  
**Assessment Queue ID**: 163  
**Status**: In assessment queue, uploaded to Shopify with 0 images

**Re-extraction**: Can manually re-run single product extraction when DNS resolves.


