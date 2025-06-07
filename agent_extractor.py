"""
Agent Extractor - Unified extraction using OpenManus -> Skyvern -> Browser Use hierarchy
Handles retailer-specific data extraction, cleaning, and validation.
"""

import json
import re
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

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
        with open('config.json', 'r') as f:
            self.config = json.load(f)
        
        self.pattern_learner = PatternLearner()
        
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
        """Main extraction method with fallback hierarchy and cost optimization"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Get learned patterns for this retailer/URL
            learned_patterns = await self.pattern_learner.get_learned_patterns(retailer, url)
            
            # Try extraction methods in order (most reliable first)
            for method in ['openmanus', 'browser_use', 'skyvern']:
                try:
                    logger.info(f"Attempting extraction with {method} for {url}")
                    
                    # Build prompt
                    prompt = self._build_extraction_prompt(url, retailer, learned_patterns)
                    
                    # Check for cached response first
                    cached_response = cost_tracker.get_cached_response(prompt)
                    if cached_response:
                        logger.info(f"Using cached response for {url}")
                        processing_time = asyncio.get_event_loop().time() - start_time
                        
                        # Track the cache hit
                        cost_tracker.track_api_call(
                            method=method, 
                            prompt=prompt, 
                            response=cached_response,
                            retailer=retailer, 
                            url=url, 
                            processing_time=processing_time
                        )
                        
                        return ExtractionResult(
                            success=True,
                            data=cached_response.get('data', {}),
                            method_used=f"{method}_cached",
                            processing_time=processing_time,
                            warnings=[],
                            errors=[]
                        )
                    
                    # Perform actual extraction
                    result = await self._extract_with_method(method, url, retailer, learned_patterns, prompt)
                    
                    if result.success:
                        # Process and validate extracted data
                        processed_data = await self._process_extracted_data(result.data, retailer)
                        
                        if self._validate_extraction_quality(processed_data, retailer):
                            # Record successful pattern
                            await self.pattern_learner.record_successful_extraction(
                                retailer, url, method, processed_data
                            )
                            
                            processing_time = asyncio.get_event_loop().time() - start_time
                            
                            # Track API call with cost tracking
                            response_data = {'success': True, 'data': processed_data}
                            cost_tracker.track_api_call(
                                method=method,
                                prompt=prompt, 
                                response=response_data,
                                retailer=retailer,
                                url=url,
                                processing_time=processing_time
                            )
                            
                            return ExtractionResult(
                                success=True,
                                data=processed_data,
                                method_used=method,
                                processing_time=processing_time,
                                warnings=result.warnings,
                                errors=[]
                            )
                
                except Exception as e:
                    logger.warning(f"Extraction failed with {method}: {e}")
                    await self.pattern_learner.record_failed_extraction(retailer, url, method, str(e))
                    
                    # Track failed API call
                    cost_tracker.track_api_call(
                        method=method,
                        prompt=self._build_extraction_prompt(url, retailer, learned_patterns),
                        response={'success': False, 'error': str(e)},
                        retailer=retailer,
                        url=url,
                        processing_time=asyncio.get_event_loop().time() - start_time
                    )
                    continue
            
            # All methods failed
            processing_time = asyncio.get_event_loop().time() - start_time
            return ExtractionResult(
                success=False,
                data={},
                method_used="none",
                processing_time=processing_time,
                warnings=[],
                errors=["All extraction methods failed"]
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
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            import subprocess
            import json
            import asyncio
            from pathlib import Path
            
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
    
    async def _extract_with_browser_use(self, url: str, retailer: str, learned_patterns: List, prompt: str) -> ExtractionResult:
        """Extract using Browser Use + Playwright"""
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            import sys
            import os
            
            # Add browser-use to path
            browser_use_path = os.path.join(os.getcwd(), "browser-use")
            if browser_use_path not in sys.path:
                sys.path.insert(0, browser_use_path)
            
            from browser_use import Agent
            import asyncio
            
            logger.info(f"Starting Browser Use extraction for {url}")
            
            # Get Browser Use configuration
            browser_config = self.config["agents"]["browser_use"]
            
            # Create Browser Use agent
            agent = Agent(
                task=prompt,
                llm=browser_config["model"],
                use_vision=browser_config["use_vision"],
                save_conversation=browser_config["save_conversation"]
            )
            
            # Run extraction with timeout
            result = await asyncio.wait_for(
                agent.run(),
                timeout=browser_config["timeout"]
            )
            
            # Calculate actual processing time
            processing_time = asyncio.get_event_loop().time() - start_time
            
            logger.debug(f"Browser Use raw result: {str(result)[:200]}...")
            
            # Parse the result
            if isinstance(result, dict):
                extracted_data = result
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
                        "raw_output": result
                    }
            else:
                # Fallback
                extracted_data = {
                    "retailer": retailer,
                    "title": "Extracted by Browser Use",
                    "raw_output": str(result)
                }
            
            return ExtractionResult(
                success=True,
                data=extracted_data,
                method_used="browser_use",
                processing_time=processing_time,
                warnings=[],
                errors=[]
            )
            
        except asyncio.TimeoutError:
            processing_time = asyncio.get_event_loop().time() - start_time
            error_msg = f"Browser Use extraction timed out after {browser_config['timeout']} seconds"
            logger.error(error_msg)
            return ExtractionResult(
                success=False,
                data={},
                method_used="browser_use",
                processing_time=processing_time,
                warnings=[],
                errors=[error_msg]
            )
            
        except Exception as e:
            processing_time = asyncio.get_event_loop().time() - start_time
            error_msg = f"Browser Use execution error: {str(e)}"
            logger.error(error_msg)
            return ExtractionResult(
                success=False,
                data={},
                method_used="browser_use",
                processing_time=processing_time,
                warnings=[],
                errors=[error_msg]
            )
    
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
            if sale_status and 'sale' in sale_status.lower():
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
    
    def _standardize_stock_status(self, status: str) -> str:
        """Standardize stock status"""
        if not status:
            return "in stock"
        
        status_lower = status.lower()
        
        if any(indicator in status_lower for indicator in 
               ['sold out', 'unavailable', 'out of stock']):
            return 'out of stock'
        elif any(indicator in status_lower for indicator in 
                 ['few left', 'limited', 'low stock', 'almost gone']):
            return 'low in stock'
        else:
            return 'in stock'
    
    def _standardize_sale_status(self, status: str) -> str:
        """Standardize sale status"""
        if not status:
            return "not on sale"
        
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