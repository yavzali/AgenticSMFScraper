"""
Updated Notification Manager - Enhanced for catalog monitoring alerts
Supports both existing scraper notifications and new catalog monitoring notifications
"""

import asyncio
import smtplib
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from logger_config import setup_logging

logger = setup_logging(__name__)

class NotificationType(Enum):
    """Types of notifications the system can send"""
    BATCH_COMPLETION = "batch_completion"
    BATCH_ERROR = "batch_error"
    CATALOG_MONITORING_COMPLETE = "catalog_monitoring_complete"
    CATALOG_BASELINE_ESTABLISHED = "catalog_baseline_established"
    CATALOG_NEW_PRODUCTS_FOUND = "catalog_new_products_found"
    CATALOG_REVIEW_NEEDED = "catalog_review_needed"
    CATALOG_SYSTEM_ERROR = "catalog_system_error"
    CATALOG_BATCH_READY = "catalog_batch_ready"
    SYSTEM_HEALTH_ALERT = "system_health_alert"

@dataclass
class NotificationTemplate:
    """Template for notification content"""
    subject_template: str
    message_template: str
    priority: str  # 'low', 'medium', 'high', 'critical'
    recipients: List[str]
    html_template: Optional[str] = None

class EnhancedNotificationManager:
    """
    Enhanced notification manager supporting both existing scraper 
    and new catalog monitoring notifications
    """
    
    def __init__(self, config_path: str = None):
        # Load configuration
        if config_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(script_dir, 'config.json')
        
        self.config = self._load_config(config_path)
        self.email_config = self.config.get('email', {})
        self.notification_config = self.config.get('notifications', {})
        
        # Notification templates
        self.templates = self._load_notification_templates()
        
        logger.info("✅ Enhanced notification manager initialized")
    
    def _load_config(self, config_path: str) -> Dict:
        """Load notification configuration"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Set defaults if not present
            if 'notifications' not in config:
                config['notifications'] = {
                    'enabled': True,
                    'default_recipients': ['user@example.com'],
                    'smtp_settings': {
                        'server': 'smtp.gmail.com',
                        'port': 587,
                        'use_tls': True
                    }
                }
            
            return config
            
        except Exception as e:
            logger.warning(f"Error loading notification config: {e}")
            return {'notifications': {'enabled': False}}
    
    def _load_notification_templates(self) -> Dict[NotificationType, NotificationTemplate]:
        """Load notification templates for different types"""
        
        templates = {
            # Existing scraper notifications
            NotificationType.BATCH_COMPLETION: NotificationTemplate(
                subject_template="✅ Scraper Batch Completed - {batch_name}",
                message_template="""
Scraper batch completed successfully:

Batch: {batch_name}
URLs Processed: {urls_processed}
Success Rate: {success_rate}%
Processing Time: {processing_time}
Total Cost: ${total_cost:.2f}

Products uploaded to Shopify: {products_uploaded}
Manual review needed: {manual_review_count}

View results: {batch_file}
""",
                priority="medium",
                recipients=self.notification_config.get('default_recipients', []),
                html_template=self._get_batch_completion_html_template()
            ),
            
            NotificationType.BATCH_ERROR: NotificationTemplate(
                subject_template="❌ Scraper Batch Error - {batch_name}",
                message_template="""
Scraper batch encountered errors:

Batch: {batch_name}
Error Type: {error_type}
Error Message: {error_message}
URLs Processed: {urls_processed}
Success Rate: {success_rate}%

Please check logs and retry if necessary.

Log file: {log_file}
""",
                priority="high",
                recipients=self.notification_config.get('default_recipients', [])
            ),
            
            # New catalog monitoring notifications
            NotificationType.CATALOG_MONITORING_COMPLETE: NotificationTemplate(
                subject_template="🕷️ Catalog Monitoring Complete - {run_type}",
                message_template="""
Catalog monitoring run completed:

Run Type: {run_type}
Run ID: {run_id}
Retailers Processed: {retailers_processed}
Total Products Crawled: {total_products_crawled}
New Products Found: {new_products_found}
Products for Review: {products_for_review}
Processing Time: {processing_time:.1f}s
Total Cost: ${total_cost:.2f}

