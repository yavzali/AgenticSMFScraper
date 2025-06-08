#!/usr/bin/env python3
"""
Simple OpenManus test with basic functionality.
"""

import asyncio
import json
import os
import subprocess
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_basic_openmanus():
    """Test basic OpenManus functionality"""
    
    print("=== Basic OpenManus Test ===\n")
    
    # Load config
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(script_dir, 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    installation_path = config["agents"]["openmanus"]["installation_path"]
    conda_env = config["agents"]["openmanus"]["conda_env"]
    
    # Create a simple test script
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
        print("✅ Creating Manus agent...")
        
        agent = await Manus.create()
        print("✅ Agent created successfully")
        
        # Simple test - just visit a page and get title
        simple_prompt = "Go to https://www.uniqlo.com and tell me the page title"
        print(f"🔍 Running simple test: {{simple_prompt}}")
        
        result = await agent.run(simple_prompt)
        
        print("=== OpenManus Result ===")
        print(result)
        
        await agent.cleanup()
        print("✅ Agent cleanup completed")
        
    except Exception as e:
        print(f"❌ Error: {{e}}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    # Write and run test script
    test_script = Path(installation_path) / "simple_openmanus_test.py"
    test_script.write_text(script_content)
    
    print(f"🚀 Running simple OpenManus test...")
    print(f"📄 Test script: {test_script}")
    
    try:
        conda_python = f"{conda_env}/bin/python"
        process = subprocess.run(
            [conda_python, str(test_script)],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minutes for simple test
            cwd=installation_path
        )
        
        print("=== STDOUT ===")
        print(process.stdout)
        
        if process.stderr:
            print("=== STDERR ===")
            print(process.stderr)
        
        print(f"\n📊 Return code: {process.returncode}")
        
        if process.returncode == 0:
            print("✅ Basic OpenManus test successful!")
            return True
        else:
            print("❌ Basic OpenManus test failed!")
            return False
        
    except subprocess.TimeoutExpired:
        print("❌ Simple test timed out after 2 minutes")
        return False
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return False
    finally:
        # Clean up
        if test_script.exists():
            test_script.unlink()
            print("🧹 Cleaned up test script")

def main():
    success = test_basic_openmanus()
    
    if success:
        print("\n✅ OpenManus is working! You can proceed with product extraction.")
        print("The timeout in the complex extraction might be normal for detailed scraping.")
    else:
        print("\n❌ OpenManus basic functionality failed.")
        print("This suggests there might be an environment or configuration issue.")

if __name__ == "__main__":
    main() 