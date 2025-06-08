#!/usr/bin/env python3
"""
Test simplified extraction for speed optimization.
"""

import asyncio
import json
import os
import subprocess
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_fast_extraction():
    """Test with simplified prompt for speed"""
    
    print("=== Fast Extraction Test ===\n")
    
    # Load config
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(script_dir, 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    installation_path = config["agents"]["openmanus"]["installation_path"]
    conda_env = config["agents"]["openmanus"]["conda_env"]
    
    # Simplified prompt - only essential fields
    url = "https://www.uniqlo.com/us/en/products/E479225-000/00?colorDisplayCode=00&sizeDisplayCode=003"
    simple_prompt = f"Go to {url} and extract: title, price, and main image URL. Return as JSON with keys: title, price, image_url."
    
    script_content = f'''
import asyncio
import sys
import json
import os
import traceback

sys.path.insert(0, "{installation_path}")

async def main():
    try:
        from app.agent.manus import Manus
        print("✅ Starting fast extraction...")
        
        agent = await Manus.create()
        result = await agent.run("{simple_prompt}")
        
        print("RESULT_START")
        print(json.dumps(result))
        print("RESULT_END")
        
        await agent.cleanup()
        
    except Exception as e:
        print(f"❌ Error: {{e}}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    # Write and run test script
    test_script = Path(installation_path) / "fast_extraction_test.py"
    test_script.write_text(script_content)
    
    print(f"🚀 Running simplified extraction test...")
    print(f"📝 Prompt: {simple_prompt}")
    
    try:
        conda_python = f"{conda_env}/bin/python"
        process = subprocess.run(
            [conda_python, str(test_script)],
            capture_output=True,
            text=True,
            timeout=90,  # Shorter timeout for simple extraction
            cwd=installation_path
        )
        
        print("\n=== STDOUT ===")
        print(process.stdout)
        
        if process.stderr:
            print("\n=== STDERR ===")
            print(process.stderr)
        
        print(f"\n📊 Return code: {process.returncode}")
        
        # Parse result if successful
        if process.returncode == 0 and "RESULT_START" in process.stdout:
            try:
                start_idx = process.stdout.find("RESULT_START") + len("RESULT_START\n")
                end_idx = process.stdout.find("RESULT_END")
                if end_idx > start_idx:
                    result_json = process.stdout[start_idx:end_idx].strip()
                    result = json.loads(result_json)
                    print(f"\n✅ Extracted Data:")
                    print(json.dumps(result, indent=2))
                    return True
            except:
                pass
        
        return process.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ Even simple extraction timed out after 90 seconds")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        if test_script.exists():
            test_script.unlink()

if __name__ == "__main__":
    success = test_fast_extraction()
    
    if success:
        print("\n✅ Simple extraction worked! Consider using incremental approach.")
    else:
        print("\n❌ Even simple extraction is slow. Consider alternative solutions.") 