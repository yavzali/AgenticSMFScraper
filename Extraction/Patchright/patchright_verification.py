"""
Patchright Tower - Verification Handler
Handle anti-bot verification challenges (PerimeterX, Cloudflare)

Extracted from: Shared/playwright_agent.py (verification logic, lines 895-1256)
Target: <600 lines
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../Shared"))

import asyncio
import json
import io
import random
from typing import Dict, Optional
from datetime import datetime
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import logging

from logger_config import setup_logging

logger = setup_logging(__name__)


class PatchrightVerificationHandler:
    """
    Handle anti-bot verification challenges
    
    Supports:
    - PerimeterX "Press & Hold" (Anthropologie, Urban Outfitters)
    - Cloudflare challenges (Aritzia)
    - Generic popup dismissal
    - Gemini Vision for visual detection
    
    Key Breakthrough: Keyboard approach (TAB + SPACE) bypasses PerimeterX
    """
    
    def __init__(self, page, config: Dict = None):
        """
        Args:
            page: Patchright Page object
            config: System configuration
        """
        self.page = page
        self.config = config or {}
        
        # Load environment
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.join(script_dir, '../..')
        env_path = os.path.join(project_root, '.env')
        load_dotenv(env_path, override=True)
        
        # Setup Gemini for visual verification detection
        self._setup_gemini()
        
        logger.info("✅ Patchright Verification Handler initialized")
    
    def _setup_gemini(self):
        """Initialize Gemini Vision for verification detection"""
        try:
            google_api_key = os.getenv("GOOGLE_API_KEY") or \
                           self.config.get("llm_providers", {}).get("google", {}).get("api_key")
            
            if not google_api_key:
                raise ValueError("Google API key not found")
            
            genai.configure(api_key=google_api_key)
            logger.info("✅ Gemini Vision initialized for verification")
        except Exception as e:
            logger.error(f"Failed to setup Gemini: {e}")
            raise
    
    async def handle_verification_challenges(self, strategy: Dict) -> bool:
        """
        Main verification handler
        
        Process:
        1. Dismiss popups
        2. Detect verification page
        3. Use Gemini Vision to locate button
        4. Execute keyboard approach (TAB + SPACE) for PerimeterX
        5. Fallback to DOM selectors if Gemini fails
        
        Args:
            strategy: Dict with retailer, domain, special_notes
            
        Returns:
            True if verification handled successfully
        """
        
        # Step 1: Dismiss popups
        await self._dismiss_popups()
        
        # Step 2: Check if we're on a verification page
        page_content = await self.page.content()
        is_verification_page = any(
            keyword in page_content.lower() 
            for keyword in ['press and hold', 'press & hold', 'verification', 
                          'captcha', 'challenge', 'cloudflare']
        )
        
        if is_verification_page:
            logger.info("🛡️ Verification page detected - using Gemini Vision...")
            
            # Save HTML for debugging
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                html_file = f"/tmp/{strategy.get('retailer', 'unknown')}_verification_{timestamp}.html"
                with open(html_file, 'w') as f:
                    f.write(page_content)
                logger.info(f"📝 Saved verification HTML to {html_file}")
            except Exception as e:
                logger.debug(f"Could not save HTML: {e}")
            
            # Step 3: Use Gemini Vision
            verification_handled = await self._gemini_handle_verification()
            logger.info(f"🔍 Gemini verification result: {verification_handled}")
            
            if verification_handled:
                logger.info("✅ Gemini Vision successfully handled verification!")
                # Wait for page to load
                try:
                    logger.info("⏱️ Waiting for page to load...")
                    await self.page.wait_for_load_state('networkidle', timeout=15000)
                    logger.info("✅ Page loaded!")
                except:
                    logger.info("⏱️ Timeout waiting for networkidle, proceeding anyway...")
                return True
        
        # Step 4: Fallback to DOM selectors
        verification_selectors = [
            # Press & Hold specific
            'button:has-text("Press & Hold")',
            'button:has-text("Press and Hold")',
            'button:has-text("PRESS & HOLD")',
            '[class*="press"][class*="hold"]',
            '[id*="press-hold"]',
            '[data-testid="press-hold-button"]',
            # Generic verification
            'button:has-text("I am human")',
            'button:has-text("Verify")',
            'button:has-text("Continue")',
            # Captcha/Cloudflare
            '.captcha-container',
            '.cloudflare-browser-verification',
            '#challenge-form',
            'iframe[src*="challenges.cloudflare.com"]',
            '[aria-label*="verification"]',
            '[aria-label*="challenge"]'
        ]
        
        # Add aggressive fallbacks if confirmed verification page
        if is_verification_page:
            verification_selectors.extend([
                'button[type="button"]',
                'button',
                'div[role="button"]'
            ])
        
        for selector in verification_selectors:
            try:
                logger.debug(f"🔍 Checking selector: {selector}")
                element = self.page.locator(selector).first
                if await element.is_visible(timeout=2000):
                    logger.info(f"✅ Found verification element: {selector}")
                    
                    # Determine if press & hold
                    is_press_hold = (
                        "Press & Hold" in selector or 
                        "press-hold" in selector or 
                        "press" in selector.lower() or 
                        (is_verification_page and selector in ['button', 'button[type="button"]'])
                    )
                    
                    if is_press_hold:
                        logger.info("🖱️ Performing press & hold (8s)...")
                        try:
                            box = await element.bounding_box()
                            if box:
                                # Move to element center and hold
                                await self.page.mouse.move(
                                    box['x'] + box['width']/2, 
                                    box['y'] + box['height']/2
                                )
                                await self.page.mouse.down()
                                await self.page.wait_for_timeout(8000)
                                await self.page.mouse.up()
                                logger.info("✅ Press & hold completed (8s)")
                            else:
                                # Fallback
                                await element.hover()
                                await self.page.wait_for_timeout(500)
                                await element.click()
                                await self.page.wait_for_timeout(8000)
                                logger.info("✅ Press & hold fallback completed")
                        except Exception as e:
                            logger.warning(f"Press & hold failed: {e}")
                    else:
                        # Regular click
                        await element.click()
                        logger.info(f"✅ Clicked verification element: {selector}")
                    
                    await self.page.wait_for_timeout(3000)
                    return True
                    
            except Exception as e:
                logger.debug(f"Selector check failed for {selector}: {e}")
                continue
        
        logger.debug("No verification challenges detected")
        return False
    
    async def _gemini_handle_verification(self) -> bool:
        """
        Use Gemini Vision to detect and handle verification
        
        Returns:
            True if verification was found and handled
        """
        try:
            # Take screenshot
            screenshot_bytes = await self.page.screenshot(type='png')
            image = Image.open(io.BytesIO(screenshot_bytes))
            
            # Get viewport
            viewport = self.page.viewport_size
            if not viewport:
                viewport = {'width': 1920, 'height': 1080}
                logger.debug("Using default viewport")
            
            # Build Gemini prompt
            prompt = """Analyze this page for verification challenges.

