#!/usr/bin/env python3
"""
Resume Product Updater from Checkpoint

This script:
1. Loads the most recent checkpoint
2. Extracts remaining URLs (not yet processed)
3. Creates a batch file
4. Runs Product Updater with the batch file
"""

import sys
import os
import json
import glob
from pathlib import Path

# Add paths
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))

def find_latest_checkpoint():
    """Find the most recent checkpoint file"""
    checkpoint_dir = Path(__file__).parent.parent / "checkpoints"
    checkpoints = list(checkpoint_dir.glob("checkpoint_*.json"))
    
    if not checkpoints:
        print("❌ No checkpoint files found")
        return None
    
    # Sort by modification time, most recent first
    latest = max(checkpoints, key=lambda p: p.stat().st_mtime)
    return latest

def load_checkpoint(checkpoint_path):
    """Load checkpoint data"""
    with open(checkpoint_path, 'r') as f:
        return json.load(f)

def create_resume_batch(checkpoint_data, output_file):
    """Create batch file from checkpoint remaining URLs"""
    all_urls = checkpoint_data.get('all_urls', [])
    processed_count = checkpoint_data.get('processed_count', 0)
    successful_count = checkpoint_data.get('successful_count', 0)
    failed_count = checkpoint_data.get('failed_count', 0)
    
    # Calculate remaining URLs
    # Since processed_count might not be accurate, we'll use a different approach:
    # Create batch file with all URLs, and let Product Updater skip already-updated ones
    # OR: Use successful_count + failed_count as processed
    
    total_processed = successful_count + failed_count
    remaining_urls = all_urls[total_processed:] if total_processed < len(all_urls) else []
    
    if not remaining_urls:
        print("✅ All products already processed!")
        return None
    
    # Create batch file
    batch_data = {
        'batch_id': checkpoint_data.get('batch_id', 'resume'),
        'urls': remaining_urls,
        'total_urls': len(remaining_urls),
        'resumed_from': str(checkpoint_data.get('batch_id')),
        'original_total': len(all_urls),
        'already_processed': total_processed
    }
    
    with open(output_file, 'w') as f:
        json.dump(batch_data, f, indent=2)
    
    return output_file

def main():
    print("🔄 Resuming Product Updater from Checkpoint\n")
    
    # Step 1: Find latest checkpoint
    checkpoint_path = find_latest_checkpoint()
    if not checkpoint_path:
        return 1
    
    print(f"📂 Found checkpoint: {checkpoint_path.name}")
    
    # Step 2: Load checkpoint
    checkpoint_data = load_checkpoint(checkpoint_path)
    batch_id = checkpoint_data.get('batch_id', 'unknown')
    total_urls = len(checkpoint_data.get('all_urls', []))
    successful = checkpoint_data.get('successful_count', 0)
    failed = checkpoint_data.get('failed_count', 0)
    processed = successful + failed
    
    print(f"\n📊 Checkpoint Summary:")
    print(f"   Batch ID: {batch_id}")
    print(f"   Total URLs: {total_urls}")
    print(f"   ✅ Successful: {successful}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📝 Processed: {processed}")
    print(f"   ⏳ Remaining: {total_urls - processed}")
    
    if processed >= total_urls:
        print("\n✅ All products already processed!")
        return 0
    
    # Step 3: Create batch file
    batch_file = f"batches/resume_{batch_id}.json"
    batch_path = Path(__file__).parent.parent / batch_file
    batch_path.parent.mkdir(exist_ok=True)
    
    batch_file_path = create_resume_batch(checkpoint_data, batch_path)
    if not batch_file_path:
        return 0
    
    print(f"\n📦 Created batch file: {batch_file}")
    print(f"   Remaining URLs: {total_urls - processed}")
    
    # Step 4: Show resume command
    print(f"\n🚀 To resume, run:")
    print(f"   cd Workflows")
    print(f"   python product_updater.py --batch-file ../{batch_file}")
    print(f"\n   OR run this script with --auto flag:")
    print(f"   python resume_product_updater.py --auto")
    
    # Step 5: Auto-resume if requested
    if '--auto' in sys.argv:
        print(f"\n▶️  Auto-resuming...")
        import subprocess
        cmd = [
            sys.executable,
            str(Path(__file__).parent / "product_updater.py"),
            "--batch-file",
            str(batch_path)
        ]
        subprocess.run(cmd)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