{batch_files_info}

Next Steps:
- Review new products: Open modesty_review_interface.html
{integration_commands}

Dashboard: {dashboard_url}
""",
                priority="medium",
                recipients=self.notification_config.get('default_recipients', []),
                html_template=self._get_catalog_monitoring_html_template()
            ),
            
            NotificationType.CATALOG_BASELINE_ESTABLISHED: NotificationTemplate(
                subject_template="📋 Catalog Baseline Established - {retailer} {category}",
                message_template="""
Catalog baseline has been successfully established:

Retailer: {retailer}
Category: {category}
Total Products Seen: {total_products}
Crawl Pages: {crawl_pages}
Baseline Date: {baseline_date}
Processing Time: {processing_time:.1f}s

This baseline will be used for future new product detection.
You can now run weekly monitoring for this retailer/category.

Command to run monitoring:
python catalog_main.py --weekly-monitoring --retailers {retailer} --categories {category}
""",
                priority="low",
                recipients=self.notification_config.get('default_recipients', [])
            ),
            
            NotificationType.CATALOG_NEW_PRODUCTS_FOUND: NotificationTemplate(
                subject_template="🆕 New Products Found - {new_product_count} products",
                message_template="""
New products have been discovered during catalog monitoring:

Total New Products: {new_product_count}
Retailers: {retailers_with_new_products}
Discovery Run: {run_id}
Discovery Date: {discovery_date}

Product Summary:
{product_summary}

These products are now pending modesty review.

Review Interface: modesty_review_interface.html
Or use: python catalog_main.py --pending-reviews
""",
                priority="high",
                recipients=self.notification_config.get('default_recipients', []),
                html_template=self._get_new_products_html_template()
            ),
            
            NotificationType.CATALOG_REVIEW_NEEDED: NotificationTemplate(
                subject_template="🔍 Products Pending Review - {pending_count} items",
                message_template="""
Products are pending modesty review:

Total Pending: {pending_count}
Low Confidence Items: {low_confidence_count}
Days Since Discovery: {oldest_pending_days}

Breakdown by Retailer:
{retailer_breakdown}

Please review these products to keep the catalog monitoring system current.

Review Interface: modesty_review_interface.html
Command: python catalog_main.py --pending-reviews
""",
                priority="medium",
                recipients=self.notification_config.get('default_recipients', [])
            ),
            
            NotificationType.CATALOG_BATCH_READY: NotificationTemplate(
                subject_template="📦 Catalog Batch Ready - {batch_count} batch files",
                message_template="""
Approved catalog products have been prepared for scraping:

Batch Files Created: {batch_count}
Total Products: {total_products}
Retailers: {retailers}

Files Created:
{batch_files_list}

Integration Commands:
{integration_commands}

These products will be processed by the existing scraper system.
""",
                priority="high",
                recipients=self.notification_config.get('default_recipients', [])
            ),
            
            NotificationType.CATALOG_SYSTEM_ERROR: NotificationTemplate(
                subject_template="🚨 Catalog System Error - {error_type}",
                message_template="""
Catalog monitoring system encountered an error:

Error Type: {error_type}
Error Message: {error_message}
Component: {component}
Timestamp: {timestamp}
Run ID: {run_id}

Context:
{error_context}

Logs: {log_file}

Please investigate and resolve the issue.
""",
                priority="critical",
                recipients=self.notification_config.get('default_recipients', [])
            ),
            
            NotificationType.SYSTEM_HEALTH_ALERT: NotificationTemplate(
                subject_template="⚠️ System Health Alert - {alert_type}",
                message_template="""
System health alert:

Alert Type: {alert_type}
Severity: {severity}
Description: {description}

Metrics:
{health_metrics}

Recommended Actions:
{recommended_actions}