LOOK FOR:
1. "Press & Hold" buttons
2. "I am human" checkboxes
3. CAPTCHA challenges
4. Verification buttons
5. "Continue" or "Verify" buttons

If you find a verification element:
- Report its TYPE (press_hold, checkbox, button, captcha)
- Report its POSITION as percentage (0-100) from top-left
  Format: {"x_percent": 50, "y_percent": 30}
- Report the TEXT on the button

Return ONLY valid JSON:
{
    "verification_found": true/false,
    "type": "press_hold | checkbox | button | captcha | none",
    "text": "exact text on button",
    "position": {"x_percent": 50, "y_percent": 30},
    "requires_hold": true/false,
    "hold_duration_seconds": 5
}

If NO verification: {"verification_found": false}"""
            
            # Call Gemini
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            response = model.generate_content([prompt, image])
            
            logger.debug(f"🎯 Gemini raw response: {response.text if response else 'None'}")
            
            # Parse response
            response_text = response.text.strip()
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()
            
            result = json.loads(response_text)
            
            if not result.get('verification_found'):
                logger.debug("Gemini: No verification detected")
                return False
            
            logger.info(f"🎯 Gemini found {result['type']}: '{result.get('text', 'unknown')}'")
            logger.info(f"📊 Details: {json.dumps(result, indent=2)}")
            
            # Check iframes first
            frames = self.page.frames
            if len(frames) > 1:
                logger.info(f"🖼️ Found {len(frames)} frames - checking...")
                
                for i, frame in enumerate(frames):
                    if frame == self.page.main_frame:
                        continue
                    
                    try:
                        frame_element = await self.page.query_selector(f'iframe:nth-of-type({i})')
                        if frame_element:
                            frame_screenshot = await frame_element.screenshot(type='png')
                            frame_image = Image.open(io.BytesIO(frame_screenshot))
                            
                            iframe_prompt = """Is this iframe the verification challenge?

