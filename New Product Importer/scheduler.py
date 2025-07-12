"""
Scheduler - Handles cost optimization timing and batch scheduling
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
import pytz

from logger_config import setup_logging

logger = setup_logging(__name__)

class CostOptimizer:
    def __init__(self):
        # Load configuration
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, '../Shared/config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        self.scheduling_config = config.get('scheduling', {})
        
        # Cost optimization settings - DISABLED by default since no longer using Deepseek
        self.cost_optimization_enabled = self.scheduling_config.get('cost_optimization_enabled', False)
        self.max_batch_duration = self.scheduling_config.get('max_batch_duration_hours', 8)
        self.discount_hours = self.scheduling_config.get('deepseek_discount_hours', [2, 3, 4, 5, 6, 7])
        
        # Timezone for scheduling (kept for legacy compatibility)
        self.utc_tz = pytz.UTC
        
        logger.info(f"Cost optimizer initialized - Cost optimization: {'ENABLED' if self.cost_optimization_enabled else 'DISABLED'}")
        if self.cost_optimization_enabled:
            logger.info(f"Discount hours: {self.discount_hours} UTC")
        else:
            logger.info("Running 24/7 - no time restrictions")
    
    def is_discount_period(self) -> bool:
        """Check if current time is within discount hours"""
        
        if not self.cost_optimization_enabled:
            return True  # Always allow if cost optimization is disabled
        
        current_utc_hour = datetime.now(self.utc_tz).hour
        is_discount = current_utc_hour in self.discount_hours
        
        logger.debug(f"Current UTC hour: {current_utc_hour}, Discount period: {is_discount}")
        return is_discount
    
    def get_next_discount_time(self) -> datetime:
        """Get the next discount period start time"""
        
        current_utc = datetime.now(self.utc_tz)
        next_discount_hour = min(self.discount_hours)
        
        # Calculate next discount period
        if current_utc.hour < next_discount_hour:
            # Today's discount period hasn't started yet
            next_discount = current_utc.replace(
                hour=next_discount_hour, 
                minute=0, 
                second=0, 
                microsecond=0
            )
        else:
            # Today's discount period has passed, schedule for tomorrow
            tomorrow = current_utc + timedelta(days=1)
            next_discount = tomorrow.replace(
                hour=next_discount_hour, 
                minute=0, 
                second=0, 
                microsecond=0
            )
        
        logger.info(f"Next discount period: {next_discount} UTC")
        return next_discount
    
    def get_discount_time_remaining(self) -> Optional[timedelta]:
        """Get remaining time in current discount period"""
        
        if not self.is_discount_period():
            return None
        
        current_utc = datetime.now(self.utc_tz)
        max_discount_hour = max(self.discount_hours)
        
        # Calculate end of current discount period
        if current_utc.hour <= max_discount_hour:
            discount_end = current_utc.replace(
                hour=max_discount_hour + 1, 
                minute=0, 
                second=0, 
                microsecond=0
            )
        else:
            # Should not happen if is_discount_period() is True
            return timedelta(0)
        
        remaining = discount_end - current_utc
        logger.debug(f"Discount time remaining: {remaining}")
        return remaining
    
    async def wait_for_discount_period(self):
        """Wait until the next discount period begins"""
        
        if self.is_discount_period():
            logger.info("Already in discount period")
            return
        
        next_discount = self.get_next_discount_time()
        current_utc = datetime.now(self.utc_tz)
        wait_time = next_discount - current_utc
        
        logger.info(f"Waiting {wait_time} until discount period starts")
        
        # Wait in smaller chunks to allow for interruption
        total_seconds = wait_time.total_seconds()
        check_interval = 300  # Check every 5 minutes
        
        while total_seconds > 0:
            sleep_time = min(check_interval, total_seconds)
            await asyncio.sleep(sleep_time)
            total_seconds -= sleep_time
            
            # Log progress every hour
            if total_seconds % 3600 < check_interval:
                hours_remaining = total_seconds / 3600
                logger.info(f"Waiting for discount period: {hours_remaining:.1f} hours remaining")
    
    def should_pause_for_cost_optimization(self, batch_start_time: datetime, estimated_remaining_time: timedelta) -> bool:
        """Determine if batch should be paused for cost optimization"""
        
        if not self.cost_optimization_enabled:
            return False
        
        current_utc = datetime.now(self.utc_tz)
        
        # Don't pause if we're in discount period
        if self.is_discount_period():
            return False
        
        # Don't pause if batch just started (give it at least 30 minutes)
        if current_utc - batch_start_time < timedelta(minutes=30):
            return False
        
        # Pause if estimated remaining time extends well into non-discount hours
        next_discount = self.get_next_discount_time()
        batch_would_end = current_utc + estimated_remaining_time
        
        # If batch would end more than 1 hour into non-discount period, pause
        if batch_would_end > next_discount + timedelta(hours=1):
            logger.info("Recommending pause: batch would extend too far into non-discount period")
            return True
        
        return False
    
    def calculate_optimal_batch_size(self, total_urls: int, avg_time_per_url: float = 45.0) -> List[Dict]:
        """Calculate optimal batch sizes to fit within discount periods"""
        
        if not self.cost_optimization_enabled:
            return [{'batch_size': total_urls, 'start_time': 'immediate'}]
        
        # Calculate how many URLs can fit in one discount period
        discount_duration_hours = len(self.discount_hours)
        max_batch_duration_hours = min(discount_duration_hours, self.max_batch_duration)
        
        urls_per_batch = int((max_batch_duration_hours * 3600) / avg_time_per_url)
        
        if total_urls <= urls_per_batch:
            # Single batch fits in one discount period
            return [{
                'batch_size': total_urls,
                'start_time': self.get_next_discount_time().isoformat(),
                'estimated_duration_hours': (total_urls * avg_time_per_url) / 3600
            }]
        
        # Multiple batches needed
        batches = []
        remaining_urls = total_urls
        batch_number = 1
        start_time = self.get_next_discount_time()
        
        while remaining_urls > 0:
            batch_size = min(remaining_urls, urls_per_batch)
            estimated_duration = (batch_size * avg_time_per_url) / 3600
            
            batches.append({
                'batch_number': batch_number,
                'batch_size': batch_size,
                'start_time': start_time.isoformat(),
                'estimated_duration_hours': estimated_duration
            })
            
            remaining_urls -= batch_size
            batch_number += 1
            
            # Next batch starts at next discount period
            start_time += timedelta(days=1)
        
        logger.info(f"Calculated {len(batches)} optimal batches for {total_urls} URLs")
        return batches
    
    async def monitor_batch_timing(self, batch_start_time: datetime, estimated_total_time: timedelta) -> Dict:
        """Monitor batch timing and provide recommendations"""
        
        current_utc = datetime.now(self.utc_tz)
        elapsed_time = current_utc - batch_start_time
        remaining_time = estimated_total_time - elapsed_time
        
        recommendations = {
            'continue_processing': True,
            'recommend_pause': False,
            'time_until_pause': None,
            'estimated_cost_savings': 0,
            'next_discount_period': self.get_next_discount_time().isoformat()
        }
        
        if not self.cost_optimization_enabled:
            return recommendations
        
        # Check if we should recommend pausing
        if self.should_pause_for_cost_optimization(batch_start_time, remaining_time):
            recommendations.update({
                'recommend_pause': True,
                'time_until_pause': timedelta(minutes=5),  # Grace period
                'estimated_cost_savings': self._estimate_cost_savings(remaining_time)
            })
        
        # Check if we're approaching end of discount period
        discount_remaining = self.get_discount_time_remaining()
        if discount_remaining and discount_remaining < remaining_time:
            recommendations.update({
                'recommend_pause': True,
                'time_until_pause': discount_remaining - timedelta(minutes=10),  # Buffer time
                'estimated_cost_savings': self._estimate_cost_savings(remaining_time - discount_remaining)
            })
        
        return recommendations
    
    def _estimate_cost_savings(self, time_in_non_discount: timedelta) -> float:
        """Estimate cost savings from waiting for discount period"""
        
        # Rough estimate: assume $5/hour during non-discount vs $2.50/hour during discount
        non_discount_cost_per_hour = 5.0
        discount_rate = 0.5  # 50% discount
        
        hours = time_in_non_discount.total_seconds() / 3600
        cost_without_optimization = hours * non_discount_cost_per_hour
        cost_with_optimization = hours * non_discount_cost_per_hour * discount_rate
        
        savings = cost_without_optimization - cost_with_optimization
        return round(savings, 2)
    
    def get_schedule_summary(self) -> Dict:
        """Get summary of current scheduling status"""
        
        current_utc = datetime.now(self.utc_tz)
        
        summary = {
            'cost_optimization_enabled': self.cost_optimization_enabled,
            'current_utc_time': current_utc.isoformat(),
            'current_hour': current_utc.hour,
            'discount_hours': self.discount_hours,
            'in_discount_period': self.is_discount_period(),
            'next_discount_period': self.get_next_discount_time().isoformat()
        }
        
        if self.is_discount_period():
            summary['discount_time_remaining'] = str(self.get_discount_time_remaining())
        else:
            next_discount = self.get_next_discount_time()
            summary['time_until_discount'] = str(next_discount - current_utc)
        
        return summary

class BatchScheduler:
    def __init__(self):
        self.cost_optimizer = CostOptimizer()
        self.scheduled_batches = []
    
    async def schedule_batch(self, batch_data: Dict, scheduling_preference: str = 'cost_optimized') -> Dict:
        """Schedule a batch based on preference"""
        
        if scheduling_preference == 'immediate':
            return {
                'action': 'start_immediately',
                'start_time': datetime.now().isoformat(),
                'cost_optimized': False
            }
        
        elif scheduling_preference == 'cost_optimized':
            if self.cost_optimizer.is_discount_period():
                return {
                    'action': 'start_immediately',
                    'start_time': datetime.now().isoformat(),
                    'cost_optimized': True,
                    'reason': 'Currently in discount period'
                }
            else:
                next_discount = self.cost_optimizer.get_next_discount_time()
                return {
                    'action': 'schedule_for_later',
                    'start_time': next_discount.isoformat(),
                    'cost_optimized': True,
                    'wait_time': str(next_discount - datetime.now(pytz.UTC)),
                    'reason': 'Scheduled for next discount period'
                }
        
        elif scheduling_preference == 'specific_time':
            # This would handle user-specified scheduling times
            return {
                'action': 'schedule_for_later',
                'start_time': batch_data.get('scheduled_time'),
                'cost_optimized': False,
                'reason': 'User-specified time'
            }
        
        else:
            raise ValueError(f"Unknown scheduling preference: {scheduling_preference}")
    
    async def check_scheduled_batches(self) -> List[Dict]:
        """Check for batches ready to start"""
        
        ready_batches = []
        current_time = datetime.now(pytz.UTC)
        
        # This would check stored scheduled batches
        # For now, return empty list as implementation depends on storage mechanism
        
        return ready_batches
    
    def get_scheduling_recommendations(self, batch_size: int, estimated_duration_hours: float) -> Dict:
        """Get scheduling recommendations for a batch"""
        
        recommendations = {
            'immediate_start': {
                'recommended': False,
                'reason': '',
                'estimated_cost': 0
            },
            'next_discount_period': {
                'recommended': True,
                'start_time': self.cost_optimizer.get_next_discount_time().isoformat(),
                'estimated_cost': 0,
                'cost_savings': 0
            },
            'optimal_batching': []
        }
        
        # Immediate start analysis
        if self.cost_optimizer.is_discount_period():
            remaining_discount = self.cost_optimizer.get_discount_time_remaining()
            if remaining_discount and remaining_discount.total_seconds() / 3600 >= estimated_duration_hours:
                recommendations['immediate_start'].update({
                    'recommended': True,
                    'reason': 'Can complete within current discount period',
                    'estimated_cost': estimated_duration_hours * 2.5  # Discount rate
                })
            else:
                recommendations['immediate_start'].update({
                    'reason': 'Would extend beyond current discount period'
                })
        else:
            recommendations['immediate_start'].update({
                'reason': 'Currently outside discount period',
                'estimated_cost': estimated_duration_hours * 5.0  # Full rate
            })
        
        # Optimal batching
        optimal_batches = self.cost_optimizer.calculate_optimal_batch_size(batch_size)
        recommendations['optimal_batching'] = optimal_batches
        
        return recommendations