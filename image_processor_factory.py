"""
Image Processor Factory - Creates appropriate image processor for each retailer
Manages the selection between reconstruction vs transformation processors
"""

from typing import Dict, Optional
from base_image_processor import BaseImageProcessor
from uniqlo_image_processor import UniqloImageProcessor
from aritzia_image_processor import AritziaImageProcessor
from simple_transform_image_processor import SimpleTransformImageProcessor
from logger_config import setup_logging

logger = setup_logging(__name__)

class ImageProcessorFactory:
    """Factory for creating retailer-specific image processors"""
    
    # Retailers that need complex URL reconstruction (build URLs from scratch)
    RECONSTRUCTION_RETAILERS = {
        'uniqlo': UniqloImageProcessor,
        'aritzia': AritziaImageProcessor,
        # Add more complex reconstruction retailers here as needed
        # 'abercrombie': AbercrombieImageProcessor,  # Future implementation
    }
    
    # Retailers that need simple URL transformation (modify existing URLs)
    TRANSFORMATION_RETAILERS = [
        'asos', 'revolve', 'hm', 'nordstrom', 'anthropologie', 
        'urban_outfitters', 'abercrombie', 'mango'
    ]
    
    _instances: Dict[str, BaseImageProcessor] = {}
    
    @classmethod
    def get_processor(cls, retailer: str) -> Optional[BaseImageProcessor]:
        """
        Get the appropriate image processor for a retailer
        Uses singleton pattern to reuse processor instances
        """
        retailer = retailer.lower()
        
        # Return cached instance if available
        if retailer in cls._instances:
            return cls._instances[retailer]
        
        # Create appropriate processor
        processor = cls._create_processor(retailer)
        
        if processor:
            cls._instances[retailer] = processor
            logger.debug(f"Created {type(processor).__name__} for {retailer}")
        
        return processor
    
    @classmethod
    def create_processor(cls, retailer: str) -> Optional[BaseImageProcessor]:
        """
        Create a new processor instance (alias for get_processor for compatibility)
        This method was referenced in tests but was missing
        """
        return cls.get_processor(retailer)
    
    @classmethod
    def _create_processor(cls, retailer: str) -> Optional[BaseImageProcessor]:
        """Create the appropriate processor for a retailer"""
        
        # Check if retailer needs complex reconstruction
        if retailer in cls.RECONSTRUCTION_RETAILERS:
            processor_class = cls.RECONSTRUCTION_RETAILERS[retailer]
            return processor_class()
        
        # Check if retailer needs simple transformation
        elif retailer in cls.TRANSFORMATION_RETAILERS:
            return SimpleTransformImageProcessor(retailer)
        
        # Unknown retailer
        else:
            logger.warning(f"No image processor available for retailer: {retailer}")
            return None
    
    @classmethod
    def get_supported_retailers(cls) -> list:
        """Get list of all supported retailers"""
        reconstruction_retailers = list(cls.RECONSTRUCTION_RETAILERS.keys())
        transformation_retailers = cls.TRANSFORMATION_RETAILERS
        return reconstruction_retailers + transformation_retailers
    
    @classmethod
    def get_processor_type(cls, retailer: str) -> str:
        """Get the type of processor needed for a retailer"""
        retailer = retailer.lower()
        
        if retailer in cls.RECONSTRUCTION_RETAILERS:
            return "reconstruction"
        elif retailer in cls.TRANSFORMATION_RETAILERS:
            return "transformation"
        else:
            return "unknown"
    
    @classmethod
    async def close_all(cls):
        """Close all processor instances"""
        for processor in cls._instances.values():
            if processor:
                await processor.close()
        cls._instances.clear()
        logger.debug("Closed all image processor instances")
    
    @classmethod
    def get_factory_stats(cls) -> Dict:
        """Get statistics about the factory and processors"""
        return {
            'total_supported_retailers': len(cls.get_supported_retailers()),
            'reconstruction_retailers': len(cls.RECONSTRUCTION_RETAILERS),
            'transformation_retailers': len(cls.TRANSFORMATION_RETAILERS),
            'active_instances': len(cls._instances),
            'supported_retailers': cls.get_supported_retailers(),
            'processor_types': {
                retailer: cls.get_processor_type(retailer) 
                for retailer in cls.get_supported_retailers()
            }
        } 