Return ONLY valid JSON:
{
    "is_verification": true/false,
    "button_position": {"x_percent": 50, "y_percent": 50}
}"""
                            
                            iframe_response = model.generate_content([iframe_prompt, frame_image])
                            iframe_text = iframe_response.text.strip()
                            
                            if '```json' in iframe_text:
                                iframe_text = iframe_text.split('```json')[1].split('```')[0].strip()
                            
                            iframe_result = json.loads(iframe_text)
                            
                            if iframe_result.get('is_verification'):
                                logger.info(f"✅ Found verification in iframe {i}")
                                box = await frame_element.bounding_box()
                                
                                if box:
                                    iframe_pos = iframe_result.get('button_position', {})
                                    iframe_x = box['x'] + (box['width'] * (iframe_pos.get('x_percent', 50) / 100.0))
                                    iframe_y = box['y'] + (box['height'] * (iframe_pos.get('y_percent', 50) / 100.0))
                                    
                                    logger.info(f"📍 Clicking iframe at ({iframe_x:.0f}, {iframe_y:.0f})")
                                    
                                    if result['type'] == 'press_hold' or result.get('requires_hold'):
                                        hold_duration = result.get('hold_duration_seconds', 8) * 1000
                                        logger.info(f"🖱️ Press & hold in iframe for {hold_duration/1000}s...")
                                        await self.page.mouse.move(iframe_x, iframe_y)
                                        await self.page.mouse.down()
                                        await self.page.wait_for_timeout(hold_duration)
                                        await self.page.mouse.up()
                                        logger.info("✅ Press & hold completed (iframe)")
                                    else:
                                        await self.page.mouse.click(iframe_x, iframe_y)
                                        await self.page.wait_for_timeout(2000)
                                        logger.info("✅ Click completed (iframe)")
                                    
                                    await self.page.wait_for_timeout(3000)
                                    return True
                    except Exception as e:
                        logger.debug(f"Could not analyze iframe {i}: {e}")
                        continue
            
            # Try to find actual button element (BREAKTHROUGH: Keyboard approach)
            logger.info("🔍 Attempting to find Press & Hold button...")
            button_element = None
            button_selectors = [
                '.px-captcha-error-button',
                'div.px-captcha-error-button',
                'div:has-text("Press & Hold")',
                'button:has-text("Press & Hold")',
                '[class*="captcha"][class*="button"]'
            ]
            
            for selector in button_selectors:
                try:
                    element = self.page.locator(selector).first
                    if await element.is_visible(timeout=2000):
                        button_element = element
                        logger.info(f"✅ Found button: {selector}")
                        break
                except:
                    continue
            
            if button_element:
                # BREAKTHROUGH: Keyboard approach bypasses PerimeterX
                logger.info("🖱️ Clicking button with press & hold...")
                try:
                    box = await button_element.bounding_box()
                    if box:
                        btn_x = box['x'] + box['width'] / 2
                        btn_y = box['y'] + box['height'] / 2
                        logger.info(f"📍 Button center: ({btn_x:.0f}, {btn_y:.0f})")
                        
                        # CRITICAL: Keyboard approach (TAB + SPACE)
                        logger.info("⌨️ Trying keyboard approach (TAB + SPACE)...")
                        
                        # Press TAB 10x to focus button
                        for i in range(10):
                            await self.page.keyboard.press('Tab')
                            await self.page.wait_for_timeout(300)
                        
                        # Hold SPACE for 10 seconds
                        logger.info("⏱️ Holding SPACE for 10s...")
                        await self.page.keyboard.down('Space')
                        await self.page.wait_for_timeout(10000)
                        await self.page.keyboard.up('Space')
                        logger.info("✅ Keyboard press & hold completed!")
                        
                        # Wait for page load
                        await self.page.wait_for_timeout(3000)
                        logger.info("⏱️ Waited 3s for page load")
                        
                        return True
                except Exception as e:
                    logger.warning(f"Button interaction failed: {e}")
            
            # Final fallback: Click Gemini coordinates
            position = result.get('position', {})
            x = viewport['width'] * (position.get('x_percent', 50) / 100.0)
            y = viewport['height'] * (position.get('y_percent', 50) / 100.0)
            
            logger.info(f"📍 Fallback to Gemini coordinates: ({x:.0f}, {y:.0f})")
            
            if result['type'] == 'press_hold' or result.get('requires_hold'):
                hold_duration = result.get('hold_duration_seconds', 10) * 1000
                logger.info(f"🖱️ Press & hold for {hold_duration/1000}s...")
                
                # Human-like movement
                start_x = random.randint(100, 500)
                start_y = random.randint(100, 500)
                await self.page.mouse.move(start_x, start_y)
                await self.page.wait_for_timeout(random.randint(100, 300))
                
                final_x = x + random.randint(-5, 5)
                final_y = y + random.randint(-5, 5)
                await self.page.mouse.move(final_x, final_y)
                await self.page.wait_for_timeout(random.randint(200, 500))
                
                await self.page.mouse.down()
                await self.page.wait_for_timeout(hold_duration)
                await self.page.mouse.up()
                
                logger.info("✅ Press & hold completed (Gemini coordinates)")
            else:
                await self.page.mouse.click(x, y)
                logger.info("✅ Click completed (Gemini coordinates)")
            
            await self.page.wait_for_timeout(3000)
            return True
            
        except Exception as e:
            logger.error(f"Gemini verification failed: {e}")
            return False
    
    async def _dismiss_popups(self) -> bool:
        """
        Dismiss common popups
        
        Types:
        - Cookie banners
        - Email signup
        - Notifications
        - Ads
        - Modal overlays
        
        Returns:
            True if any popups were dismissed
        """
        dismissed_count = 0
        
        close_selectors = [
            # X buttons
            'button[aria-label*="close" i]',
            'button[aria-label*="dismiss" i]',
            'button[title*="close" i]',
            '[class*="close-button" i]',
            '[class*="close-btn" i]',
            '[class*="modal-close" i]',
            '[id*="close-button" i]',
            '.close-icon',
            # Text buttons
            'button:has-text("Close")',
            'button:has-text("No Thanks")',
            'button:has-text("No thanks")',
            'button:has-text("Maybe Later")',
            'button:has-text("Not Now")',
            'button:has-text("Dismiss")',
            'button:has-text("Continue")',
            'button:has-text("Accept")',
            # Cookies
            'button:has-text("Accept All")',
            'button:has-text("Accept Cookies")',
            'button:has-text("I Agree")',
            '[id*="cookie-accept"]',
            '[class*="cookie-accept"]',
            # Email signup
            '[data-testid*="close"]',
            '[data-testid*="dismiss"]',
            '.email-signup-close',
            '.newsletter-close',
            # Overlays
            '.modal-overlay',
            '.popup-overlay',
            '[class*="overlay"][class*="modal"]'
        ]
        
        for selector in close_selectors:
            try:
                elements = await self.page.locator(selector).all()
                
                for element in elements:
                    try:
                        if await element.is_visible(timeout=500):
                            await element.click(timeout=1000)
                            dismissed_count += 1
                            logger.info(f"✅ Dismissed popup: {selector}")
                            await asyncio.sleep(0.5)
                    except:
                        continue
                        
            except Exception as e:
                logger.debug(f"Popup check failed for {selector}: {e}")
                continue
        
        if dismissed_count > 0:
            logger.info(f"🧹 Dismissed {dismissed_count} popups")
        
        return dismissed_count > 0
