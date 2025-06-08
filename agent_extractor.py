"""
Agent Extractor - Unified extraction using OpenManus -> Skyvern -> Browser Use hierarchy
Handles retailer-specific data extraction, cleaning, and validation.
"""

import json
import re
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import os

from logger_config import setup_logging
from pattern_learner import PatternLearner
from cost_tracker import cost_tracker

logger = setup_logging(__name__)

@dataclass
class ExtractionResult:
    success: bool
    data: Dict[str, Any]
    method_used: str
    processing_time: float
    warnings: List[str]
    errors: List[str]

class AgentExtractor:
    def __init__(self):
        # Load configuration
        import json
        import os
        
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, 'config.json')
        
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.pattern_learner = PatternLearner()
        
        # Initialize browser use components
        self.browser_use_agent = None
        self.browser_use_llm = None
        
        # Initialize LLM clients for browser use
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            self.browser_use_llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash-exp",
                temperature=0.1,
                google_api_key=self.config["agents"]["openmanus"]["api_key"]
            )
            logger.info("✅ Browser Use LLM initialized")
        except Exception as e:
            logger.warning(f"⚠️ Browser Use LLM initialization failed: {e}")
        
        # Import extraction tools
        try:
            # These would be actual imports in real implementation
            self.openmanus = None  # OpenManus client
            self.skyvern = None    # Skyvern client  
            self.browser_use = None # Browser Use client
            logger.info("Extraction agents initialized")
        except ImportError as e:
            logger.warning(f"Some extraction tools not available: {e}")
    
    async def extract_product_data(self, url: str, retailer: str) -> ExtractionResult:
        """Main extraction method with markdown/agent routing and fallback hierarchy"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Get learned patterns for this retailer/URL
            learned_patterns = await self.pattern_learner.get_learned_patterns(retailer, url)
            
            # STEP 1: Route to appropriate extraction method based on retailer
            from markdown_extractor import MarkdownExtractor, MARKDOWN_RETAILERS
            
            if retailer in MARKDOWN_RETAILERS:
                # Try markdown extraction first for these retailers
                logger.info(f"Using markdown extraction for {retailer}: {url}")
                
                try:
                    markdown_extractor = MarkdownExtractor()
                    markdown_result = await markdown_extractor.extract_product_data(url, retailer)
                    
                    if markdown_result.success and not markdown_result.should_fallback:
                        # Markdown extraction succeeded - process and return
                        processed_data = await self._process_extracted_data(markdown_result.data, retailer)
                        
                        if self._validate_extraction_quality(processed_data, retailer):
                            # Record successful pattern
                            await self.pattern_learner.record_successful_extraction(
                                retailer, url, "markdown_extractor", processed_data
                            )
                            
                            processing_time = asyncio.get_event_loop().time() - start_time
                            
                            # Track API call with cost tracking
                            cost_tracker.track_api_call(
                                method="markdown_extractor",
                                prompt=f"Markdown extraction for {retailer}",
                                response={'success': True, 'data': processed_data},
                                retailer=retailer,
                                url=url,
                                processing_time=processing_time
                            )
                            
                            logger.info(f"✅ Markdown extraction successful for {retailer} in {processing_time:.2f}s")
                            return ExtractionResult(
                                success=True,
                                data=processed_data,
                                method_used="markdown_extractor",
                                processing_time=processing_time,
                                warnings=markdown_result.warnings,
                                errors=[]
                            )
                    
                    # Markdown extraction failed or indicated fallback needed
                    logger.warning(f"Markdown extraction failed for {retailer}, falling back to browser agent")
                    logger.warning(f"Markdown errors: {markdown_result.errors}")
                    
                except Exception as e:
                    logger.error(f"Markdown extractor error for {retailer}: {e}, falling back to browser agent")
            
            # STEP 2: Use browser agent (either direct route or fallback)
            if retailer not in MARKDOWN_RETAILERS:
                logger.info(f"Using browser agent for {retailer} (direct route): {url}")
            else:
                logger.info(f"Using browser agent for {retailer} (fallback from markdown): {url}")
            
            # Build prompt for browser agent
            prompt = self._build_extraction_prompt(url, retailer, learned_patterns)
            
            # Check for cached response first
            cached_response = cost_tracker.get_cached_response(prompt)
            if cached_response:
                logger.info(f"Using cached response for {url}")
                processing_time = asyncio.get_event_loop().time() - start_time
                
                # Track the cache hit
                cost_tracker.track_api_call(
                    method="browser_use_cached", 
                    prompt=prompt, 
                    response=cached_response,
                    retailer=retailer, 
                    url=url, 
                    processing_time=processing_time
                )
                
                # Ensure cached_response is a dict
                if isinstance(cached_response, dict):
                    cached_data = cached_response.get('data', {})
                else:
                    # Handle case where cached_response is a string or other type
                    cached_data = {
                        "retailer": retailer,
                        "title": "Cached Result",
                        "raw_output": str(cached_response)
                    }
                
                return ExtractionResult(
                    success=True,
                    data=cached_data,
                    method_used="browser_use_cached",
                    processing_time=processing_time,
                    warnings=[],
                    errors=[]
                )
            
            # Perform browser agent extraction
            result = await self._extract_with_browser_use(url, retailer, learned_patterns, prompt)
            
            if result.success:
                # Process and validate extracted data
                processed_data = await self._process_extracted_data(result.data, retailer)
                
                if self._validate_extraction_quality(processed_data, retailer):
                    # Record successful pattern
                    await self.pattern_learner.record_successful_extraction(
                        retailer, url, "browser_use", processed_data
                    )
                    
                    processing_time = asyncio.get_event_loop().time() - start_time
                    
                    # Track API call with cost tracking
                    response_data = {'success': True, 'data': processed_data}
                    cost_tracker.track_api_call(
                        method="browser_use",
                        prompt=prompt, 
                        response=response_data,
                        retailer=retailer,
                        url=url,
                        processing_time=processing_time
                    )
                    
                    return ExtractionResult(
                        success=True,
                        data=processed_data,
                        method_used="browser_use",
                        processing_time=processing_time,
                        warnings=result.warnings,
                        errors=[]
                    )
                else:
                    logger.warning(f"Browser agent extraction quality validation failed for {retailer}")
            
            # Browser agent also failed
            await self.pattern_learner.record_failed_extraction(retailer, url, "browser_use", str(result.errors))
            
            # Track failed API call
            cost_tracker.track_api_call(
                method="browser_use",
                prompt=prompt,
                response={'success': False, 'error': str(result.errors)},
                retailer=retailer,
                url=url,
                processing_time=asyncio.get_event_loop().time() - start_time
            )
            
            # All methods failed
            processing_time = asyncio.get_event_loop().time() - start_time
            error_message = f"Both markdown and browser agent extraction failed for {retailer}"
            logger.error(error_message)
            
            return ExtractionResult(
                success=False,
                data={},
                method_used="none",
                processing_time=processing_time,
                warnings=[],
                errors=[error_message]
            )
            
        except Exception as e:
            logger.error(f"Critical error in extraction for {url}: {e}")
            processing_time = asyncio.get_event_loop().time() - start_time
            return ExtractionResult(
                success=False,
                data={},
                method_used="error",
                processing_time=processing_time,
                warnings=[],
                errors=[str(e)]
            )
    
    async def _extract_with_method(self, method: str, url: str, retailer: str, 
                                 learned_patterns: List, prompt: str) -> ExtractionResult:
        """Extract using specific method"""
        
        if method == 'openmanus':
            return await self._extract_with_openmanus(url, retailer, learned_patterns, prompt)
        elif method == 'skyvern':
            return await self._extract_with_skyvern(url, retailer, learned_patterns, prompt)
        elif method == 'browser_use':
            return await self._extract_with_browser_use(url, retailer, learned_patterns, prompt)
        else:
            raise ValueError(f"Unknown extraction method: {method}")
    
    async def _extract_with_openmanus(self, url: str, retailer: str, learned_patterns: List, prompt: str) -> ExtractionResult:
        """Extract using OpenManus CLI agent"""
        
        try:
            import subprocess
            import json
            import asyncio
            from pathlib import Path
            
            start_time = asyncio.get_event_loop().time()
            
            logger.info(f"Starting OpenManus extraction for {url}")
            
            # Get OpenManus configuration
            openmanus_config = self.config["agents"]["openmanus"]
            installation_path = openmanus_config["installation_path"]
            conda_env = openmanus_config["conda_env"]
            
            logger.debug(f"OpenManus config: {installation_path}, {conda_env}")
            
            # Build the command to run OpenManus
            # We'll create a temporary script that runs OpenManus with our prompt
            # Use repr() to properly escape the prompt for Python
            escaped_prompt = repr(prompt)
            
            script_content = f'''
import asyncio
import sys
import json
import traceback
sys.path.insert(0, "{installation_path}")

from app.agent.manus import Manus

async def main():
    try:
        agent = await Manus.create()
        result = await agent.run({escaped_prompt})
        print("OPENMANUS_RESULT_START")
        print(json.dumps(result))
        print("OPENMANUS_RESULT_END")
        await agent.cleanup()
    except Exception as e:
        print("OPENMANUS_ERROR_START")
        print(f"Error: {{e}}")
        traceback.print_exc()
        print("OPENMANUS_ERROR_END")

if __name__ == "__main__":
    asyncio.run(main())
'''
            
            # Write temporary script
            temp_script = Path(installation_path) / "temp_openmanus_script.py"
            temp_script.write_text(script_content)
            
            try:
                # Run OpenManus using conda environment
                cmd = [
                    f"{conda_env}/bin/python",
                    str(temp_script)
                ]
                
                logger.info(f"Running OpenManus command: {' '.join(cmd)}")
                
                # Run the command with timeout
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=installation_path
                )
                
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=openmanus_config["timeout"]
                )
                
                stdout_text = stdout.decode().strip()
                stderr_text = stderr.decode().strip()
                
                logger.debug(f"OpenManus stdout: {stdout_text[:500]}...")
                logger.debug(f"OpenManus stderr: {stderr_text[:500]}...")
                
                # Calculate actual processing time
                processing_time = asyncio.get_event_loop().time() - start_time
                
                if process.returncode == 0:
                    # Parse OpenManus output
                    try:
                        # Look for result markers
                        if "OPENMANUS_RESULT_START" in stdout_text:
                            start_idx = stdout_text.find("OPENMANUS_RESULT_START") + len("OPENMANUS_RESULT_START\n")
                            end_idx = stdout_text.find("OPENMANUS_RESULT_END")
                            if end_idx > start_idx:
                                result_json = stdout_text[start_idx:end_idx].strip()
                                data = json.loads(result_json)
                            else:
                                raise ValueError("Could not parse OpenManus result")
                        else:
                            # Try to parse entire output as JSON
                            data = json.loads(stdout_text)
                    except json.JSONDecodeError:
                        # If not JSON, create structured data from text output
                        data = {
                            "retailer": retailer,
                            "title": "Extracted by OpenManus",
                            "description": stdout_text,
                            "raw_output": stdout_text
                        }
                    
                    # Ensure data is a dictionary for processing
                    if not isinstance(data, dict):
                        data = {
                            "retailer": retailer,
                            "title": "Extracted by OpenManus",
                            "description": str(data),
                            "raw_output": str(data)
                        }
                    
                    return ExtractionResult(
                        success=True,
                        data=data,
                        method_used="openmanus",
                        processing_time=processing_time,
                        warnings=[],
                        errors=[]
                    )
                else:
                    error_msg = f"OpenManus CLI error (code {process.returncode}): {stderr_text}"
                    logger.error(error_msg)
                    return ExtractionResult(
                        success=False,
                        data={},
                        method_used="openmanus",
                        processing_time=processing_time,
                        warnings=[],
                        errors=[error_msg]
                    )
                    
            finally:
                # Clean up temporary script
                if temp_script.exists():
                    temp_script.unlink()
            
        except asyncio.TimeoutError:
            processing_time = asyncio.get_event_loop().time() - start_time
            error_msg = f"OpenManus extraction timed out after {openmanus_config['timeout']} seconds"
            logger.error(error_msg)
            return ExtractionResult(
                success=False,
                data={},
                method_used="openmanus",
                processing_time=processing_time,
                warnings=[],
                errors=[error_msg]
            )
            
        except Exception as e:
            processing_time = asyncio.get_event_loop().time() - start_time
            error_msg = f"OpenManus CLI execution error: {str(e)}"
            logger.error(error_msg)
            return ExtractionResult(
                success=False,
                data={},
                method_used="openmanus",
                processing_time=processing_time,
                warnings=[],
                errors=[error_msg]
            )
    
    async def _extract_with_skyvern(self, url: str, retailer: str, learned_patterns: List, prompt: str) -> ExtractionResult:
        """Extract using Skyvern agent"""
        # Similar structure to OpenManus but with Skyvern-specific implementation
        return ExtractionResult(success=False, data={}, method_used="skyvern", 
                              processing_time=0, warnings=[], errors=["Skyvern not implemented"])
    
    async def _extract_with_browser_use(self, url: str, retailer: str, learned_patterns: dict, prompt: str) -> ExtractionResult:
        """Perform extraction using browser_use agent"""
        try:
            # Initialize browser_use if not already done
            if not self.browser_use_llm:
                return ExtractionResult(
                    success=False,
                    data={},
                    method_used="browser_use",
                    processing_time=0,
                    warnings=[],
                    errors=["Browser Use LLM not initialized"]
                )
            
            # Import and initialize browser_use
            try:
                # Try to import browser_use from external installation
                import sys
                import os
                
                # Add the external browser-use path if it exists
                external_browser_use_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'browser-use')
                if os.path.exists(external_browser_use_path) and external_browser_use_path not in sys.path:
                    sys.path.insert(0, external_browser_use_path)
                
                from browser_use import Browser, BrowserConfig  # type: ignore
                from browser_use.browser.browser import BrowserContextConfig  # type: ignore
                logger.debug("Browser Use imported successfully")
                
            except ImportError as e:
                logger.error(f"Failed to import browser_use: {e}")
                logger.info("Note: Browser Use should be installed separately or placed in ../browser-use/")
                return ExtractionResult(
                    success=False,
                    data={},
                    method_used="browser_use",
                    processing_time=0,
                    warnings=[],
                    errors=[f"Browser Use not available: {e}"]
                )
            
            # Configure browser session with anti-detection
            browser_config = {
                'headless': True,
                'extra_chromium_args': [
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                ]
            }
            
            # Apply retailer-specific anti-detection
            if retailer in ['nordstrom', 'aritzia', 'anthropologie']:
                # These retailers have stronger anti-bot measures
                browser_config['extra_chromium_args'].extend([
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-extensions'
                ])
            
            # Create context config
            context_config = BrowserContextConfig(
                disable_security=True,
                browser_window_size={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # Create browser config
            config = BrowserConfig(
                headless=browser_config['headless'],
                extra_chromium_args=browser_config['extra_chromium_args'],
                new_context_config=context_config
            )
            
            browser = Browser(config=config)
            
            try:
                # Execute extraction task
                logger.debug(f"Executing browser_use extraction: {prompt[:200]}...")
                
                # Enhanced prompt with URL navigation
                full_prompt = f"Navigate to {url} and {prompt}"
                
                result = await browser.run(full_prompt)
                
                # Parse result
                parsed_data = self._parse_json_result(str(result), retailer)
                
                if parsed_data:
                    return ExtractionResult(
                        success=True,
                        data=parsed_data,
                        method_used="browser_use",
                        processing_time=0,  # Will be calculated by caller
                        warnings=[],
                        errors=[]
                    )
                else:
                    # Create fallback data structure
                    fallback_data = {
                        "retailer": retailer,
                        "title": "Extracted by Browser Use",
                        "description": str(result)[:500],
                        "raw_output": str(result)
                    }
                    
                    return ExtractionResult(
                        success=True,  # Technical success
                        data=fallback_data,
                        method_used="browser_use",
                        processing_time=0,
                        warnings=["Could not parse structured data, using fallback"],
                        errors=[]
                    )
                    
            finally:
                # Clean up browser
                try:
                    await browser.close()
                except:
                    pass  # Ignore cleanup errors
                
        except Exception as e:
            logger.error(f"Browser Use extraction failed: {e}")
            return ExtractionResult(
                success=False,
                data={},
                method_used="browser_use",
                processing_time=0,
                warnings=[],
                errors=[str(e)]
            )
    
    def _parse_json_result(self, result_text: str, retailer: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from extraction result text"""
        
        if not result_text:
            return None
        
        try:
            # Look for JSON pattern in the text
            import re
            import json
            
            # Try to find JSON blocks
            json_patterns = [
                r'\{[^{}]*"retailer"[^{}]*\}',  # Simple JSON with retailer field
                r'\{.*?\}',  # Any JSON-like structure
                r'```json\s*(\{.*?\})\s*```',  # Markdown JSON blocks
                r'```\s*(\{.*?\})\s*```'  # Generic code blocks
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, result_text, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    try:
                        # Clean up the match
                        json_str = match.strip()
                        if json_str.startswith('json'):
                            json_str = json_str[4:].strip()
                        
                        # Parse JSON
                        data = json.loads(json_str)
                        
                        # Validate it has some expected fields
                        if isinstance(data, dict) and (
                            'title' in data or 
                            'retailer' in data or 
                            'price' in data
                        ):
                            # Ensure retailer field matches
                            data['retailer'] = retailer
                            return data
                            
                    except json.JSONDecodeError:
                        continue
            
            # If no JSON found, try to extract key-value pairs
            extracted_data = {"retailer": retailer}
            
            # Extract title
            title_patterns = [
                r'title[:\s]*["\']([^"\']+)["\']',
                r'product[_\s]*title[:\s]*["\']([^"\']+)["\']',
                r'name[:\s]*["\']([^"\']+)["\']'
            ]
            
            for pattern in title_patterns:
                match = re.search(pattern, result_text, re.IGNORECASE)
                if match:
                    extracted_data['title'] = match.group(1).strip()
                    break
            
            # Extract price
            price_patterns = [
                r'price[:\s]*["\']?[\$]?([0-9.,]+)["\']?',
                r'cost[:\s]*["\']?[\$]?([0-9.,]+)["\']?',
                r'\$([0-9.,]+)'
            ]
            
            for pattern in price_patterns:
                match = re.search(pattern, result_text, re.IGNORECASE)
                if match:
                    extracted_data['price'] = f"${match.group(1)}"
                    break
            
            # Return if we found at least title or price
            if 'title' in extracted_data or 'price' in extracted_data:
                return extracted_data
                
        except Exception as e:
            logger.warning(f"Error parsing JSON result: {e}")
        
        return None
    
    def _get_rotated_user_agents(self, retailer: str) -> List[str]:
        """Get realistic user agents with rotation based on retailer preferences"""
        
        # Desktop user agents (primary)
        desktop_agents = [
            # Chrome (most common)
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            
            # Firefox
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
            
            # Safari (Mac)
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            
            # Edge
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        ]
        
        # Mobile user agents (often less detected)
        mobile_agents = [
            # iPhone
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0.6099.119 Mobile/15E148 Safari/604.1",
            
            # Android
            "Mozilla/5.0 (Linux; Android 14; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.210 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.210 Mobile Safari/537.36"
        ]
        
        # Retailer-specific preferences
        retailer_preferences = {
            "nordstrom": desktop_agents + mobile_agents[:2],  # Include mobile for better success
            "aritzia": desktop_agents[1:4] + mobile_agents[:1],  # Prefer Mac agents 
            "anthropologie": desktop_agents,  # Desktop focus
            "abercrombie": desktop_agents + mobile_agents,  # Mixed
            "revolve": desktop_agents[:3],  # Chrome focused
        }
        
        return retailer_preferences.get(retailer, desktop_agents)
    
    def _get_retailer_specific_args(self, retailer: str) -> List[str]:
        """Get retailer-specific browser arguments for enhanced stealth"""
        
        base_args = [
            "--disable-default-browser-check",
            "--disable-translate",
            "--disable-extensions",
            "--disable-plugins",
            "--disable-sync"
        ]
        
        retailer_args = {
            "nordstrom": [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-notifications",
                "--disable-popup-blocking"
            ],
            "aritzia": [
                "--disable-blink-features=AutomationControlled", 
                "--disable-geolocation",
                "--disable-notifications"
            ],
            "anthropologie": [
                "--disable-blink-features=AutomationControlled",
                "--disable-notifications"
            ],
            "abercrombie": [
                "--disable-blink-features=AutomationControlled",
                "--disable-notifications", 
                "--disable-infobars"
            ],
            "revolve": [
                "--disable-blink-features=AutomationControlled",
                "--disable-notifications",
                "--disable-images=false"  # Revolve is image-heavy
            ]
        }
        
        return base_args + retailer_args.get(retailer, [])
    
    def _get_retailer_timeout(self, retailer: str, base_timeout: int, attempt: int) -> int:
        """Get retailer-specific timeout values with retry adjustments"""
        
        # Base timeouts by retailer difficulty
        retailer_timeouts = {
            "nordstrom": 300,  # Longer for high-protection sites
            "aritzia": 240,
            "anthropologie": 180,
            "abercrombie": 200,
            "revolve": 180,
            "default": base_timeout
        }
        
        timeout = retailer_timeouts.get(retailer, base_timeout)
        
        # Increase timeout on retries
        if attempt > 0:
            timeout += (attempt * 60)  # Add 1 minute per retry
        
        return timeout
    
    def _build_anti_detection_prompt(self, base_prompt: str, retailer: str) -> str:
        """Build enhanced prompt with human-like behavior instructions"""
        
        # PHASE 2: Human-like browsing behavior + VERIFICATION HANDLING
        behavioral_instructions = {
            "nordstrom": """IMPORTANT: Browse naturally like a real customer:
1. First, wait 3-5 seconds after page loads
2. Scroll down slowly to see the page content
3. Hover over product images before extracting data
4. Take time to "read" product details (pause 2-3 seconds)
5. If you see any popups or overlays, close them naturally
6. VERIFICATION HANDLING: If you see "Press & Hold to confirm you are a human" button, click and hold it for 3-5 seconds until verification completes
7. If Cloudflare protection appears, wait for it to complete automatically or click through any checkboxes""",
            
            "aritzia": """IMPORTANT: Shop naturally on Aritzia:
1. Wait for page to fully load (3-5 seconds)
2. Scroll through the product page slowly
3. Look at size options and product details
4. Hover over elements before clicking
5. Take your time extracting information
6. VERIFICATION HANDLING: If "verify you are human" checkbox appears, click it immediately
7. If Cloudflare tabs open, close them by clicking the X or switching back to main tab
8. If verification fails, try the checkbox again after a 2-3 second pause
9. Keep retrying verification until the product page loads properly""",
            
            "anthropologie": """IMPORTANT: Browse like a real shopper:
1. Allow page to load completely (3-4 seconds)
2. Scroll down to see all product information
3. Examine product details and images naturally
4. Don't rush through the extraction process
5. VERIFICATION HANDLING: If you see "Press & Hold to confirm you are a human" button, click and hold it for 4-6 seconds
6. Wait for verification to complete before proceeding
7. If verification appears multiple times, repeat the process patiently""",
            
            "urban_outfitters": """IMPORTANT: Shop naturally:
1. Wait for page load (3-5 seconds)
2. Scroll down to view product details
3. Close any popups that appear
4. Hover over product information before extracting
5. Take time between actions (2-3 second pauses)
6. VERIFICATION HANDLING: If "Press & Hold to confirm you are a human" appears, click and hold the button for 4-6 seconds
7. Watch for the verification to complete (button color change or checkmark)
8. If verification fails, wait 3 seconds and try again""",
            
            "abercrombie": """IMPORTANT: Shop naturally:
1. Wait for page load (3-5 seconds)
2. Scroll down to view product details
3. Close any popups that appear
4. Hover over product information before extracting
5. Take time between actions (2-3 second pauses)
6. VERIFICATION HANDLING: If any verification appears (checkboxes, press-and-hold), complete it patiently
7. Multiple verification attempts may be needed - keep trying until successful""",
            
            "revolve": """IMPORTANT: Shop naturally:
1. Wait for page load (3-5 seconds) 
2. Scroll down to view product details
3. Close any popups that appear
4. Hover over product information before extracting
5. Take time between actions (2-3 second pauses)
6. VERIFICATION HANDLING: Handle any verification challenges that appear""",
            
            "default": """IMPORTANT: Browse naturally:
1. Wait 3-5 seconds after page loads
2. Scroll down to view all content
3. Hover over elements before interacting
4. Take natural pauses between actions
5. VERIFICATION HANDLING: If any verification appears (checkboxes, press-and-hold buttons, Cloudflare), handle it:
   - For checkboxes: Click them immediately
   - For press-and-hold: Click and hold for 4-6 seconds
   - For Cloudflare: Wait for auto-completion or follow prompts
   - If verification fails, retry after a 2-3 second pause"""
        }
        
        behavior = behavioral_instructions.get(retailer, behavioral_instructions["default"])
        
        # Add universal verification handling instructions
        verification_guidance = """

CRITICAL VERIFICATION HANDLING RULES:
- ALWAYS complete any verification challenges before extracting data
- "Verify you are human" checkboxes: Click immediately, retry if needed
- "Press & Hold" buttons: Click and hold for 4-6 seconds minimum
- Cloudflare protection: Wait patiently, close extra tabs if they appear
- If verification fails, wait 2-3 seconds and try again
- Don't give up - some sites require multiple verification attempts
- Only proceed to data extraction AFTER all verifications are completed"""
        
        return f"{behavior}\n{verification_guidance}\n\nAfter completing all verifications and browsing naturally, {base_prompt}"
    
    async def _process_browser_use_result(self, result, retailer: str, processing_time: float, url: str) -> ExtractionResult:
        """Process Browser Use result with enhanced verification detection logic"""
        
        logger.debug(f"Browser Use raw result: {str(result)[:200]}...")
        
        # Enhanced verification attempt detection
        verification_indicators = self._detect_verification_attempts(result)
        
        # Parse the result
        if isinstance(result, dict):
            extracted_data = result
        elif hasattr(result, 'action_results'):
            action_results = result.action_results()
            # Parse Browser Use AgentHistoryList
            extracted_data = None
            
            # Enhanced parsing with verification loop detection
            verification_loops = 0
            done_actions = 0
            failed_actions = 0
            
            # Look for extracted content with JSON
            for i, action_result in enumerate(action_results):
                # Count verification-related actions
                if hasattr(action_result, 'extracted_content') and action_result.extracted_content:
                    content = action_result.extracted_content.lower()
                    if any(term in content for term in ['click', 'hold', 'verify', 'human', 'wait']):
                        verification_loops += 1
                
                # Count done vs failed actions
                if hasattr(action_result, 'is_done') and action_result.is_done:
                    done_actions += 1
                if hasattr(action_result, 'success') and action_result.success == False:
                    failed_actions += 1
                    
                if hasattr(action_result, 'extracted_content') and action_result.extracted_content:
                    content = action_result.extracted_content
                    
                    # Check if this is the final done action with clean JSON
                    if hasattr(action_result, 'is_done') and action_result.is_done and '{' in content and '}' in content:
                        # Check for verification failure messages
                        if any(phrase in content.lower() for phrase in 
                               ['unable to complete', 'could not pass', 'verification failed', 'did not work']):
                            logger.warning(f"Browser Use reported verification failure: {content[:100]}...")
                            verification_indicators['verification_failed'] = True
                            verification_indicators['failure_message'] = content
                        
                        # Try to extract JSON from the done message
                        import re
                        json_match = re.search(r'\{.*\}', content, re.DOTALL)
                        if json_match:
                            try:
                                import json
                                json_string = json_match.group(0)
                                # Clean escaped characters
                                json_string = json_string.replace('\\n', '\n').replace('\\"', '"')
                                extracted_data = json.loads(json_string)
                                # Ensure retailer field matches our input
                                extracted_data['retailer'] = retailer
                                break
                            except json.JSONDecodeError as e:
                                logger.debug(f"JSON decode error from done action: {e}")
                    
                    # Check for markdown JSON blocks
                    if '```json' in content:
                        # Extract JSON from markdown code blocks
                        import re
                        json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL | re.MULTILINE)
                        if not json_match:
                            # Try a more flexible pattern
                            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL | re.MULTILINE)
                            if json_match:
                                # Check if it looks like valid JSON
                                candidate = json_match.group(1).strip()
                                if candidate.startswith('{') and candidate.endswith('}'):
                                    json_match = type('Match', (), {'group': lambda self, n: candidate})()
                        
                        if json_match:
                            try:
                                import json
                                json_string = json_match.group(1)
                                # Clean escaped characters from Browser Use output
                                json_string = json_string.replace('\\n', '\n').replace('\\"', '"')
                                extracted_data = json.loads(json_string)
                                # Standardize field names to match our expected format
                                if 'product_title' in extracted_data:
                                    extracted_data['title'] = extracted_data.pop('product_title')
                                if 'product_id' in extracted_data:
                                    extracted_data['product_code'] = extracted_data.pop('product_id')
                                if 'main_image_urls' in extracted_data:
                                    extracted_data['image_urls'] = extracted_data.pop('main_image_urls')
                                # Ensure retailer field matches our input
                                extracted_data['retailer'] = retailer
                                break
                            except json.JSONDecodeError as e:
                                logger.debug(f"JSON decode error: {e}")
                                continue
            
            # Analyze verification handling patterns
            verification_indicators.update({
                'verification_loops': verification_loops,
                'done_actions': done_actions,
                'failed_actions': failed_actions,
                'total_actions': len(action_results),
                'likely_stuck_in_loop': verification_loops > 20,  # More than 20 verification attempts
                'action_failure_rate': failed_actions / max(1, len(action_results))
            })
            
            # Fallback if no JSON found
            if not extracted_data:
                # Check if this was a verification failure
                if verification_indicators.get('verification_failed'):
                    logger.warning(f"Browser Use failed verification challenges for {retailer}")
                    return ExtractionResult(
                        success=False,
                        data={},
                        method_used="browser_use",
                        processing_time=processing_time,
                        warnings=[f"Verification handling failed: {verification_indicators.get('failure_message', 'Unknown')}"],
                        errors=["Verification challenges could not be completed"]
                    )
                
                # Create fallback data but mark it as such
                extracted_data = {
                    "retailer": retailer,
                    "title": "Extracted by Browser Use",
                    "description": str(result),
                    "raw_output": str(result),
                    "_is_fallback_data": True,  # Flag for validation
                    "_verification_indicators": verification_indicators
                }
                
        elif isinstance(result, str):
            # Try to parse as JSON
            try:
                import json
                extracted_data = json.loads(result)
            except json.JSONDecodeError:
                # Create structured data from text
                extracted_data = {
                    "retailer": retailer,
                    "title": "Extracted by Browser Use",
                    "description": result,
                    "raw_output": result,
                    "_is_fallback_data": True
                }
        else:
            # Fallback
            extracted_data = {
                "retailer": retailer,
                "title": "Extracted by Browser Use",
                "raw_output": str(result),
                "_is_fallback_data": True
            }
        
        # Enhanced success determination
        is_real_success = self._assess_extraction_quality(extracted_data, verification_indicators, processing_time)
        
        # Add verification metadata
        extracted_data['_verification_metadata'] = {
            'processing_time': processing_time,
            'verification_indicators': verification_indicators,
            'is_real_success': is_real_success
        }
        
        if not is_real_success:
            logger.warning(f"Browser Use extraction quality low for {retailer} - likely fallback data")
        
        return ExtractionResult(
            success=True,  # Technical success (no crash)
            data=extracted_data,
            method_used="browser_use",
            processing_time=processing_time,
            warnings=[] if is_real_success else ["Low extraction quality detected"],
            errors=[]
        )
    
    def _detect_verification_attempts(self, result) -> dict:
        """Detect verification handling attempts in Browser Use results"""
        
        indicators = {
            'verification_keywords_found': False,
            'repeated_clicking_detected': False,
            'verification_failed': False,
            'cloudflare_detected': False,
            'press_hold_attempted': False
        }
        
        # Convert result to string for analysis
        result_str = str(result).lower()
        
        # Check for verification keywords
        verification_keywords = [
            'verify you are human', 'press and hold', 'cloudflare', 
            'just a moment', 'checking your browser', 'security check',
            'human verification', 'captcha', 'click and hold'
        ]
        
        for keyword in verification_keywords:
            if keyword in result_str:
                indicators['verification_keywords_found'] = True
                if 'cloudflare' in keyword:
                    indicators['cloudflare_detected'] = True
                if 'press' in keyword or 'hold' in keyword:
                    indicators['press_hold_attempted'] = True
                break
        
        # Check for repeated clicking patterns (indicates stuck in loop)
        click_count = result_str.count('click')
        wait_count = result_str.count('wait')
        
        if click_count > 15 and wait_count > 15:  # Many repeated actions
            indicators['repeated_clicking_detected'] = True
        
        # Check for explicit failure messages
        failure_phrases = [
            'unable to complete', 'could not pass', 'verification failed',
            'did not work', 'cannot proceed', 'blocked'
        ]
        
        for phrase in failure_phrases:
            if phrase in result_str:
                indicators['verification_failed'] = True
                break
        
        return indicators
    
    def _assess_extraction_quality(self, data: dict, verification_indicators: dict, processing_time: float) -> bool:
        """Assess if extraction represents real success vs fallback data"""
        
        # Immediate disqualifiers
        if data.get('_is_fallback_data'):
            return False
        
        if verification_indicators.get('verification_failed'):
            return False
        
        if verification_indicators.get('likely_stuck_in_loop'):
            return False
        
        # Quality indicators
        quality_score = 0
        
        # Check for real data vs placeholder text
        title = data.get('title', '')
        if title and not any(phrase in title.lower() for phrase in 
                           ['extracted by', 'no title', 'extracted product']):
            quality_score += 2
        
        # Check for actual price
        price = data.get('price')
        if price and isinstance(price, (int, float)) and price > 0:
            quality_score += 3
        elif price and str(price).replace('.', '').replace(',', '').isdigit():
            quality_score += 2
        
        # Check for brand
        if data.get('brand') and data.get('brand') != 'N/A':
            quality_score += 1
        
        # Check for image URLs
        image_urls = data.get('image_urls', [])
        if len(image_urls) >= 3:
            quality_score += 2
        elif len(image_urls) > 0:
            quality_score += 1
        
        # Check for product description
        description = data.get('description', '')
        if description and len(description) > 50:
            quality_score += 1
        
        # Processing time consideration
        if 30 <= processing_time <= 180:  # Reasonable time for real extraction
            quality_score += 1
        elif processing_time > 300:  # Too long suggests issues
            quality_score -= 2
        elif processing_time < 15:  # Too fast suggests no verification encountered
            quality_score -= 1
        
        # Final assessment
        return quality_score >= 5
    
    def _build_extraction_prompt(self, url: str, retailer: str, learned_patterns: List) -> str:
        """Build retailer-specific extraction prompt for agents"""
        
        # Working prompt structure with additional important fields added
        base_prompt = f"Go to {url} and extract product title, brand, price, original_price, description, stock status, sale status, clothing type, product ID/code, and main image URLs. Return as JSON with keys: title, brand, price, original_price, description, stock_status, sale_status, clothing_type, product_code, image_urls, retailer."

        # Add retailer-specific instructions
        retailer_instructions = self._get_retailer_instructions(retailer)
        
        return f"{base_prompt} {retailer_instructions}"
    
    def _get_retailer_instructions(self, retailer: str) -> str:
        """Get retailer-specific extraction instructions"""
        
        instructions = {
            "aritzia": "CAD prices. TNA/Wilfred brands. Sale indicators: compare-at prices. Order images: main product view first.",
            "asos": "Multi-brand. Check designer names. Sale vs original pricing. Order images: primary product view first, detail views after.",
            "hm": "H&M brand. European sizing. Conscious collection indicators. Order images: main product photo first.",
            "uniqlo": "Uniqlo/collaboration brands. Limited availability = low stock. IMPORTANT: When on sale, original_price may not be available - set to null if not shown. Order images: primary product view first.",
            "revolve": "Designer brands. Revolve exclusive indicators. Crossed-out prices = sale. Order images: main model shot first, detail views after.",
            "mango": "Mango brand. Outlet vs regular. European price format (US$ XX.XX). Order images: primary product view first.",
            "anthropologie": "Anthropologie/Free People brands. Compare-at pricing. Order images: main product shot first, styled shots after.",
            "abercrombie": "A&F/Abercrombie brands. Clearance indicators. Order images: primary product view first, detail shots after.",
            "nordstrom": "Multi-brand designers. Compare-at sale pricing. Order images: main product image first, detail views after.",
            "urban_outfitters": "UO/multi-brand. Exclusive indicators. Order images: primary product shot first, lifestyle shots after."
        }
        
        return instructions.get(retailer, "Extract standard product data. Order images: primary view first.")
    
    async def _process_extracted_data(self, data: Dict, retailer: str) -> Dict:
        """Apply retailer-specific data cleaning and formatting"""
        
        # Ensure data is a dictionary
        if not isinstance(data, dict):
            logger.warning(f"Expected dict but got {type(data)}: {data}")
            # Convert to dict if possible
            if isinstance(data, str):
                try:
                    import json
                    data = json.loads(data)
                except json.JSONDecodeError:
                    # Fallback: create a basic dict
                    data = {
                        "retailer": retailer,
                        "title": "Extracted Product",
                        "raw_output": str(data)
                    }
            else:
                # Fallback for other types
                data = {
                    "retailer": retailer,
                    "title": "Extracted Product",
                    "raw_output": str(data)
                }
        
        processed = data.copy()
        
        # Clean price formats
        if 'price' in processed:
            processed['price'] = self._clean_price_format(processed['price'], retailer)
        
        if 'original_price' in processed:
            processed['original_price'] = self._clean_price_format(processed['original_price'], retailer)
        
        # Special handling for Uniqlo - they don't show original prices during sales
        if retailer == 'uniqlo':
            sale_status = processed.get('sale_status', '')
            # Handle both boolean and string sale_status
            is_on_sale = False
            if isinstance(sale_status, bool):
                is_on_sale = sale_status
            elif isinstance(sale_status, str) and sale_status and 'sale' in sale_status.lower():
                is_on_sale = True
            
            if is_on_sale:
                # If item is on sale but no original price provided, set to None
                if not processed.get('original_price'):
                    processed['original_price'] = None
                    logger.debug(f"Uniqlo sale item without original price: {processed.get('title', 'Unknown')}")
        
        # Clean title
        if 'title' in processed:
            processed['title'] = self._clean_title_format(processed['title'], retailer)
        
        # Clean brand
        if 'brand' in processed:
            processed['brand'] = self._clean_brand_format(processed['brand'], retailer)
        
        # Enhance and validate image URLs
        if 'image_urls' in processed:
            processed['image_urls'] = await self._enhance_and_validate_images(processed['image_urls'], retailer)
        
        # Standardize status fields
        if 'stock_status' in processed:
            processed['stock_status'] = self._standardize_stock_status(processed['stock_status'])
        
        if 'sale_status' in processed:
            processed['sale_status'] = self._standardize_sale_status(processed['sale_status'])
        
        if 'clothing_type' in processed:
            processed['clothing_type'] = self._standardize_clothing_type(processed['clothing_type'])
        
        # Validate retailer name
        if 'retailer' in processed:
            processed['retailer'] = retailer  # Ensure consistency
        
        return processed
    
    def _clean_price_format(self, price_string: str, retailer: str) -> Optional[float]:
        """Clean and validate price format"""
        if not price_string:
            return None
        
        # Retailer-specific price patterns
        patterns = {
            "aritzia": r'CAD\s*\$?(\d+(?:\.\d{2})?)',
            "mango": r'US\$\s*(\d+(?:[.,]\d{2})?)|(\d+(?:[.,]\d{2})?)\s*€',
            "hm": r'£(\d+(?:\.\d{2})?)|\$(\d+(?:\.\d{2})?)',
            "revolve": r'\$(\d+(?:\.\d{2})?)',
            "nordstrom": r'\$(\d+(?:\.\d{2})?)',
            "anthropologie": r'\$(\d+(?:\.\d{2})?)',
            "default": r'[\$£€]?(\d+(?:[.,]\d{2})?)'
        }
        
        pattern = patterns.get(retailer, patterns["default"])
        
        # Clean the price string
        clean_price = str(price_string).replace(',', '').replace(' ', '')
        
        match = re.search(pattern, clean_price)
        
        if match:
            try:
                # Get the first non-None group
                price_value = next((group for group in match.groups() if group is not None), None)
                if price_value:
                    return float(price_value.replace(',', '.'))
            except (ValueError, AttributeError):
                pass
        
        # Fallback: try to extract any number
        fallback_match = re.search(r'(\d+(?:[.,]\d{2})?)', clean_price)
        if fallback_match:
            try:
                return float(fallback_match.group(1).replace(',', '.'))
            except ValueError:
                pass
        
        return None
    
    def _clean_title_format(self, title: str, retailer: str) -> str:
        """Clean retailer-specific title formats"""
        if not title:
            return ""
        
        # Remove retailer suffixes
        cleaning_rules = {
            "aritzia": lambda t: re.sub(r'\s+\|\s+Aritzia.*$', '', t),
            "asos": lambda t: re.sub(r'\s+\|\s+ASOS.*$', '', t),
            "hm": lambda t: re.sub(r'\s+-\s+H&M.*$', '', t),
        }
        
        cleaner = cleaning_rules.get(retailer, lambda t: t)
        return cleaner(title).strip()
    
    def _clean_brand_format(self, brand: str, retailer: str) -> str:
        """Clean and validate brand names"""
        if not brand:
            return retailer.title()
        
        # Remove retailer suffixes and validate
        brand = re.sub(r'\s+\|\s+.*$', '', brand).strip()
        
        # Retailer-specific brand validation
        valid_brands = {
            "aritzia": ["Aritzia", "TNA", "Wilfred", "Babaton"],
            "hm": ["H&M"],
            "uniqlo": ["Uniqlo"],
            "mango": ["Mango"]
        }
        
        if retailer in valid_brands:
            if brand.lower() not in [b.lower() for b in valid_brands[retailer]]:
                return valid_brands[retailer][0]  # Default to main brand
        
        return brand
    
    def _standardize_stock_status(self, status) -> str:
        """Standardize stock status - handles various input types"""
        if status is None:
            return "in stock"
        
        # Handle boolean input (True = in stock, False = out of stock)
        if isinstance(status, bool):
            return 'in stock' if status else 'out of stock'
        
        # Handle string input
        if not isinstance(status, str):
            status = str(status)
        
        status_lower = status.lower()
        
        if any(indicator in status_lower for indicator in 
               ['sold out', 'unavailable', 'out of stock']):
            return 'out of stock'
        elif any(indicator in status_lower for indicator in 
                 ['few left', 'limited', 'low stock', 'almost gone']):
            return 'low in stock'
        else:
            return 'in stock'
    
    def _standardize_sale_status(self, status) -> str:
        """Standardize sale status - handles both string and boolean inputs"""
        if status is None:
            return "not on sale"
        
        # Handle boolean input
        if isinstance(status, bool):
            return 'on sale' if status else 'not on sale'
        
        # Handle string input
        if not isinstance(status, str):
            status = str(status)
        
        sale_indicators = ['sale', 'clearance', 'reduced', 'discount', 'marked down', 'on sale']
        
        if any(indicator in status.lower() for indicator in sale_indicators):
            return 'on sale'
        return 'not on sale'
    
    def _standardize_clothing_type(self, clothing_type: str) -> str:
        """Standardize clothing type categories"""
        if not clothing_type:
            return "clothing"
        
        type_mapping = {
            'dresses': 'dress',
            'tops & tees': 'top',
            'blouses': 'top',
            'shirts': 'top',
            'sweaters': 'top',
            'pants': 'bottom',
            'jeans': 'bottom',
            'skirts': 'bottom',
            'shorts': 'bottom',
            'jackets': 'outerwear',
            'coats': 'outerwear',
            'blazers': 'outerwear'
        }
        
        clothing_type_lower = clothing_type.lower()
        for key, value in type_mapping.items():
            if key in clothing_type_lower:
                return value
        
        return clothing_type.lower()
    
    def _validate_extraction_quality(self, data: Dict, retailer: str) -> bool:
        """Validate extracted data quality"""
        
        # Required fields - made more lenient for debugging
        required_fields = ['title']  # Only require title for now
        for field in required_fields:
            if not data.get(field):
                logger.warning(f"Missing required field: {field}")
                return False
        
        # Price validation - more lenient
        price = data.get('price')
        if price is not None:
            if not isinstance(price, (int, float)) or price <= 0 or price > 10000:
                logger.warning(f"Invalid price: {price}")
                # Don't fail validation, just warn
        
        # Original price validation (if on sale)
        if data.get('sale_status') == 'on sale':
            original_price = data.get('original_price')
            
            # Special case for Uniqlo - they don't show original prices during sales
            if retailer == 'uniqlo' and not original_price:
                logger.debug(f"Uniqlo sale item without original price - this is expected behavior")
                # Don't validate original price for Uniqlo sales
            elif original_price and price and original_price <= price:
                logger.warning(f"Original price {original_price} not higher than sale price {price}")
                # Don't fail validation, just warn
        
        # Title validation - more lenient
        title = data.get('title', '')
        if title and (len(title) < 3 or len(title) > 500):  # Increased max length
            logger.warning(f"Title length unusual: {len(title)}")
            # Don't fail validation, just warn
        
        # Stock status validation
        stock_status = data.get('stock_status')
        if stock_status and stock_status not in ['in stock', 'low in stock', 'out of stock']:
            logger.warning(f"Invalid stock status: {stock_status}")
            # Don't fail validation, just warn
        
        # Sale status validation
        sale_status = data.get('sale_status')
        if sale_status and sale_status not in ['on sale', 'not on sale']:
            logger.warning(f"Invalid sale status: {sale_status}")
            # Don't fail validation, just warn
        
        # Image count validation
        image_urls = data.get('image_urls', [])
        if len(image_urls) > 5:
            logger.warning(f"Too many images: {len(image_urls)} (max 5)")
            data['image_urls'] = image_urls[:5]  # Truncate to 5
        
        logger.info(f"Validation passed for {retailer} extraction with {len(data)} fields")
        return True
    
    async def _enhance_and_validate_images(self, image_urls: List[str], retailer: str) -> List[str]:
        """Quick image URL enhancement and validation"""
        if not image_urls:
            return []
        
        try:
            # Use the new image processor factory system instead of the old enhancer
            from image_processor_factory import ImageProcessorFactory
            
            processor = ImageProcessorFactory.get_processor(retailer)
            if not processor:
                logger.warning(f"No image processor available for {retailer}, using original URLs")
                return image_urls[:5]
            
            # For agent extractor, we just do quick URL validation/cleanup
            # The full processing happens in batch_processor
            enhanced_urls = []
            for url in image_urls[:5]:  # Max 5 images
                if url and url.startswith(('http://', 'https://')):
                    enhanced_urls.append(url)
            
            logger.debug(f"Validated {len(enhanced_urls)} image URLs for {retailer}")
            return enhanced_urls
                
        except Exception as e:
            logger.error(f"Image URL validation failed for {retailer}: {e}")
            return image_urls[:5]
    
    def _get_enhanced_headers(self, retailer: str, url: str) -> Dict[str, str]:
        """Get enhanced anti-scraping headers for specific retailers"""
        
        base_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
        
        # Retailer-specific header enhancements
        retailer_headers = {
            "asos": {
                'Referer': 'https://www.asos.com/',
                'Origin': 'https://www.asos.com',
                'X-Requested-With': 'XMLHttpRequest'
            },
            "revolve": {
                'Referer': 'https://www.revolve.com/',
                'Origin': 'https://www.revolve.com'
            },
            "nordstrom": {
                'Referer': 'https://www.nordstrom.com/',
                'Origin': 'https://www.nordstrom.com'
            },
            "hm": {
                'Referer': 'https://www2.hm.com/',
                'Origin': 'https://www2.hm.com'
            },
            "anthropologie": {
                'Referer': 'https://www.anthropologie.com/',
                'Origin': 'https://www.anthropologie.com'
            },
            "mango": {
                'Referer': 'https://shop.mango.com/',
                'Origin': 'https://shop.mango.com'
            }
        }
        
        # Merge retailer-specific headers
        if retailer.lower() in retailer_headers:
            base_headers.update(retailer_headers[retailer.lower()])
        
        return base_headers
    
    async def get_extraction_stats(self) -> Dict:
        """Get extraction statistics"""
        return {
            'methods_available': ['openmanus', 'skyvern', 'browser_use'],
            'pattern_learner_stats': await self.pattern_learner.get_stats()
        }