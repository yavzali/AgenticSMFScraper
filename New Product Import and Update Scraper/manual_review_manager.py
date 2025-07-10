"""
Manual Review Manager - Handles the manual review queue for failed items
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))

import csv
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

from logger_config import setup_logging

logger = setup_logging(__name__)

class ReviewStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    SKIPPED = "skipped"

class ErrorType(Enum):
    EXTRACTION_FAILED = "extraction_failed"
    IMAGE_DOWNLOAD_FAILED = "image_download_failed"
    SHOPIFY_CREATION_FAILED = "shopify_creation_failed"
    DUPLICATE_UNCERTAIN = "duplicate_uncertain"
    VALIDATION_FAILED = "validation_failed"
    NETWORK_ERROR = "network_error"
    CRITICAL_ERROR = "critical_error"
    PROCESSING_ERROR = "processing_error"

class RecommendedAction(Enum):
    RETRY_WITH_DIFFERENT_METHOD = "retry_with_different_method"
    CREATE_PRODUCT_WITHOUT_IMAGES = "create_product_without_images"
    MANUAL_DUPLICATE_REVIEW = "manual_duplicate_review"
    MANUAL_DATA_CORRECTION = "manual_data_correction"
    SKIP_PERMANENTLY = "skip_permanently"
    INVESTIGATE_WEBSITE_CHANGES = "investigate_website_changes"
    CHECK_NETWORK_CONNECTIVITY = "check_network_connectivity"
    CONTACT_SUPPORT = "contact_support"

@dataclass
class ManualReviewItem:
    url: str
    retailer: str
    modesty_level: str
    error_type: str
    error_details: str
    extracted_title: Optional[str] = None
    extracted_price: Optional[float] = None
    original_price: Optional[float] = None
    sale_status: Optional[str] = None
    clothing_type: Optional[str] = None
    stock_status: Optional[str] = None
    extracted_images: int = 0
    recommended_action: str = RecommendedAction.RETRY_WITH_DIFFERENT_METHOD.value
    retry_possible: bool = True
    timestamp: str = None
    status: str = ReviewStatus.PENDING.value
    assigned_to: Optional[str] = None
    resolution_notes: Optional[str] = None
    retry_count: int = 0
    last_retry: Optional[str] = None
    batch_id: Optional[str] = None
    priority: str = "normal"  # low, normal, high, critical

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()

class ManualReviewManager:
    def __init__(self, review_file: str = "manual_review.csv"):
        self.review_file = review_file
        self.review_items = []
        
        # Ensure directory exists
        Path(review_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing review items
        self._load_existing_items()
    
    def add_review_item(self, url: str, retailer: str, modesty_level: str, 
                       error_type: str, error_details: str, 
                       extracted_data: Optional[Dict] = None,
                       batch_id: Optional[str] = None,
                       priority: str = "normal") -> bool:
        """Add item to manual review queue"""
        
        try:
            # Create review item
            item = ManualReviewItem(
                url=url,
                retailer=retailer,
                modesty_level=modesty_level,
                error_type=error_type,
                error_details=error_details,
                batch_id=batch_id,
                priority=priority
            )
            
            # Add extracted data if available
            if extracted_data:
                item.extracted_title = extracted_data.get('title')
                item.extracted_price = extracted_data.get('price')
                item.original_price = extracted_data.get('original_price')
                item.sale_status = extracted_data.get('sale_status')
                item.clothing_type = extracted_data.get('clothing_type')
                item.stock_status = extracted_data.get('stock_status')
                item.extracted_images = len(extracted_data.get('image_urls', []))
            
            # Set recommended action based on error type
            item.recommended_action = self._determine_recommended_action(error_type, extracted_data)
            item.retry_possible = self._determine_retry_possibility(error_type)
            
            # Set priority based on error type
            if priority == "normal":  # Auto-adjust if not manually set
                item.priority = self._determine_priority(error_type, extracted_data)
            
            # Add to memory and file
            self.review_items.append(item)
            self._append_to_file(item)
            
            logger.info(f"Added to manual review: {url} ({error_type})")
            return True
        
        except Exception as e:
            logger.error(f"Failed to add review item: {e}")
            return False
    
    def get_pending_items(self, retailer: Optional[str] = None, 
                         priority: Optional[str] = None) -> List[ManualReviewItem]:
        """Get pending review items with optional filtering"""
        
        items = [item for item in self.review_items if item.status == ReviewStatus.PENDING.value]
        
        if retailer:
            items = [item for item in items if item.retailer == retailer]
        
        if priority:
            items = [item for item in items if item.priority == priority]
        
        # Sort by priority and timestamp
        priority_order = {'critical': 0, 'high': 1, 'normal': 2, 'low': 3}
        items.sort(key=lambda x: (priority_order.get(x.priority, 2), x.timestamp))
        
        return items
    
    def update_item_status(self, url: str, status: str, assigned_to: Optional[str] = None,
                          resolution_notes: Optional[str] = None) -> bool:
        """Update status of a review item"""
        
        try:
            for item in self.review_items:
                if item.url == url:
                    item.status = status
                    if assigned_to:
                        item.assigned_to = assigned_to
                    if resolution_notes:
                        item.resolution_notes = resolution_notes
                    
                    # Rewrite the entire file to update status
                    self._rewrite_file()
                    
                    logger.info(f"Updated review item status: {url} -> {status}")
                    return True
            
            logger.warning(f"Review item not found for URL: {url}")
            return False
        
        except Exception as e:
            logger.error(f"Failed to update item status: {e}")
            return False
    
    def retry_item(self, url: str, new_method: Optional[str] = None) -> Dict:
        """Mark item for retry and return retry information"""
        
        try:
            for item in self.review_items:
                if item.url == url:
                    if not item.retry_possible:
                        return {
                            'success': False,
                            'error': 'Item marked as not retryable'
                        }
                    
                    item.retry_count += 1
                    item.last_retry = datetime.utcnow().isoformat()
                    item.status = ReviewStatus.PENDING.value  # Reset to pending
                    
                    if item.retry_count > 3:
                        item.retry_possible = False
                        item.recommended_action = RecommendedAction.SKIP_PERMANENTLY.value
                    
                    self._rewrite_file()
                    
                    return {
                        'success': True,
                        'retry_count': item.retry_count,
                        'recommended_method': new_method or self._suggest_retry_method(item),
                        'item': item
                    }
            
            return {'success': False, 'error': 'Item not found'}
        
        except Exception as e:
            logger.error(f"Failed to retry item: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_review_summary(self) -> Dict:
        """Get summary statistics for manual review queue"""
        
        total_items = len(self.review_items)
        pending_items = len([item for item in self.review_items if item.status == ReviewStatus.PENDING.value])
        in_progress_items = len([item for item in self.review_items if item.status == ReviewStatus.IN_PROGRESS.value])
        resolved_items = len([item for item in self.review_items if item.status == ReviewStatus.RESOLVED.value])
        
        # Group by error type
        error_type_counts = {}
        for item in self.review_items:
            if item.status == ReviewStatus.PENDING.value:
                error_type_counts[item.error_type] = error_type_counts.get(item.error_type, 0) + 1
        
        # Group by retailer
        retailer_counts = {}
        for item in self.review_items:
            if item.status == ReviewStatus.PENDING.value:
                retailer_counts[item.retailer] = retailer_counts.get(item.retailer, 0) + 1
        
        # Priority breakdown
        priority_counts = {}
        for item in self.review_items:
            if item.status == ReviewStatus.PENDING.value:
                priority_counts[item.priority] = priority_counts.get(item.priority, 0) + 1
        
        return {
            'total_items': total_items,
            'pending': pending_items,
            'in_progress': in_progress_items,
            'resolved': resolved_items,
            'by_error_type': error_type_counts,
            'by_retailer': retailer_counts,
            'by_priority': priority_counts,
            'oldest_pending': self._get_oldest_pending_item(),
            'retry_candidates': len([item for item in self.review_items 
                                   if item.status == ReviewStatus.PENDING.value and item.retry_possible])
        }
    
    def export_for_analysis(self, output_file: str, status_filter: Optional[str] = None) -> bool:
        """Export review items for external analysis"""
        
        try:
            items_to_export = self.review_items
            
            if status_filter:
                items_to_export = [item for item in items_to_export if item.status == status_filter]
            
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'url', 'retailer', 'modesty_level', 'error_type', 'error_details',
                    'extracted_title', 'extracted_price', 'original_price', 'sale_status',
                    'clothing_type', 'stock_status', 'extracted_images', 'recommended_action',
                    'retry_possible', 'timestamp', 'status', 'assigned_to', 'resolution_notes',
                    'retry_count', 'last_retry', 'batch_id', 'priority'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for item in items_to_export:
                    writer.writerow(asdict(item))
            
            logger.info(f"Exported {len(items_to_export)} items to {output_file}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to export review items: {e}")
            return False
    
    def bulk_update_status(self, retailer: str, old_status: str, new_status: str,
                          resolution_notes: Optional[str] = None) -> int:
        """Bulk update status for items matching criteria"""
        
        try:
            updated_count = 0
            
            for item in self.review_items:
                if item.retailer == retailer and item.status == old_status:
                    item.status = new_status
                    if resolution_notes:
                        item.resolution_notes = resolution_notes
                    updated_count += 1
            
            if updated_count > 0:
                self._rewrite_file()
                logger.info(f"Bulk updated {updated_count} items for {retailer}")
            
            return updated_count
        
        except Exception as e:
            logger.error(f"Failed to bulk update: {e}")
            return 0
    
    def cleanup_old_items(self, days: int = 30) -> int:
        """Clean up old resolved items"""
        
        try:
            cutoff_date = datetime.utcnow().timestamp() - (days * 24 * 3600)
            original_count = len(self.review_items)
            
            self.review_items = [
                item for item in self.review_items
                if not (item.status == ReviewStatus.RESOLVED.value and 
                       datetime.fromisoformat(item.timestamp).timestamp() < cutoff_date)
            ]
            
            removed_count = original_count - len(self.review_items)
            
            if removed_count > 0:
                self._rewrite_file()
                logger.info(f"Cleaned up {removed_count} old resolved items")
            
            return removed_count
        
        except Exception as e:
            logger.error(f"Failed to cleanup old items: {e}")
            return 0
    
    def _load_existing_items(self):
        """Load existing review items from CSV file"""
        
        if not os.path.exists(self.review_file):
            logger.info("No existing manual review file found")
            return
        
        try:
            with open(self.review_file, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    # Convert string values back to appropriate types
                    item_data = dict(row)
                    
                    # Handle numeric fields
                    if item_data.get('extracted_price'):
                        try:
                            item_data['extracted_price'] = float(item_data['extracted_price'])
                        except ValueError:
                            item_data['extracted_price'] = None
                    
                    if item_data.get('original_price'):
                        try:
                            item_data['original_price'] = float(item_data['original_price'])
                        except ValueError:
                            item_data['original_price'] = None
                    
                    if item_data.get('extracted_images'):
                        try:
                            item_data['extracted_images'] = int(item_data['extracted_images'])
                        except ValueError:
                            item_data['extracted_images'] = 0
                    
                    if item_data.get('retry_count'):
                        try:
                            item_data['retry_count'] = int(item_data['retry_count'])
                        except ValueError:
                            item_data['retry_count'] = 0
                    
                    # Handle boolean fields
                    if item_data.get('retry_possible'):
                        item_data['retry_possible'] = item_data['retry_possible'].lower() == 'true'
                    
                    # Handle None/empty fields
                    for field in ['extracted_title', 'sale_status', 'clothing_type', 'stock_status', 
                                'assigned_to', 'resolution_notes', 'last_retry', 'batch_id']:
                        if not item_data.get(field):
                            item_data[field] = None
                    
                    item = ManualReviewItem(**item_data)
                    self.review_items.append(item)
            
            logger.info(f"Loaded {len(self.review_items)} existing review items")
        
        except Exception as e:
            logger.error(f"Failed to load existing review items: {e}")
    
    def _append_to_file(self, item: ManualReviewItem):
        """Append single item to CSV file"""
        
        try:
            file_exists = os.path.exists(self.review_file)
            
            with open(self.review_file, 'a', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'url', 'retailer', 'modesty_level', 'error_type', 'error_details',
                    'extracted_title', 'extracted_price', 'original_price', 'sale_status',
                    'clothing_type', 'stock_status', 'extracted_images', 'recommended_action',
                    'retry_possible', 'timestamp', 'status', 'assigned_to', 'resolution_notes',
                    'retry_count', 'last_retry', 'batch_id', 'priority'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write header if file is new
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow(asdict(item))
        
        except Exception as e:
            logger.error(f"Failed to append to review file: {e}")
    
    def _rewrite_file(self):
        """Rewrite entire CSV file with current items"""
        
        try:
            with open(self.review_file, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'url', 'retailer', 'modesty_level', 'error_type', 'error_details',
                    'extracted_title', 'extracted_price', 'original_price', 'sale_status',
                    'clothing_type', 'stock_status', 'extracted_images', 'recommended_action',
                    'retry_possible', 'timestamp', 'status', 'assigned_to', 'resolution_notes',
                    'retry_count', 'last_retry', 'batch_id', 'priority'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for item in self.review_items:
                    writer.writerow(asdict(item))
        
        except Exception as e:
            logger.error(f"Failed to rewrite review file: {e}")
    
    def _determine_recommended_action(self, error_type: str, extracted_data: Optional[Dict]) -> str:
        """Determine recommended action based on error type and available data"""
        
        action_mapping = {
            ErrorType.EXTRACTION_FAILED.value: RecommendedAction.RETRY_WITH_DIFFERENT_METHOD.value,
            ErrorType.IMAGE_DOWNLOAD_FAILED.value: RecommendedAction.CREATE_PRODUCT_WITHOUT_IMAGES.value,
            ErrorType.SHOPIFY_CREATION_FAILED.value: RecommendedAction.MANUAL_DATA_CORRECTION.value,
            ErrorType.DUPLICATE_UNCERTAIN.value: RecommendedAction.MANUAL_DUPLICATE_REVIEW.value,
            ErrorType.VALIDATION_FAILED.value: RecommendedAction.MANUAL_DATA_CORRECTION.value,
            ErrorType.NETWORK_ERROR.value: RecommendedAction.CHECK_NETWORK_CONNECTIVITY.value,
            ErrorType.CRITICAL_ERROR.value: RecommendedAction.CONTACT_SUPPORT.value,
            ErrorType.PROCESSING_ERROR.value: RecommendedAction.RETRY_WITH_DIFFERENT_METHOD.value
        }
        
        # Special logic for extraction failures with partial data
        if error_type == ErrorType.EXTRACTION_FAILED.value and extracted_data:
            if extracted_data.get('title') and extracted_data.get('price'):
                return RecommendedAction.MANUAL_DATA_CORRECTION.value
        
        return action_mapping.get(error_type, RecommendedAction.RETRY_WITH_DIFFERENT_METHOD.value)
    
    def _determine_retry_possibility(self, error_type: str) -> bool:
        """Determine if item can be retried"""
        
        non_retryable_errors = [
            ErrorType.DUPLICATE_UNCERTAIN.value,
            ErrorType.CRITICAL_ERROR.value
        ]
        
        return error_type not in non_retryable_errors
    
    def _determine_priority(self, error_type: str, extracted_data: Optional[Dict]) -> str:
        """Determine priority level for review item"""
        
        # Critical errors get high priority
        if error_type == ErrorType.CRITICAL_ERROR.value:
            return "critical"
        
        # Network errors affecting multiple items get high priority
        if error_type == ErrorType.NETWORK_ERROR.value:
            return "high"
        
        # Items with good extracted data but failed creation get high priority
        if (error_type == ErrorType.SHOPIFY_CREATION_FAILED.value and 
            extracted_data and extracted_data.get('title') and extracted_data.get('price')):
            return "high"
        
        # Duplicate reviews get normal priority
        if error_type == ErrorType.DUPLICATE_UNCERTAIN.value:
            return "normal"
        
        # Everything else gets normal priority
        return "normal"
    
    def _suggest_retry_method(self, item: ManualReviewItem) -> str:
        """Suggest retry method based on previous failures"""
        
        if item.retry_count == 0:
            return "skyvern"  # Try second method in hierarchy
        elif item.retry_count == 1:
            return "browser_use"  # Try third method
        else:
            return "manual_extraction"  # Manual process required
    
    def _get_oldest_pending_item(self) -> Optional[str]:
        """Get timestamp of oldest pending item"""
        
        pending_items = [item for item in self.review_items if item.status == ReviewStatus.PENDING.value]
        
        if not pending_items:
            return None
        
        oldest = min(pending_items, key=lambda x: x.timestamp)
        return oldest.timestamp