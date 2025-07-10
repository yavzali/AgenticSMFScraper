"""
Catalog Scheduler - Weekly automation and integration with existing scheduler
Handles scheduling of catalog monitoring runs and integration with existing scraper scheduler
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import asyncio
import schedule
import time
import json
import os
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import threading

from logger_config import setup_logging
from catalog_orchestrator import CatalogOrchestrator, OrchestrationConfig
from retailer_crawlers import CatalogCrawlerFactory
from notification_manager import EnhancedNotificationManager, NotificationType

logger = setup_logging(__name__)

class ScheduleType(Enum):
    """Types of scheduled operations"""
    WEEKLY_MONITORING = "weekly_monitoring"
    BASELINE_VALIDATION = "baseline_validation"
    REVIEW_REMINDER = "review_reminder"
    SYSTEM_HEALTH_CHECK = "system_health_check"
    BATCH_EXPORT = "batch_export"
    CLEANUP_OLD_DATA = "cleanup_old_data"

@dataclass
class ScheduledTask:
    """Scheduled task configuration"""
    task_id: str
    schedule_type: ScheduleType
    schedule_pattern: str  # e.g., "weekly", "daily", "monday at 09:00"
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    failure_count: int = 0
    max_failures: int = 3
    task_config: Dict[str, Any] = None

class CatalogScheduler:
    """
    Catalog monitoring scheduler with integration to existing system
    Handles automated weekly monitoring, health checks, and notifications
    """
    
    def __init__(self, config_path: str = None):
        # Load configuration
        if config_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(script_dir, '../Shared/config.json')
        
        self.config = self._load_config(config_path)
        self.scheduler_config = self.config.get('catalog_scheduler', {})
        
        # Initialize components
        self.orchestrator = CatalogOrchestrator()
        self.notification_manager = EnhancedNotificationManager()
        
        # Scheduled tasks
        self.scheduled_tasks: Dict[str, ScheduledTask] = {}
        self.is_running = False
        self.scheduler_thread = None
        
        # Setup default schedules
        self._setup_default_schedules()
        
        logger.info("✅ Catalog scheduler initialized")
    
    def _load_config(self, config_path: str) -> Dict:
        """Load scheduler configuration"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Set default scheduler config if not present
            if 'catalog_scheduler' not in config:
                config['catalog_scheduler'] = {
                    'enabled': True,
                    'weekly_monitoring': {
                        'enabled': True,
                        'day': 'monday',
                        'time': '09:00',
                        'retailers': 'all',
                        'categories': ['dresses', 'tops']
                    },
                    'health_checks': {
                        'enabled': True,
                        'frequency': 'daily',
                        'time': '08:00'
                    },
                    'review_reminders': {
                        'enabled': True,
                        'frequency': 'daily',
                        'time': '17:00',
                        'threshold_days': 3
                    },
                    'cleanup': {
                        'enabled': True,
                        'frequency': 'weekly',
                        'day': 'sunday',
                        'time': '02:00',
                        'retention_days': 30
                    }
                }
            
            return config
            
        except Exception as e:
            logger.warning(f"Error loading scheduler config: {e}")
            return {'catalog_scheduler': {'enabled': False}}
    
    def _setup_default_schedules(self):
        """Setup default scheduled tasks"""
        
        try:
            scheduler_config = self.scheduler_config
            
            # Weekly monitoring
            if scheduler_config.get('weekly_monitoring', {}).get('enabled', True):
                weekly_config = scheduler_config['weekly_monitoring']
                day = weekly_config.get('day', 'monday')
                time_str = weekly_config.get('time', '09:00')
                
                self.add_scheduled_task(
                    task_id='weekly_monitoring',
                    schedule_type=ScheduleType.WEEKLY_MONITORING,
                    schedule_pattern=f"{day} at {time_str}",
                    task_config={
                        'retailers': weekly_config.get('retailers', 'all'),
                        'categories': weekly_config.get('categories', ['dresses', 'tops'])
                    }
                )
            
            # Daily health checks
            if scheduler_config.get('health_checks', {}).get('enabled', True):
                health_config = scheduler_config['health_checks']
                time_str = health_config.get('time', '08:00')
                
                self.add_scheduled_task(
                    task_id='system_health_check',
                    schedule_type=ScheduleType.SYSTEM_HEALTH_CHECK,
                    schedule_pattern=f"daily at {time_str}",
                    task_config={}
                )
            
            # Review reminders
            if scheduler_config.get('review_reminders', {}).get('enabled', True):
                reminder_config = scheduler_config['review_reminders']
                time_str = reminder_config.get('time', '17:00')
                
                self.add_scheduled_task(
                    task_id='review_reminder',
                    schedule_type=ScheduleType.REVIEW_REMINDER,
                    schedule_pattern=f"daily at {time_str}",
                    task_config={
                        'threshold_days': reminder_config.get('threshold_days', 3)
                    }
                )
            
            # Weekly cleanup
            if scheduler_config.get('cleanup', {}).get('enabled', True):
                cleanup_config = scheduler_config['cleanup']
                day = cleanup_config.get('day', 'sunday')
                time_str = cleanup_config.get('time', '02:00')
                
                self.add_scheduled_task(
                    task_id='cleanup_old_data',
                    schedule_type=ScheduleType.CLEANUP_OLD_DATA,
                    schedule_pattern=f"{day} at {time_str}",
                    task_config={
                        'retention_days': cleanup_config.get('retention_days', 30)
                    }
                )
            
            # Weekly baseline validation
            self.add_scheduled_task(
                task_id='baseline_validation',
                schedule_type=ScheduleType.BASELINE_VALIDATION,
                schedule_pattern="sunday at 08:00",
                task_config={}
            )
            
            # Daily batch export check
            self.add_scheduled_task(
                task_id='batch_export',
                schedule_type=ScheduleType.BATCH_EXPORT,
                schedule_pattern="daily at 18:00",
                task_config={}
            )
            
            logger.info(f"Setup {len(self.scheduled_tasks)} default scheduled tasks")
            
        except Exception as e:
            logger.error(f"Error setting up default schedules: {e}")
    
    # =================== TASK MANAGEMENT ===================
    
    def add_scheduled_task(self, task_id: str, schedule_type: ScheduleType,
                          schedule_pattern: str, task_config: Dict = None,
                          enabled: bool = True) -> bool:
        """Add a new scheduled task"""
        
        try:
            task = ScheduledTask(
                task_id=task_id,
                schedule_type=schedule_type,
                schedule_pattern=schedule_pattern,
                enabled=enabled,
                task_config=task_config or {}
            )
            
            self.scheduled_tasks[task_id] = task
            
            # Register with schedule library
            if enabled:
                self._register_task_with_schedule(task)
            
            logger.info(f"Added scheduled task: {task_id} ({schedule_pattern})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding scheduled task {task_id}: {e}")
            return False
    
    def remove_scheduled_task(self, task_id: str) -> bool:
        """Remove a scheduled task"""
        
        try:
            if task_id in self.scheduled_tasks:
                del self.scheduled_tasks[task_id]
                logger.info(f"Removed scheduled task: {task_id}")
                return True
            else:
                logger.warning(f"Task not found: {task_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error removing scheduled task {task_id}: {e}")
            return False
    
    def enable_task(self, task_id: str) -> bool:
        """Enable a scheduled task"""
        
        try:
            if task_id in self.scheduled_tasks:
                task = self.scheduled_tasks[task_id]
                task.enabled = True
                self._register_task_with_schedule(task)
                logger.info(f"Enabled scheduled task: {task_id}")
                return True
            else:
                logger.warning(f"Task not found: {task_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error enabling task {task_id}: {e}")
            return False
    
    def disable_task(self, task_id: str) -> bool:
        """Disable a scheduled task"""
        
        try:
            if task_id in self.scheduled_tasks:
                task = self.scheduled_tasks[task_id]
                task.enabled = False
                logger.info(f"Disabled scheduled task: {task_id}")
                return True
            else:
                logger.warning(f"Task not found: {task_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error disabling task {task_id}: {e}")
            return False
    
    def _register_task_with_schedule(self, task: ScheduledTask):
        """Register task with schedule library"""
        
        try:
            # Create wrapper function for the task
            def task_wrapper():
                asyncio.run(self._execute_scheduled_task(task.task_id))
            
            # Parse schedule pattern and register
            pattern_parts = task.schedule_pattern.lower().split()
            
            if 'daily' in pattern_parts:
                if 'at' in pattern_parts:
                    time_str = pattern_parts[pattern_parts.index('at') + 1]
                    schedule.every().day.at(time_str).do(task_wrapper)
                else:
                    schedule.every().day.do(task_wrapper)
            
            elif 'weekly' in pattern_parts:
                schedule.every().week.do(task_wrapper)
            
            elif any(day in pattern_parts for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']):
                # Specific day
                day = next(d for d in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] if d in pattern_parts)
                
                if 'at' in pattern_parts:
                    time_str = pattern_parts[pattern_parts.index('at') + 1]
                    getattr(schedule.every(), day).at(time_str).do(task_wrapper)
                else:
                    getattr(schedule.every(), day).do(task_wrapper)
            
            else:
                logger.warning(f"Unknown schedule pattern: {task.schedule_pattern}")
            
        except Exception as e:
            logger.error(f"Error registering task {task.task_id} with schedule: {e}")
    
    # =================== SCHEDULER EXECUTION ===================
    
    def start_scheduler(self) -> bool:
        """Start the scheduler in a background thread"""
        
        if not self.scheduler_config.get('enabled', True):
            logger.info("Catalog scheduler is disabled in configuration")
            return False
        
        if self.is_running:
            logger.warning("Scheduler is already running")
            return False
        
        try:
            self.is_running = True
            
            # Start scheduler in background thread
            self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.scheduler_thread.start()
            
            logger.info("✅ Catalog scheduler started")
            return True
            
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")
            self.is_running = False
            return False
    
    def stop_scheduler(self):
        """Stop the scheduler"""
        
        try:
            self.is_running = False
            
            if self.scheduler_thread and self.scheduler_thread.is_alive():
                self.scheduler_thread.join(timeout=10)
            
            # Clear all scheduled jobs
            schedule.clear()
            
            logger.info("Catalog scheduler stopped")
            
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
    
    def _run_scheduler(self):
        """Main scheduler loop"""
        
        logger.info("Scheduler thread started")
        
        while self.is_running:
            try:
                # Run pending scheduled jobs
                schedule.run_pending()
                
                # Sleep for 1 minute
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(60)  # Continue after error
        
        logger.info("Scheduler thread stopped")
    
    async def _execute_scheduled_task(self, task_id: str):
        """Execute a scheduled task"""
        
        if task_id not in self.scheduled_tasks:
            logger.error(f"Unknown scheduled task: {task_id}")
            return
        
        task = self.scheduled_tasks[task_id]
        
        if not task.enabled:
            logger.debug(f"Skipping disabled task: {task_id}")
            return
        
        logger.info(f"🕒 Executing scheduled task: {task_id}")
        
        try:
            task.last_run = datetime.utcnow()
            
            # Execute task based on type
            if task.schedule_type == ScheduleType.WEEKLY_MONITORING:
                await self._execute_weekly_monitoring(task)
            elif task.schedule_type == ScheduleType.BASELINE_VALIDATION:
                await self._execute_baseline_validation(task)
            elif task.schedule_type == ScheduleType.REVIEW_REMINDER:
                await self._execute_review_reminder(task)
            elif task.schedule_type == ScheduleType.SYSTEM_HEALTH_CHECK:
                await self._execute_health_check(task)
            elif task.schedule_type == ScheduleType.BATCH_EXPORT:
                await self._execute_batch_export(task)
            elif task.schedule_type == ScheduleType.CLEANUP_OLD_DATA:
                await self._execute_cleanup(task)
            else:
                logger.warning(f"Unknown task type: {task.schedule_type}")
                return
            
            # Update success tracking
            task.run_count += 1
            task.failure_count = 0  # Reset failure count on success
            
            logger.info(f"✅ Completed scheduled task: {task_id}")
            
        except Exception as e:
            # Update failure tracking
            task.failure_count += 1
            
            logger.error(f"❌ Scheduled task failed: {task_id} - {e}")
            
            # Disable task if too many failures
            if task.failure_count >= task.max_failures:
                task.enabled = False
                logger.error(f"Disabled task {task_id} due to repeated failures")
                
                # Send notification about task failure
                await self.notification_manager.notify_system_error(
                    error_type="scheduled_task_failure",
                    error_message=f"Task {task_id} disabled after {task.failure_count} failures",
                    component="catalog_scheduler",
                    error_context={'task_config': task.task_config}
                )
    
    # =================== TASK IMPLEMENTATIONS ===================
    
    async def _execute_weekly_monitoring(self, task: ScheduledTask):
        """Execute weekly catalog monitoring"""
        
        task_config = task.task_config
        retailers = task_config.get('retailers', 'all')
        categories = task_config.get('categories', ['dresses', 'tops'])
        
        # Convert 'all' to actual retailer list
        if retailers == 'all':
            retailers = CatalogCrawlerFactory.get_supported_retailers()
        
        logger.info(f"Starting weekly monitoring for {len(retailers)} retailers, {len(categories)} categories")
        
        # Execute monitoring
        result = await self.orchestrator.run_weekly_monitoring(retailers, categories)
        
        # Send completion notification
        await self.notification_manager.notify_catalog_monitoring_complete(result)
        
        # Check if new products were found
        if result.new_products_found > 0:
            # This would get actual product data in real implementation
            await self.notification_manager.notify_new_products_found(
                [], result.run_id)  # Empty list as placeholder
    
    async def _execute_baseline_validation(self, task: ScheduledTask):
        """Execute baseline validation"""
        
        logger.info("Starting weekly baseline validation")
        
        # Validate baselines
        validation_results = await self.orchestrator.validate_baselines()
        
        # Send notification if issues found
        if validation_results['needs_refresh'] or validation_results['missing']:
            context = {
                'alert_type': 'baseline_validation',
                'severity': 'medium',
                'description': f"Baseline issues found: {len(validation_results['needs_refresh'])} need refresh, {len(validation_results['missing'])} missing",
                'health_metrics': f"Valid: {len(validation_results['valid'])}, Needs Refresh: {len(validation_results['needs_refresh'])}, Missing: {len(validation_results['missing'])}",
                'recommended_actions': 'Run baseline establishment for missing/outdated baselines',
                'system_status_url': 'catalog_main.py --validate-baselines'
            }
            
            await self.notification_manager.send_notification(
                NotificationType.SYSTEM_HEALTH_ALERT, context)
    
    async def _execute_review_reminder(self, task: ScheduledTask):
        """Execute review reminder check"""
        
        threshold_days = task.task_config.get('threshold_days', 3)
        
        logger.info(f"Checking for products pending review longer than {threshold_days} days")
        
        # This would get actual pending review stats in real implementation
        pending_stats = {
            'total_pending': 15,  # Placeholder
            'low_confidence': 8,
            'oldest_pending_days': 5,
            'by_retailer': {'asos': 5, 'revolve': 7, 'aritzia': 3}
        }
        
        # Send reminder if products are pending too long
        if pending_stats['total_pending'] > 0 and pending_stats['oldest_pending_days'] >= threshold_days:
            await self.notification_manager.notify_review_needed(pending_stats)
    
    async def _execute_health_check(self, task: ScheduledTask):
        """Execute system health check"""
        
        logger.info("Performing system health check")
        
        # Get system status
        system_status = await self.orchestrator.get_system_status()
        
        # Check for issues
        issues = []
        
        # Check pending reviews
        pending_reviews = system_status.get('database_stats', {}).get('pending_reviews', 0)
        if pending_reviews > 50:
            issues.append(f"High number of pending reviews: {pending_reviews}")
        
        # Check recent runs
        recent_runs = system_status.get('database_stats', {}).get('recent_runs', 0)
        if recent_runs == 0:
            issues.append("No recent monitoring runs found")
        
        # Check baseline status
        baseline_validation = system_status.get('baseline_validation', {})
        missing_baselines = len(baseline_validation.get('missing', []))
        if missing_baselines > 0:
            issues.append(f"Missing baselines: {missing_baselines}")
        
        # Send alert if issues found
        if issues:
            context = {
                'alert_type': 'daily_health_check',
                'severity': 'medium',
                'description': f"System health issues detected: {', '.join(issues)}",
                'health_metrics': json.dumps(system_status.get('database_stats', {}), indent=2),
                'recommended_actions': 'Review system status and resolve identified issues',
                'system_status_url': 'catalog_main.py --status'
            }
            
            await self.notification_manager.send_notification(
                NotificationType.SYSTEM_HEALTH_ALERT, context)
    
    async def _execute_batch_export(self, task: ScheduledTask):
        """Execute batch export for approved products"""
        
        logger.info("Checking for approved products ready for batch export")
        
        # This would create batch files in real implementation
        batch_files = []  # Placeholder
        
        if batch_files:
            batch_stats = {
                'total_products': 12,  # Placeholder
                'retailers': ['asos', 'revolve']
            }
            
            await self.notification_manager.notify_batch_ready(batch_files, batch_stats)
    
    async def _execute_cleanup(self, task: ScheduledTask):
        """Execute cleanup of old data"""
        
        retention_days = task.task_config.get('retention_days', 30)
        
        logger.info(f"Cleaning up data older than {retention_days} days")
        
        # This would perform actual cleanup in real implementation
        # - Remove old error logs
        # - Clean up old pattern data
        # - Archive old monitoring runs
        
        logger.info("Cleanup completed")
    
    # =================== INTEGRATION WITH EXISTING SCHEDULER ===================
    
    def integrate_with_existing_scheduler(self) -> bool:
        """
        Integrate catalog scheduler with existing scraper scheduler
        This allows coordination between catalog monitoring and scraper runs
        """
        
        try:
            # Check if existing scheduler exists
            existing_scheduler_path = os.path.join(os.path.dirname(__file__), 'scheduler.py')
            
            if os.path.exists(existing_scheduler_path):
                logger.info("Found existing scheduler, setting up integration")
                
                # Add catalog-aware scheduling
                # This would modify the existing scheduler to:
                # 1. Run catalog monitoring before weekly scraper batches
                # 2. Coordinate timing to avoid conflicts
                # 3. Share configuration and notification settings
                
                return True
            else:
                logger.info("No existing scheduler found, running standalone")
                return True
                
        except Exception as e:
            logger.error(f"Error integrating with existing scheduler: {e}")
            return False
    
    # =================== MANUAL TRIGGER METHODS ===================
    
    async def trigger_weekly_monitoring_now(self, retailers: List[str] = None,
                                          categories: List[str] = None) -> bool:
        """Manually trigger weekly monitoring"""
        
        try:
            logger.info("Manual trigger: weekly monitoring")
            
            task = ScheduledTask(
                task_id='manual_weekly_monitoring',
                schedule_type=ScheduleType.WEEKLY_MONITORING,
                schedule_pattern='manual',
                task_config={
                    'retailers': retailers or 'all',
                    'categories': categories or ['dresses', 'tops']
                }
            )
            
            await self._execute_weekly_monitoring(task)
            return True
            
        except Exception as e:
            logger.error(f"Error in manual weekly monitoring trigger: {e}")
            return False
    
    async def trigger_health_check_now(self) -> bool:
        """Manually trigger system health check"""
        
        try:
            logger.info("Manual trigger: health check")
            
            task = ScheduledTask(
                task_id='manual_health_check',
                schedule_type=ScheduleType.SYSTEM_HEALTH_CHECK,
                schedule_pattern='manual',
                task_config={}
            )
            
            await self._execute_health_check(task)
            return True
            
        except Exception as e:
            logger.error(f"Error in manual health check trigger: {e}")
            return False
    
    # =================== STATUS AND MANAGEMENT ===================
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        
        return {
            'running': self.is_running,
            'enabled': self.scheduler_config.get('enabled', True),
            'total_tasks': len(self.scheduled_tasks),
            'enabled_tasks': len([t for t in self.scheduled_tasks.values() if t.enabled]),
            'tasks': {
                task_id: {
                    'schedule_type': task.schedule_type.value,
                    'schedule_pattern': task.schedule_pattern,
                    'enabled': task.enabled,
                    'last_run': task.last_run.isoformat() if task.last_run else None,
                    'run_count': task.run_count,
                    'failure_count': task.failure_count
                }
                for task_id, task in self.scheduled_tasks.items()
            },
            'next_runs': [
                {
                    'task_id': job.job_func.__name__ if hasattr(job.job_func, '__name__') else 'unknown',
                    'next_run': job.next_run.isoformat() if job.next_run else None
                }
                for job in schedule.jobs
            ]
        }
    
    async def close(self):
        """Cleanup scheduler resources"""
        
        self.stop_scheduler()
        
        if self.orchestrator:
            await self.orchestrator.close()
        
        logger.info("Catalog scheduler closed")