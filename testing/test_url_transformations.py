import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simple_transform_image_processor import SimpleTransformImageProcessor

async def test_url_transformations():
    """Test if URL transformations are working correctly"""
    
    # Test H&M URLs (real examples from logs)
    print("🧪 Testing H&M URL transformations...")
    hm_processor = SimpleTransformImageProcessor('hm')
    
    hm_urls = [
        "https://image.hm.com/assets/hm/b0/6b/b06bda0c8c652e3c9235ac91de92749a26a85b4f.jpg?imwidth=2160",
        "https://image.hm.com/assets/hm/fc/2a/fc2a93b5d6cc51d49ca0fe2999dcef26802d55c4.jpg?imwidth=384",
        "https://image.hm.com/assets/hm/1f/d2/1fd25d5d785529ac3fe2edd89f1ff3b48c40094e.jpg"
    ]
    
    transformed_hm = await hm_processor.reconstruct_image_urls("", {"image_urls": hm_urls})
    
    for i, (original, transformed) in enumerate(zip(hm_urls, transformed_hm)):
        print(f"  {i+1}. Original: {original}")
        print(f"     Transformed: {transformed}")
        print()
    
    # Test Revolve URLs
    print("🧪 Testing Revolve URL transformations...")
    revolve_processor = SimpleTransformImageProcessor('revolve')
    
    revolve_urls = [
        "https://is4.revolveassets.com/images/p4/n/z/LAGR-WD258_V1.jpg",  # Already /n/z/
        "https://is4.revolveassets.com/images/p4/n/ct/LAGR-WD258_V1.jpg", # Should transform
        "https://is4.revolveassets.com/images/p4/n/uv/LAGR-WD258_V1.jpg"  # Should transform
    ]
    
    transformed_revolve = await revolve_processor.reconstruct_image_urls("", {"image_urls": revolve_urls})
    
    for i, (original, transformed) in enumerate(zip(revolve_urls, transformed_revolve)):
        print(f"  {i+1}. Original: {original}")
        print(f"     Transformed: {transformed}")
        print()
    
    # Test ASOS URLs
    print("🧪 Testing ASOS URL transformations...")
    asos_processor = SimpleTransformImageProcessor('asos')
    
    asos_urls = [
        "https://images.asos-media.com/products/asos-design-oversized-t-shirt-in-black/12345-1-black?$S$&wid=513&fit=constrain",
        "https://images.asos-media.com/products/asos-design-oversized-t-shirt-in-black/12345-1-black?$T$&wid=400"
    ]
    
    transformed_asos = await asos_processor.reconstruct_image_urls("", {"image_urls": asos_urls})
    
    for i, (original, transformed) in enumerate(zip(asos_urls, transformed_asos)):
        print(f"  {i+1}. Original: {original}")
        print(f"     Transformed: {transformed}")
        print()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_url_transformations()) 