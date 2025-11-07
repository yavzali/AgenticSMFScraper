# PerimeterX "Press & Hold" Verification - BREAKTHROUGH SOLUTION

**Date**: November 6, 2025  
**Retailer**: Anthropologie (PerimeterX verification)  
**Status**: ✅ **SOLVED**

---

## The Challenge

Anthropologie uses PerimeterX's sophisticated "Press & Hold" verification:
- Displays a button: "Press & Hold to confirm you are a human (and not a bot)"
- Button is a visible `<div class="px-captcha-error-button">`
- Contains a hidden `<iframe>` for verification logic
- Resistant to mouse-based automation

---

## What DIDN'T Work ❌

1. **Mouse coordinates with press & hold**
   - `page.mouse.move(x, y)` + `mouse.down()` + 10s wait + `mouse.up()`
   - Button visual never changed

2. **Dispatching mouse events to element**
   - `element.dispatch_event('mousedown')` + wait + `dispatch_event('mouseup')`
   - No response from verification system

3. **Human-like mouse movements**
   - Random starting positions
   - Gradual movements with delays
   - Still detected as bot

4. **Clicking iframe coordinates**
   - Attempting to click inside the hidden iframe
   - Iframe is `display: none` and not interactive

---

## The SOLUTION ✅

**Keyboard Navigation**: TAB + SPACE Hold

```python
# 1. Find the button element (Gemini Vision detects it first)
button_element = page.locator('div:has-text("Press & Hold")').first

# 2. Press TAB multiple times to focus the button
for i in range(10):
    await page.keyboard.press('Tab')
    await page.wait_for_timeout(300)

# 3. Hold SPACE for 10 seconds
await page.keyboard.down('Space')
await page.wait_for_timeout(10000)
await page.keyboard.up('Space')

# 4. Wait for page to load
await page.wait_for_timeout(3000)
```

**Result**: Verification BYPASSED! ✅

---

## Why It Works

1. **Keyboard events are harder to detect as bot behavior**
   - More similar to accessibility tools
   - Less fingerprinting possible than mouse patterns

2. **TAB navigation is standard browser behavior**
   - Natural focus progression
   - Expected by verification systems

3. **SPACE key triggers button activation**
   - Standard HTML button interaction
   - No coordinate detection needed

---

## Implementation in System

**File**: `Shared/playwright_agent.py`  
**Method**: `_gemini_handle_verification()`

**Flow**:
1. **Gemini Vision** detects "Press & Hold" verification visually
2. **DOM** finds the button element with selector
3. **Keyboard** performs TAB navigation + SPACE hold
4. **Success**: Product page loads

---

## Key Learnings

### ✅ DO:
- Use **keyboard navigation** for PerimeterX verification
- Combine **Gemini Vision** (detection) + **DOM** (element finding) + **Keyboard** (interaction)
- TAB at least 10 times to ensure button focus
- Hold SPACE for 10+ seconds
- Wait 3+ seconds after release for page load

### ❌ DON'T:
- Use mouse coordinates for PerimeterX
- Try to click the hidden iframe
- Dispatch synthetic mouse events
- Assume verification passes immediately

---

## Applicable To

- **Anthropologie** ✅ Confirmed working
- **Urban Outfitters** (likely uses same PerimeterX)
- **Free People** (likely uses same PerimeterX)
- Any site using PerimeterX "Press & Hold" verification

---

## Future Enhancements

1. **Auto-detect PerimeterX**: Check for `px-captcha` class names
2. **Adaptive TAB count**: Try 5 TABs first, then 10, then 15
3. **Variable hold duration**: Try 5s, 8s, 10s based on response
4. **Success detection**: Monitor for page title change or URL change

---

## Credit

Solution discovered through:
- User suggestion: "Let's look this up online"
- Web research: StackOverflow, ZenRows, Selenium documentation
- Key insight: Keyboard navigation bypasses mouse fingerprinting

---

**Status**: Production-ready, committed to main branch
**Commit**: d36d4d9 - "VICTORY: Bypassed PerimeterX Press & Hold with keyboard approach!"
