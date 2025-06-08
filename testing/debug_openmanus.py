#!/usr/bin/env python3
"""
Debug script to test OpenManus execution step by step.
"""

import asyncio
import json
import os
import sys
import subprocess
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_openmanus_setup():
    """Test OpenManus installation and setup"""
    
    print("🔍 Testing OpenManus setup...")
    
    # Load config
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(script_dir, 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    openmanus_config = config["agents"]["openmanus"]
    installation_path = openmanus_config["installation_path"]
    conda_env = openmanus_config["conda_env"]
    
    print(f"📁 Installation path: {installation_path}")
    print(f"🐍 Conda environment: {conda_env}")
    
    # Check if path exists
    if Path(installation_path).exists():
        print(f"✅ Installation path exists")
    else:
        print(f"❌ Installation path not found: {installation_path}")
        return False
    
    # Check if conda env exists
    conda_python = f"{conda_env}/bin/python"
    if Path(conda_python).exists():
        print(f"✅ Conda environment Python found")
    else:
        print(f"❌ Conda environment Python not found: {conda_python}")
        return False
    
    # Test Python execution
    try:
        result = subprocess.run([conda_python, "--version"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ Python version: {result.stdout.strip()}")
        else:
            print(f"❌ Python execution failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Python test failed: {e}")
        return False
    
    # Test OpenManus import
    test_import = f'''
import sys
sys.path.insert(0, "{installation_path}")
try:
    from app.agent.manus import Manus
    print("OpenManus import successful")
except Exception as e:
    print(f"OpenManus import failed: {{e}}")
'''
    
    try:
        result = subprocess.run([conda_python, "-c", test_import], 
                              capture_output=True, text=True, timeout=30)
        print(f"📦 Import test result: {result.stdout.strip()}")
        if result.stderr:
            print(f"⚠️  Import warnings: {result.stderr.strip()}")
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False
    
    return True

def create_test_script(url: str, prompt: str, installation_path: str):
    """Create a test script for OpenManus"""
    
    script_content = f'''
import asyncio
import sys
import json
import os
import traceback

# Add OpenManus to path
sys.path.insert(0, "{installation_path}")

async def main():
    try:
        from app.agent.manus import Manus
        print("Creating Manus agent...")
        
        agent = await Manus.create()
        print("Agent created successfully")
        
        print(f"Running prompt: {{repr("{prompt}")}}")
        result = await agent.run("{prompt}")
        
        print("=== OpenManus Result ===")
        print(json.dumps(result, indent=2))
        
        await agent.cleanup()
        print("Agent cleanup completed")
        
    except Exception as e:
        print(f"Error: {{e}}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    return script_content

def main():
    url = "https://www.uniqlo.com/us/en/products/E479225-000/00?colorDisplayCode=00&sizeDisplayCode=003"
    
    print("=== OpenManus Debug Test ===\n")
    
    # Test setup
    if not test_openmanus_setup():
        print("\n❌ OpenManus setup failed!")
        return
    
    print("\n🔧 Creating test prompt...")
    
    # Create the prompt (same as the system would)
    prompt = f"Extract from {url}: retailer, brand, title, price, original_price, description, stock_status, sale_status, clothing_type, product_code, image_urls (ordered: primary view first). Return JSON. Uniqlo/collaboration brands. Limited availability = low stock. IMPORTANT: When on sale, original_price may not be available - set to null if not shown. Order images: primary product view first."
    
    print(f"📝 Prompt: {prompt}")
    
    # Load config for paths
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(script_dir, 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    installation_path = config["agents"]["openmanus"]["installation_path"]
    conda_env = config["agents"]["openmanus"]["conda_env"]
    
    # Create test script
    script_content = create_test_script(url, prompt, installation_path)
    
    # Write and run test script
    test_script = Path(installation_path) / "debug_openmanus_test.py"
    test_script.write_text(script_content)
    
    print(f"\n🚀 Running OpenManus test...")
    print(f"📄 Test script: {test_script}")
    
    try:
        conda_python = f"{conda_env}/bin/python"
        process = subprocess.run(
            [conda_python, str(test_script)],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=installation_path
        )
        
        print("=== STDOUT ===")
        print(process.stdout)
        
        if process.stderr:
            print("=== STDERR ===")
            print(process.stderr)
        
        print(f"\n📊 Return code: {process.returncode}")
        
    except subprocess.TimeoutExpired:
        print("❌ OpenManus test timed out after 3 minutes")
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
    finally:
        # Clean up
        if test_script.exists():
            test_script.unlink()
            print("🧹 Cleaned up test script")

if __name__ == "__main__":
    main() 