System Status: {system_status_url}
""",
                priority="high",
                recipients=self.notification_config.get('default_recipients', [])
            )
        }
        
        return templates
    
    # =================== MAIN NOTIFICATION INTERFACE ===================
    
    async def send_notification(self, notification_type: NotificationType, 
                              context: Dict[str, Any],
                              custom_recipients: List[str] = None) -> bool:
        """
        Send notification of specified type with context data
        
        Args:
            notification_type: Type of notification to send
            context: Data to populate notification template
            custom_recipients: Override default recipients
            
        Returns:
            True if notification sent successfully
        """
        
        if not self.notification_config.get('enabled', True):
            logger.debug("Notifications disabled in configuration")
            return True
        
        try:
            template = self.templates.get(notification_type)
            if not template:
                logger.error(f"No template found for notification type: {notification_type}")
                return False
            
            # Prepare notification content
            subject = template.subject_template.format(**context)
            message = template.message_template.format(**context)
            recipients = custom_recipients or template.recipients
            
            # Send notification
            success = await self._send_email_notification(
                subject, message, recipients, template.html_template, context)
            
            if success:
                logger.info(f"✅ Sent {notification_type.value} notification to {len(recipients)} recipients")
            else:
                logger.error(f"❌ Failed to send {notification_type.value} notification")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending notification {notification_type.value}: {e}")
            return False
    
    # =================== CATALOG-SPECIFIC NOTIFICATION METHODS ===================
    
    async def notify_catalog_monitoring_complete(self, orchestration_result) -> bool:
        """Notify when catalog monitoring run completes"""
        
        # Prepare batch files info
        batch_files_info = ""
        integration_commands = ""
        
        if orchestration_result.batch_files_created:
            batch_files_info = f"Batch Files Created: {len(orchestration_result.batch_files_created)}\n"
            batch_files_info += "\n".join([f"  - {bf}" for bf in orchestration_result.batch_files_created])
            
            integration_commands = "\nIntegration Commands:"
            for batch_file in orchestration_result.batch_files_created:
                integration_commands += f"\n  python main_scraper.py --batch-file {batch_file}"
        else:
            batch_files_info = "No batch files created (no approved products ready)"
            integration_commands = ""
        
        context = {
            'run_type': orchestration_result.run_type,
            'run_id': orchestration_result.run_id,
            'retailers_processed': ', '.join(orchestration_result.retailers_processed),
            'total_products_crawled': orchestration_result.total_products_crawled,
            'new_products_found': orchestration_result.new_products_found,
            'products_for_review': orchestration_result.products_for_review,
            'processing_time': orchestration_result.processing_time,
            'total_cost': orchestration_result.total_cost,
            'batch_files_info': batch_files_info,
            'integration_commands': integration_commands,
            'dashboard_url': 'modesty_review_interface.html'
        }
        
        return await self.send_notification(
            NotificationType.CATALOG_MONITORING_COMPLETE, context)
    
    async def notify_baseline_established(self, retailer: str, category: str, 
                                        baseline_data: Dict) -> bool:
        """Notify when catalog baseline is established"""
        
        context = {
            'retailer': retailer,
            'category': category,
            'total_products': baseline_data.get('total_products', 0),
            'crawl_pages': baseline_data.get('crawl_pages', 0),
            'baseline_date': baseline_data.get('baseline_date', datetime.utcnow().strftime('%Y-%m-%d')),
            'processing_time': baseline_data.get('processing_time', 0.0)
        }
        
        return await self.send_notification(
            NotificationType.CATALOG_BASELINE_ESTABLISHED, context)
    
    async def notify_new_products_found(self, new_products: List[Dict], run_id: str) -> bool:
        """Notify when new products are discovered"""
        
        # Prepare product summary
        retailer_summary = {}
        for product in new_products:
            retailer = product.get('retailer', 'unknown')
            if retailer not in retailer_summary:
                retailer_summary[retailer] = {'count': 0, 'categories': set()}
            retailer_summary[retailer]['count'] += 1
            retailer_summary[retailer]['categories'].add(product.get('category', 'unknown'))
        
        product_summary = ""
        for retailer, data in retailer_summary.items():
            categories = ', '.join(data['categories'])
            product_summary += f"  {retailer}: {data['count']} products ({categories})\n"
        
        context = {
            'new_product_count': len(new_products),
            'retailers_with_new_products': ', '.join(retailer_summary.keys()),
            'run_id': run_id,
            'discovery_date': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
            'product_summary': product_summary.strip()
        }
        
        return await self.send_notification(
            NotificationType.CATALOG_NEW_PRODUCTS_FOUND, context)
    
    async def notify_review_needed(self, pending_stats: Dict) -> bool:
        """Notify when products need review"""
        
        # Prepare retailer breakdown
        retailer_breakdown = ""
        if 'by_retailer' in pending_stats:
            for retailer, count in pending_stats['by_retailer'].items():
                retailer_breakdown += f"  {retailer}: {count} products\n"
        
        context = {
            'pending_count': pending_stats.get('total_pending', 0),
            'low_confidence_count': pending_stats.get('low_confidence', 0),
            'oldest_pending_days': pending_stats.get('oldest_pending_days', 0),
            'retailer_breakdown': retailer_breakdown.strip()
        }
        
        return await self.send_notification(
            NotificationType.CATALOG_REVIEW_NEEDED, context)
    
    async def notify_batch_ready(self, batch_files: List[str], 
                               batch_stats: Dict) -> bool:
        """Notify when catalog batch files are ready"""
        
        batch_files_list = "\n".join([f"  - {bf}" for bf in batch_files])
        
        integration_commands = ""
        for batch_file in batch_files:
            integration_commands += f"\n  python main_scraper.py --batch-file {batch_file}"
        
        context = {
            'batch_count': len(batch_files),
            'total_products': batch_stats.get('total_products', 0),
            'retailers': ', '.join(batch_stats.get('retailers', [])),
            'batch_files_list': batch_files_list,
            'integration_commands': integration_commands.strip()
        }
        
        return await self.send_notification(
            NotificationType.CATALOG_BATCH_READY, context)
    
    async def notify_system_error(self, error_type: str, error_message: str,
                                component: str, run_id: str = None,
                                error_context: Dict = None) -> bool:
        """Notify when system error occurs"""
        
        context = {
            'error_type': error_type,
            'error_message': error_message,
            'component': component,
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'run_id': run_id or 'N/A',
            'error_context': json.dumps(error_context or {}, indent=2),
            'log_file': 'logs/catalog_errors.log'
        }
        
        return await self.send_notification(
            NotificationType.CATALOG_SYSTEM_ERROR, context)
    
    # =================== EXISTING SCRAPER COMPATIBILITY ===================
    
    async def notify_batch_completion(self, batch_name: str, batch_stats: Dict) -> bool:
        """Notify when scraper batch completes (existing functionality)"""
        
        context = {
            'batch_name': batch_name,
            'urls_processed': batch_stats.get('urls_processed', 0),
            'success_rate': batch_stats.get('success_rate', 0),
            'processing_time': batch_stats.get('processing_time', '0s'),
            'total_cost': batch_stats.get('total_cost', 0.0),
            'products_uploaded': batch_stats.get('products_uploaded', 0),
            'manual_review_count': batch_stats.get('manual_review_count', 0),
            'batch_file': batch_stats.get('batch_file', 'N/A')
        }
        
        return await self.send_notification(
            NotificationType.BATCH_COMPLETION, context)
    
    async def notify_batch_error(self, batch_name: str, error_info: Dict) -> bool:
        """Notify when scraper batch has errors (existing functionality)"""
        
        context = {
            'batch_name': batch_name,
            'error_type': error_info.get('error_type', 'Unknown'),
            'error_message': error_info.get('error_message', 'No details'),
            'urls_processed': error_info.get('urls_processed', 0),
            'success_rate': error_info.get('success_rate', 0),
            'log_file': error_info.get('log_file', 'logs/errors.log')
        }
        
        return await self.send_notification(
            NotificationType.BATCH_ERROR, context)
    
    # =================== EMAIL SENDING IMPLEMENTATION ===================
    
    async def _send_email_notification(self, subject: str, message: str,
                                     recipients: List[str], html_template: str = None,
                                     context: Dict = None) -> bool:
        """Send email notification"""
        
        try:
            if not self.email_config.get('enabled', True):
                logger.debug("Email notifications disabled")
                return True
            
            # SMTP configuration
            smtp_server = self.email_config.get('smtp_server', 'smtp.gmail.com')
            smtp_port = self.email_config.get('smtp_port', 587)
            use_tls = self.email_config.get('use_tls', True)
            username = self.email_config.get('username')
            password = self.email_config.get('password')
            from_email = self.email_config.get('from_email', username)
            
            if not username or not password:
                logger.warning("Email credentials not configured")
                return False
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = from_email
            msg['To'] = ', '.join(recipients)
            
            # Add plain text part
            text_part = MIMEText(message, 'plain')
            msg.attach(text_part)
            
            # Add HTML part if template provided
            if html_template and context:
                html_content = html_template.format(**context)
                html_part = MIMEText(html_content, 'html')
                msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if use_tls:
                    server.starttls()
                server.login(username, password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False
    
    # =================== HTML TEMPLATES ===================
    
    def _get_batch_completion_html_template(self) -> str:
        """HTML template for batch completion notifications"""
        return """
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center;">
                <h1>✅ Scraper Batch Completed</h1>
                <h2>{batch_name}</h2>
            </div>
            <div style="padding: 20px;">
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                    <h3>📊 Batch Statistics</h3>
                    <ul style="list-style-type: none; padding: 0;">
                        <li><strong>URLs Processed:</strong> {urls_processed}</li>
                        <li><strong>Success Rate:</strong> {success_rate}%</li>
                        <li><strong>Processing Time:</strong> {processing_time}</li>
                        <li><strong>Total Cost:</strong> ${total_cost:.2f}</li>
                    </ul>
                </div>
                <div style="background: #e7f5e7; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                    <h3>🏪 Shopify Results</h3>
                    <ul style="list-style-type: none; padding: 0;">
                        <li><strong>Products Uploaded:</strong> {products_uploaded}</li>
                        <li><strong>Manual Review Needed:</strong> {manual_review_count}</li>
                    </ul>
                </div>
                <div style="text-align: center; margin-top: 20px;">
                    <a href="file:///{batch_file}" style="background: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Batch File</a>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _get_catalog_monitoring_html_template(self) -> str:
        """HTML template for catalog monitoring completion"""
        return """
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center;">
                <h1>🕷️ Catalog Monitoring Complete</h1>
                <h2>{run_type}</h2>
            </div>
            <div style="padding: 20px;">
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                    <h3>📊 Monitoring Results</h3>
                    <ul style="list-style-type: none; padding: 0;">
                        <li><strong>Run ID:</strong> {run_id}</li>
                        <li><strong>Retailers:</strong> {retailers_processed}</li>
                        <li><strong>Products Crawled:</strong> {total_products_crawled}</li>
                        <li><strong>New Products:</strong> {new_products_found}</li>
                        <li><strong>Pending Review:</strong> {products_for_review}</li>
                        <li><strong>Processing Time:</strong> {processing_time:.1f}s</li>
                        <li><strong>Cost:</strong> ${total_cost:.2f}</li>
                    </ul>
                </div>
                <div style="background: #e7f5e7; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                    <h3>📦 Next Steps</h3>
                    <p><strong>Review new products:</strong> Open modesty_review_interface.html</p>
                    {integration_commands}
                </div>
                <div style="text-align: center; margin-top: 20px;">
                    <a href="{dashboard_url}" style="background: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Open Review Interface</a>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _get_new_products_html_template(self) -> str:
        """HTML template for new products found notification"""
        return """
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); color: white; padding: 20px; text-align: center;">
                <h1>🆕 New Products Found</h1>
                <h2>{new_product_count} Products Discovered</h2>
            </div>
            <div style="padding: 20px;">
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                    <h3>📋 Discovery Summary</h3>
                    <ul style="list-style-type: none; padding: 0;">
                        <li><strong>Total Products:</strong> {new_product_count}</li>
                        <li><strong>Retailers:</strong> {retailers_with_new_products}</li>
                        <li><strong>Run ID:</strong> {run_id}</li>
                        <li><strong>Discovery Date:</strong> {discovery_date}</li>
                    </ul>
                </div>
                <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                    <h3>🏪 Product Breakdown</h3>
                    <pre style="margin: 0; font-family: monospace;">{product_summary}</pre>
                </div>
                <div style="text-align: center; margin-top: 20px;">
                    <a href="modesty_review_interface.html" style="background: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Review Products</a>
                </div>
            </div>
        </body>
        </html>
        """
    
    # =================== HEALTH MONITORING ===================
    
    async def check_notification_health(self) -> Dict[str, Any]:
        """Check notification system health"""
        
        health_status = {
            'email_configured': bool(self.email_config.get('username')),
            'notifications_enabled': self.notification_config.get('enabled', True),
            'templates_loaded': len(self.templates),
            'recipients_configured': len(self.notification_config.get('default_recipients', [])),
            'last_test': None,
            'status': 'unknown'
        }
        
        # Test email connection if configured
        if health_status['email_configured']:
            try:
                # Quick connection test
                smtp_server = self.email_config.get('smtp_server', 'smtp.gmail.com')
                smtp_port = self.email_config.get('smtp_port', 587)
                
                with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                    if self.email_config.get('use_tls', True):
                        server.starttls()
                
                health_status['status'] = 'healthy'
                health_status['last_test'] = datetime.utcnow().isoformat()
                
            except Exception as e:
                health_status['status'] = 'unhealthy'
                health_status['error'] = str(e)
        else:
            health_status['status'] = 'not_configured'
        
        return health_status

# Maintain backward compatibility with existing notification_manager usage
class NotificationManager(EnhancedNotificationManager):
    """Backward compatibility class"""
    
    async def send_notification(self, subject: str, message: str, 
                              notification_type: str = None) -> bool:
        """Backward compatible method"""
        context = {'subject': subject, 'message': message}
        
        # Map old notification types to new enum
        if notification_type == 'batch_complete':
            return await super().send_notification(NotificationType.BATCH_COMPLETION, context)
        elif notification_type == 'batch_error':
            return await super().send_notification(NotificationType.BATCH_ERROR, context)
        else:
            # Default to system health alert
            return await super().send_notification(NotificationType.SYSTEM_HEALTH_ALERT, {
                'alert_type': 'custom_notification',
                'severity': 'medium',
                'description': message,
                'health_metrics': '',
                'recommended_actions': '',
                'system_status_url': ''
            })
    
    async def send_batch_completion(self, batch_id: str, results: Dict) -> bool:
        """Send batch completion notification (NEW METHOD)"""
        try:
            # Calculate success rate and processing time
            total = results.get('total_urls', results.get('processed_count', 0))
            successful = results.get('successful_count', results.get('updated_count', 0))
            success_rate = (successful / total * 100) if total > 0 else 0
            
            # Calculate processing time if not provided
            processing_time = results.get('processing_time', 0)
            if processing_time == 0 and 'start_time' in results and 'end_time' in results:
                try:
                    from datetime import datetime
                    start = datetime.fromisoformat(results['start_time'])
                    end = datetime.fromisoformat(results['end_time'])
                    processing_time = (end - start).total_seconds() / 60  # minutes
                except:
                    processing_time = 0
            
            # Build context with ALL fields the template expects (with safe defaults)
            context = {
                'batch_id': batch_id,
                'batch_name': results.get('batch_name', batch_id),
                'total_products': total,
                'urls_processed': results.get('processed_count', 0),
                'successful': successful,
                'failed': results.get('failed_count', 0),
                'manual_review': results.get('manual_review_count', 0),
                'manual_review_count': results.get('manual_review_count', 0),  # Template uses this
                'success_rate': success_rate,
                'processing_time': processing_time,
                'completion_time': results.get('completion_time', results.get('end_time', '')),
                'total_cost': results.get('total_cost', 0.0),  # Default to 0 if not tracked
                'products_uploaded': successful,  # Template expects this
                'batch_file': results.get('batch_file', 'N/A')  # Template expects this
            }
            return await super().send_notification(NotificationType.BATCH_COMPLETION, context)
        except Exception as e:
            logger.error(f"Error sending notification batch_completion: {e}")
            return False
    
    async def send_critical_error(self, error_message: str) -> bool:
        """Send critical error notification (NEW METHOD)"""
        context = {
            'error_type': 'critical_error',
            'severity': 'critical',
            'error_message': error_message,
            'timestamp': datetime.utcnow().isoformat(),
            'requires_action': True
        }
        return await super().send_notification(NotificationType.BATCH_ERROR, context)