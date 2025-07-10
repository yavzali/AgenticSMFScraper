"""
Unified Extractor - Single agent system replacing both agent_extractor and providing orchestration
Combines markdown extraction, Playwright multi-screenshot, pattern learning, and cost tracking
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))

import json
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import os
import time

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

class UnifiedExtractor:
    """
    Single extraction system that replaces agent_extractor.py
    Routes between markdown and Playwright, includes pattern learning & cost tracking
    """
    
    def __init__(self):
        # Load configuration
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, 'config.json')
        
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.pattern_learner = PatternLearner()
        logger.info("✅ Unified extractor initialized - Playwright + Markdown routing")
    
    async def extract_product_data(self, url: str, retailer: str) -> ExtractionResult:
        """Main extraction method with intelligent routing"""
        start_time = time.time()
        
        try:
            # Get learned patterns
            learned_patterns = await self.pattern_learner.get_learned_patterns(retailer, url)
            
            # ROUTING DECISION: Markdown vs Playwright
            from markdown_extractor import MarkdownExtractor, MARKDOWN_RETAILERS
            
            if retailer in MARKDOWN_RETAILERS:
                # Try markdown first for compatible retailers
                logger.info(f"🔄 Trying markdown extraction for {retailer}: {url}")
                
                try:
                    markdown_extractor = MarkdownExtractor()
                    markdown_result = await markdown_extractor.extract_product_data(url, retailer)
                    
                    if markdown_result.success and not markdown_result.should_fallback:
                        # Markdown succeeded
                        processing_time = time.time() - start_time
                        
                        # Record success and track cost
                        await self.pattern_learner.record_successful_extraction(
                            retailer, url, "markdown_extractor", markdown_result.data
                        )
                        
                        cost_tracker.track_api_call(
                            method="markdown_extractor",
                            prompt=f"Markdown extraction for {retailer}",
                            response={'success': True, 'data': markdown_result.data},
                            retailer=retailer,
                            url=url,
                            processing_time=processing_time
                        )
                        
                        logger.info(f"✅ Markdown extraction successful for {retailer} in {processing_time:.2f}s")
                        return ExtractionResult(
                            success=True,
                            data=markdown_result.data,
                            method_used="markdown_extractor",
                            processing_time=processing_time,
                            warnings=markdown_result.warnings,
                            errors=[]
                        )
                    
                    logger.warning(f"⚠️ Markdown extraction failed for {retailer}, falling back to Playwright")
                    
                except Exception as e:
                    logger.error(f"❌ Markdown extractor error for {retailer}: {e}, falling back to Playwright")
            
            # PLAYWRIGHT EXTRACTION (direct or fallback)
            if retailer not in MARKDOWN_RETAILERS:
                logger.info(f"🎭 Using Playwright extraction for {retailer} (direct route): {url}")
            else:
                logger.info(f"🎭 Using Playwright extraction for {retailer} (fallback from markdown): {url}")
            
            # Build prompt for caching
            prompt = self._build_extraction_prompt(url, retailer, learned_patterns)
            
            # Check cache first
            cached_response = cost_tracker.get_cached_response(prompt)
            if cached_response:
                logger.info(f"📦 Using cached response for {url}")
                processing_time = time.time() - start_time
                
                cost_tracker.track_api_call(
                    method="playwright_agent_cached", 
                    prompt=prompt, 
                    response=cached_response,
                    retailer=retailer, 
                    url=url, 
                    processing_time=processing_time
                )
                
                cached_data = cached_response.get('data', {}) if isinstance(cached_response, dict) else {"retailer": retailer, "raw_output": str(cached_response)}
                
                return ExtractionResult(
                    success=True,
                    data=cached_data,
                    method_used="playwright_agent_cached",
                    processing_time=processing_time,
                    warnings=[],
                    errors=[]
                )
            
            # Perform Playwright extraction
            result = await self._extract_with_playwright(url, retailer, learned_patterns, prompt)
            
            if result.success:
                # Record successful pattern
                await self.pattern_learner.record_successful_extraction(
                    retailer, url, "playwright_agent", result.data
                )
                
                processing_time = time.time() - start_time
                
                # Track API call
                cost_tracker.track_api_call(
                    method="playwright_agent",
                    prompt=prompt, 
                    response={'success': True, 'data': result.data},
                    retailer=retailer,
                    url=url,
                    processing_time=processing_time
                )
                
                logger.info(f"✅ Playwright extraction successful for {retailer} in {processing_time:.2f}s")
                return result
            else:
                # Record failure
                await self.pattern_learner.record_failed_extraction(retailer, url, "playwright_agent", str(result.errors))
                
                # Track failed API call
                cost_tracker.track_api_call(
                    method="playwright_agent",
                    prompt=prompt,
                    response={'success': False, 'error': str(result.errors)},
                    retailer=retailer,
                    url=url,
                    processing_time=time.time() - start_time
                )
                
                logger.error(f"❌ All extraction methods failed for {retailer}")
                return result
            
        except Exception as e:
            logger.error(f"💥 Critical error in extraction for {url}: {e}")
            processing_time = time.time() - start_time
            return ExtractionResult(
                success=False,
                data={},
                method_used="error",
                processing_time=processing_time,
                warnings=[],
                errors=[str(e)]
            )
    
    async def _extract_with_playwright(self, url: str, retailer: str, learned_patterns: dict, prompt: str) -> ExtractionResult:
        """Perform extraction using Playwright multi-screenshot agent"""
        try:
            # Import the Playwright agent
            from playwright_agent import PlaywrightMultiScreenshotAgent
            
            # Initialize and extract
            async with PlaywrightMultiScreenshotAgent(self.config) as agent:
                result = await agent.extract_product(url, retailer)
                return result
            
        except ImportError as e:
            logger.error(f"❌ Playwright agent not available: {e}")
            return ExtractionResult(
                success=False,
                data={},
                method_used="playwright_multi_screenshot",
                processing_time=0,
                warnings=[],
                errors=[f"Playwright agent not available: {e}"]
            )
            
        except Exception as e:
            logger.error(f"❌ Playwright extraction failed: {e}")
            return ExtractionResult(
                success=False,
                data={},
                method_used="playwright_multi_screenshot",
                processing_time=0,
                warnings=[],
                errors=[str(e)]
            )
    
    def _build_extraction_prompt(self, url: str, retailer: str, learned_patterns: List) -> str:
        """Build retailer-specific extraction prompt for caching"""
        base_prompt = f"Extract product data from {url} for {retailer}: title, brand, price, original_price, description, stock_status, sale_status, clothing_type, product_code, image_urls"
        
        # Add retailer-specific instructions
        retailer_instructions = {
            "aritzia": "CAD prices. TNA/Wilfred brands. Sale indicators: compare-at prices.",
            "asos": "Multi-brand. Check designer names. Sale vs original pricing.",
            "hm": "H&M brand. European sizing. Conscious collection indicators.",
            "uniqlo": "Uniqlo/collaboration brands. Limited availability = low stock.",
            "revolve": "Designer brands. Revolve exclusive indicators. Crossed-out prices = sale.",
            "mango": "Mango brand. Outlet vs regular. European price format.",
            "anthropologie": "Anthropologie/Free People brands. Compare-at pricing.",
            "abercrombie": "A&F/Abercrombie brands. Clearance indicators.",
            "nordstrom": "Multi-brand designers. Compare-at sale pricing.",
            "urban_outfitters": "UO/multi-brand. Exclusive indicators."
        }
        
        instruction = retailer_instructions.get(retailer, "Extract standard product data.")
        return f"{base_prompt} {instruction}"
    
    async def get_extraction_stats(self) -> Dict:
        """Get extraction statistics"""
        return {
            'methods_available': ['markdown_extractor', 'playwright_agent'],
            'pattern_learner_stats': await self.pattern_learner.get_stats()
        } 