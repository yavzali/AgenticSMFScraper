"""
Notification Manager - Handles email notifications and alerts
"""

import smtplib
import json
import os
import csv
import io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from logger_config import setup_logging

logger = setup_logging(__name__)

class NotificationManager:
    def __init__(self):
        # Load configuration
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        self.notification_config = config.get('notifications', {})
        self.email_enabled = self.notification_config.get('email_enabled', False)
        self.recipients = self.notification_config.get('email_recipients', [])
        self.triggers = self.notification_config.get('notification_triggers', {})
        
        # Email configuration (you'll need to add these to config.json)
        self.smtp_server = self.notification_config.get('smtp_server', 'smtp.gmail.com')
        self.smtp_port = self.notification_config.get('smtp_port', 587)
        self.email_username = self.notification_config.get('email_username', '')
        self.email_password = self.notification_config.get('email_password', '')
        self.sender_email = self.notification_config.get('sender_email', self.email_username)
        
        logger.info(f"Notification manager initialized - Email enabled: {self.email_enabled}")
    
    async def send_batch_completion(self, batch_id: str, results: Dict):
        """Send batch completion notification"""
        
        if not self._should_send_notification('batch_complete'):
            return
        
        subject = f"Scraping Batch Complete - {batch_id}"
        
        # Calculate additional metrics
        success_rate = results.get('success_rate', 0)
        total_urls = results.get('total_urls', 0)
        duration_minutes = results.get('duration_minutes', 0)
        
        # Build retailer breakdown
        retailer_breakdown = self._format_retailer_breakdown(results.get('retailer_breakdown', {}))
        
        # Build method performance
        method_performance = self._format_method_performance(results.get('method_performance', {}))
        
        # Estimate cost
        estimated_cost = self._estimate_batch_cost(results)
        
        body = f"""
Batch Processing Summary:

Batch ID: {batch_id}
Duration: {duration_minutes:.1f} minutes
Start Time: {results.get('start_time', 'Unknown')}
End Time: {results.get('end_time', 'Unknown')}

Results:
✅ Successfully Processed: {results.get('successful_count', 0)}/{total_urls} ({success_rate:.1f}%)
❌ Failed: {results.get('failed_count', 0)}
⚠️  Manual Review Required: {results.get('manual_review_count', 0)}

By Retailer:
{retailer_breakdown}

Extraction Method Performance:
{method_performance}

Cost Summary:
Estimated Cost: ${estimated_cost:.2f}
Processing Rate: {total_urls / max(duration_minutes / 60, 0.1):.1f} URLs/hour

Manual Review Items: {results.get('manual_review_count', 0)}
{self._get_manual_review_summary() if results.get('manual_review_count', 0) > 0 else ''}

Next Steps:
1. Review products in Shopify (all created as drafts)
2. Check manual review queue if items failed
3. Verify product images and descriptions

Dashboard: https://{self._get_shopify_domain()}/admin/products
"""
        
        attachments = []
        
        # Attach manual review CSV if there are failed items
        if results.get('manual_review_count', 0) > 0:
            manual_review_csv = self._create_manual_review_attachment()
            if manual_review_csv:
                attachments.append(manual_review_csv)
        
        await self._send_email(subject, body, attachments)
    
    async def send_critical_error(self, error_message: str, batch_id: str = None):
        """Send critical error notification"""
        
        if not self._should_send_notification('critical_errors'):
            return
        
        subject = f"🚨 Critical Error in Scraping System"
        if batch_id:
            subject += f" - Batch {batch_id}"
        
        body = f"""
Critical Error Alert:

Error: {error_message}
Time: {datetime.utcnow().isoformat()} UTC
Batch ID: {batch_id or 'N/A'}

This error may have interrupted the scraping process. Please check the system logs for more details.

Recommended Actions:
1. Check system logs: logs/errors.log
2. Verify system status
3. Resume processing if possible using: python main_scraper.py --resume

Log Files:
- Main log: logs/scraper_main.log
- Error log: logs/errors.log
- Performance log: logs/performance.log
"""
        
        await self._send_email(subject, body, priority='high')
    
    async def send_system_status(self, status_data: Dict):
        """Send system status notification"""
        
        subject = f"Scraping System Status Report"
        
        body = f"""
System Status Report:

Generated: {datetime.utcnow().isoformat()} UTC

Database Statistics:
- Total Products: {status_data.get('total_products', 0)}
- Active Batches: {status_data.get('active_batches', 0)}
- Recent Activity (7 days): {status_data.get('recent_activity', 0)}

System Health:
- Disk Space: {status_data.get('disk_space', 'Unknown')}
- Log File Sizes: {status_data.get('log_sizes', 'Unknown')}
- Database Size: {status_data.get('db_size', 'Unknown')}

Performance Metrics:
- Average Processing Time: {status_data.get('avg_processing_time', 0):.1f}s per URL
- Success Rate (7 days): {status_data.get('success_rate', 0):.1f}%
- Most Successful Retailer: {status_data.get('top_retailer', 'N/A')}

Next Scheduled Maintenance: {status_data.get('next_maintenance', 'Not scheduled')}
"""
        
        await self._send_email(subject, body)
    
    async def send_manual_review_alert(self, failed_count: int, batch_id: str):
        """Send alert when manual review threshold is exceeded"""
        
        threshold = self.triggers.get('manual_review_threshold', 20)
        
        if failed_count < threshold:
            return
        
        if not self._should_send_notification('critical_errors'):
            return
        
        subject = f"⚠️ High Manual Review Count - Batch {batch_id}"
        
        body = f"""
Manual Review Alert:

Batch ID: {batch_id}
Failed Items: {failed_count}
Threshold: {threshold}

A high number of items require manual review. This may indicate:
1. System issues with extraction
2. Retailer website changes
3. Network connectivity problems
4. Agent API issues

Recommended Actions:
1. Check recent error logs
2. Review manual_review.csv for patterns
3. Test a few URLs manually
4. Consider pausing the batch if issues persist

Manual Review File: manual_review.csv
"""
        
        await self._send_email(subject, body, priority='high')
    
    def _should_send_notification(self, trigger_type: str) -> bool:
        """Check if notification should be sent based on configuration"""
        
        if not self.email_enabled:
            logger.debug("Email notifications disabled")
            return False
        
        if not self.recipients:
            logger.warning("No email recipients configured")
            return False
        
        if not self.triggers.get(trigger_type, True):
            logger.debug(f"Notification trigger '{trigger_type}' disabled")
            return False
        
        return True
    
    async def _send_email(self, subject: str, body: str, attachments: List = None, priority: str = 'normal'):
        """Send email notification"""
        
        try:
            if not self.email_username or not self.email_password:
                logger.warning("⚠️ Email credentials not configured - email notifications disabled")
                return
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(self.recipients)
            msg['Subject'] = subject
            
            # Set priority
            if priority == 'high':
                msg['X-Priority'] = '1'
                msg['X-MSMail-Priority'] = 'High'
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    msg.attach(attachment)
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_username, self.email_password)
            
            text = msg.as_string()
            server.sendmail(self.sender_email, self.recipients, text)
            server.quit()
            
            logger.info(f"Email notification sent: {subject}")
        
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
    
    def _format_retailer_breakdown(self, retailer_data: Dict) -> str:
        """Format retailer breakdown for email"""
        
        if not retailer_data:
            return "No retailer data available"
        
        lines = []
        for retailer, stats in retailer_data.items():
            total = stats.get('total', 0)
            successful = stats.get('successful', 0)
            failed = stats.get('failed', 0)
            success_rate = (successful / total * 100) if total > 0 else 0
            
            lines.append(f"  {retailer.title()}: {successful}/{total} ({success_rate:.1f}%) - {failed} failed")
        
        return '\n'.join(lines) if lines else "No data"
    
    def _format_method_performance(self, method_data: Dict) -> str:
        """Format extraction method performance for email"""
        
        if not method_data:
            return "No method data available"
        
        lines = []
        for method, stats in method_data.items():
            count = stats.get('count', 0)
            success_rate = stats.get('success_rate', 0)
            
            lines.append(f"  {method.title()}: {success_rate:.1f}% success rate ({count} attempts)")
        
        return '\n'.join(lines) if lines else "No data"
    
    def _estimate_batch_cost(self, results: Dict) -> float:
        """Estimate batch processing cost"""
        
        # Simple cost estimation based on processing time and method usage
        duration_hours = results.get('duration_minutes', 0) / 60
        
        # Estimate based on method usage (most tools are free)
        base_cost_per_hour = 1.0  # Conservative estimate for hosting/compute
        estimated_cost = duration_hours * base_cost_per_hour
        
        return max(estimated_cost, 0.50)  # Minimum $0.50
    
    def _get_manual_review_summary(self) -> str:
        """Get summary of manual review items"""
        
        try:
            # This would read from actual manual_review.csv
            # For now, return placeholder
            return "Check manual_review.csv for detailed failure analysis"
        except Exception:
            return "Manual review file not accessible"
    
    def _create_manual_review_attachment(self) -> Optional[MIMEBase]:
        """Create manual review CSV attachment"""
        
        try:
            # Create CSV content in memory
            csv_content = io.StringIO()
            
            # This would read from actual manual review data
            # For now, create sample structure
            writer = csv.writer(csv_content)
            writer.writerow([
                'URL', 'Retailer', 'Modesty_Level', 'Error_Type', 
                'Error_Details', 'Timestamp', 'Recommended_Action'
            ])
            
            # Sample data - in real implementation, this would come from actual failed items
            sample_row = [
                'https://example.com/product',
                'Example Retailer', 
                'modest',
                'extraction_failed',
                'OpenManus timeout after 60s',
                datetime.utcnow().isoformat(),
                'retry_with_different_method'
            ]
            writer.writerow(sample_row)
            
            # Create attachment
            csv_data = csv_content.getvalue().encode('utf-8')
            
            attachment = MIMEBase('application', 'octet-stream')
            attachment.set_payload(csv_data)
            encoders.encode_base64(attachment)
            attachment.add_header(
                'Content-Disposition',
                f'attachment; filename="manual_review_{datetime.now().strftime("%Y%m%d_%H%M")}.csv"'
            )
            
            return attachment
        
        except Exception as e:
            logger.error(f"Failed to create manual review attachment: {e}")
            return None
    
    def _get_shopify_domain(self) -> str:
        """Get Shopify domain from config"""
        
        try:
            # Get the directory where this script is located
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(script_dir, 'config.json')
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config.get('shopify', {}).get('store_url', 'your-store.myshopify.com')
        except Exception:
            return 'your-store.myshopify.com'
    
    async def test_email_configuration(self) -> Dict:
        """Test email configuration and send test email"""
        
        try:
            if not self.email_enabled:
                return {'success': False, 'error': 'Email notifications disabled'}
            
            if not self.recipients:
                return {'success': False, 'error': 'No recipients configured'}
            
            # Test SMTP connection
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_username, self.email_password)
            server.quit()
            
            # Send test email
            subject = "Scraping System - Email Test"
            body = f"""
This is a test email from the Scraping System.

Configuration:
- SMTP Server: {self.smtp_server}:{self.smtp_port}
- From: {self.sender_email}
- Recipients: {', '.join(self.recipients)}
- Test Time: {datetime.utcnow().isoformat()} UTC

If you received this email, your notification system is working correctly!
"""
            
            await self._send_email(subject, body)
            
            return {
                'success': True, 
                'message': f'Test email sent to {len(self.recipients)} recipients'
            }
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_notification_status(self) -> Dict:
        """Get current notification configuration status"""
        
        return {
            'email_enabled': self.email_enabled,
            'recipients_count': len(self.recipients),
            'recipients': self.recipients if self.email_enabled else ['[hidden]'],
            'smtp_server': self.smtp_server,
            'triggers': self.triggers,
            'credentials_configured': bool(self.email_username and self.email_password)
        }