"""
Cost Tracker - Tracks API usage, costs, and optimizes for cost efficiency
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import json
import os
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict

from logger_config import setup_logging

logger = setup_logging(__name__)

@dataclass
class APICall:
    method: str  # openmanus, skyvern, browser_use
    prompt_hash: str
    tokens_used: Optional[int]
    cost: float
    success: bool
    response_cached: bool
    timestamp: str
    retailer: str
    url: str
    processing_time: float

class CostTracker:
    def __init__(self, cost_file: str = "cost_tracking.json"):
        self.cost_file = cost_file
        self.api_calls = []
        self.cost_rates = {
            'openmanus': 0.0,      # Free
            'skyvern': 0.0,        # Free
            'browser_use': 0.0,    # Free
            # Note: Deepseek pricing removed - no longer using Deepseek
        }
        
        # Response cache for deduplication
        self.response_cache = {}
        self.prompt_cache = {}
        
        # Load existing data
        self._load_existing_data()
    
    def track_api_call(self, method: str, prompt: str, response: Dict, 
                      retailer: str, url: str, processing_time: float,
                      tokens_used: Optional[int] = None) -> str:
        """Track API call and return cache key"""
        
        prompt_hash = self._hash_prompt(prompt)
        
        # Check if response was cached
        was_cached = prompt_hash in self.response_cache
        
        # Calculate cost
        cost = self._calculate_cost(method, tokens_used, was_cached)
        
        # Create API call record
        api_call = APICall(
            method=method,
            prompt_hash=prompt_hash,
            tokens_used=tokens_used,
            cost=cost,
            success=bool(response.get('success')),
            response_cached=was_cached,
            timestamp=datetime.utcnow().isoformat(),
            retailer=retailer,
            url=url,
            processing_time=processing_time
        )
        
        self.api_calls.append(api_call)
        
        # Cache successful responses for future deduplication
        if api_call.success and not was_cached:
            self.response_cache[prompt_hash] = {
                'response': response,
                'timestamp': api_call.timestamp,
                'usage_count': 1
            }
        elif was_cached:
            # Increment usage count
            self.response_cache[prompt_hash]['usage_count'] += 1
        
        # Save periodically
        if len(self.api_calls) % 10 == 0:
            self._save_data()
        
        logger.debug(f"Tracked API call: {method} (${cost:.4f}) - Cached: {was_cached}")
        return prompt_hash
    
    def get_cached_response(self, prompt: str) -> Optional[Dict]:
        """Get cached response for identical prompt"""
        prompt_hash = self._hash_prompt(prompt)
        cached = self.response_cache.get(prompt_hash)
        
        if cached:
            # Check if cache is still fresh (24 hours)
            cache_time = datetime.fromisoformat(cached['timestamp'])
            if datetime.utcnow() - cache_time < timedelta(hours=24):
                logger.debug(f"Using cached response for prompt hash: {prompt_hash[:8]}")
                return cached['response']
            else:
                # Remove stale cache
                del self.response_cache[prompt_hash]
        
        return None
    
    def should_use_cache(self, prompt: str, retailer: str) -> bool:
        """Determine if prompt is suitable for caching"""
        
        # Cache if prompt is for same retailer and similar structure
        prompt_pattern = self._extract_prompt_pattern(prompt)
        cache_key = f"{retailer}_{prompt_pattern}"
        
        return cache_key in self.prompt_cache
    
    def get_session_cost(self) -> float:
        """Get total cost for current session (all tracked calls)"""
        return sum(call.cost for call in self.api_calls)
    
    def get_cost_summary(self, days: int = 7) -> Dict:
        """Get cost summary for specified period"""
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        recent_calls = [
            call for call in self.api_calls 
            if datetime.fromisoformat(call.timestamp) > cutoff_date
        ]
        
        if not recent_calls:
            return {'period_days': days, 'total_calls': 0, 'total_cost': 0}
        
        total_cost = sum(call.cost for call in recent_calls)
        total_calls = len(recent_calls)
        successful_calls = sum(1 for call in recent_calls if call.success)
        cached_calls = sum(1 for call in recent_calls if call.response_cached)
        
        # Breakdown by method
        method_breakdown = defaultdict(lambda: {'calls': 0, 'cost': 0, 'success_rate': 0})
        for call in recent_calls:
            method_breakdown[call.method]['calls'] += 1
            method_breakdown[call.method]['cost'] += call.cost
            if call.success:
                method_breakdown[call.method]['success_rate'] += 1
        
        # Calculate success rates
        for method_data in method_breakdown.values():
            if method_data['calls'] > 0:
                method_data['success_rate'] = method_data['success_rate'] / method_data['calls']
        
        # Breakdown by retailer
        retailer_breakdown = defaultdict(lambda: {'calls': 0, 'cost': 0})
        for call in recent_calls:
            retailer_breakdown[call.retailer]['calls'] += 1
            retailer_breakdown[call.retailer]['cost'] += call.cost
        
        return {
            'period_days': days,
            'total_calls': total_calls,
            'total_cost': total_cost,
            'successful_calls': successful_calls,
            'success_rate': successful_calls / total_calls if total_calls > 0 else 0,
            'cached_calls': cached_calls,
            'cache_hit_rate': cached_calls / total_calls if total_calls > 0 else 0,
            'cost_per_success': total_cost / successful_calls if successful_calls > 0 else 0,
            'average_cost_per_call': total_cost / total_calls if total_calls > 0 else 0,
            'by_method': dict(method_breakdown),
            'by_retailer': dict(retailer_breakdown),
            'estimated_savings_from_cache': self._calculate_cache_savings(recent_calls)
        }
    
    def get_optimization_recommendations(self) -> List[str]:
        """Get cost optimization recommendations based on usage patterns"""
        
        recommendations = []
        recent_summary = self.get_cost_summary(days=7)
        
        # Cache hit rate recommendations
        if recent_summary['cache_hit_rate'] < 0.3:
            recommendations.append(
                "Low cache hit rate detected. Consider grouping similar URLs for better caching."
            )
        
        # Success rate recommendations
        if recent_summary['success_rate'] < 0.85:
            recommendations.append(
                "Low success rate detected. Review failed patterns to improve prompts."
            )
        
        # Cost efficiency recommendations
        if recent_summary['cost_per_success'] > 0.01:  # Threshold for concern
            recommendations.append(
                "High cost per success. Consider using more cached responses or optimizing prompts."
            )
        
        # Method efficiency recommendations
        method_data = recent_summary['by_method']
        for method, stats in method_data.items():
            if stats['success_rate'] < 0.7 and stats['calls'] > 5:
                recommendations.append(
                    f"Method '{method}' has low success rate ({stats['success_rate']:.1%}). Consider tuning prompts."
                )
        
        return recommendations
    
    def _hash_prompt(self, prompt: str) -> str:
        """Create hash for prompt deduplication"""
        # Normalize prompt (remove URL-specific parts for better caching)
        normalized = self._normalize_prompt(prompt)
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def _normalize_prompt(self, prompt: str) -> str:
        """Normalize prompt for better caching by removing URL-specific parts"""
        import re
        
        # Replace URLs with placeholder
        normalized = re.sub(r'https?://[^\s]+', '[URL]', prompt)
        
        # Replace specific product codes/IDs with placeholder
        normalized = re.sub(r'\b\d{6,}\b', '[ID]', normalized)
        normalized = re.sub(r'\b[A-Z]{2,}\d+\b', '[CODE]', normalized)
        
        return normalized.lower().strip()
    
    def _extract_prompt_pattern(self, prompt: str) -> str:
        """Extract pattern from prompt for categorization"""
        # Simple pattern extraction - could be more sophisticated
        if 'extract from' in prompt.lower():
            return 'extraction'
        elif 'screenshot' in prompt.lower():
            return 'screenshot'
        else:
            return 'other'
    
    def _calculate_cost(self, method: str, tokens_used: Optional[int], was_cached: bool) -> float:
        """Calculate cost for API call"""
        
        if was_cached:
            return 0.0  # Cached responses are free
        
        if method in ['openmanus', 'skyvern', 'browser_use']:
            return 0.0  # These are free services
        
        # For future paid services (Deepseek logic removed)
        # All current services are free
        return 0.0
    
    def _calculate_cache_savings(self, api_calls: List[APICall]) -> float:
        """Calculate estimated savings from cache usage"""
        cached_calls = [call for call in api_calls if call.response_cached]
        
        # Estimate what these calls would have cost without cache
        estimated_savings = 0.0
        for call in cached_calls:
            if call.tokens_used:
                # Assume regular rate for savings calculation
                estimated_cost = (call.tokens_used / 1000) * 0.002
                estimated_savings += estimated_cost
        
        return estimated_savings
    
    def _load_existing_data(self):
        """Load existing cost tracking data"""
        try:
            if os.path.exists(self.cost_file):
                with open(self.cost_file, 'r') as f:
                    data = json.load(f)
                
                # Load API calls
                for call_data in data.get('api_calls', []):
                    api_call = APICall(**call_data)
                    self.api_calls.append(api_call)
                
                # Load response cache
                self.response_cache = data.get('response_cache', {})
                
                logger.info(f"Loaded {len(self.api_calls)} existing API call records")
        
        except Exception as e:
            logger.error(f"Failed to load existing cost data: {e}")
    
    def _save_data(self):
        """Save cost tracking data"""
        try:
            data = {
                'api_calls': [asdict(call) for call in self.api_calls],
                'response_cache': self.response_cache,
                'last_updated': datetime.utcnow().isoformat()
            }
            
            with open(self.cost_file, 'w') as f:
                json.dump(data, f, indent=2)
        
        except Exception as e:
            logger.error(f"Failed to save cost data: {e}")
    
    def cleanup_old_data(self, days: int = 30):
        """Clean up old cost tracking data"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Remove old API calls
        original_count = len(self.api_calls)
        self.api_calls = [
            call for call in self.api_calls 
            if datetime.fromisoformat(call.timestamp) > cutoff_date
        ]
        
        # Remove old cached responses
        for prompt_hash, cached_data in list(self.response_cache.items()):
            cache_time = datetime.fromisoformat(cached_data['timestamp'])
            if cache_time < cutoff_date:
                del self.response_cache[prompt_hash]
        
        removed_count = original_count - len(self.api_calls)
        if removed_count > 0:
            self._save_data()
            logger.info(f"Cleaned up {removed_count} old API call records")
        
        return removed_count

# Global cost tracker instance
cost_tracker = CostTracker()