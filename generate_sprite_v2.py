#!/usr/bin/env python3

import os
import subprocess
import json
import argparse
import glob
import boto3
import sys

# --- 1. CORE PROCESSING LOGIC ---
def generate_sprite(input_path, num_thumbs, interval, width, output_mesh, output_sprite):
    """
    Core logic: Generates thumbnails with FFmpeg and tiles them with ImageMagick.
    Works for both local files and Lambda /tmp/ files.
    """
    print(f"--- Starting Sprite Generation ---")
    print(f"Input: {input_path}")
    
    # 1. Cleanup: Remove old thumbs from previous 'warm' Lambda starts
    # This prevents the new sprite from including old video frames.
    for f in glob.glob("/tmp/thumb_*.png"):
        try:
            os.remove(f)
        except OSError:
            pass

    # 2. Generate Thumbnails via FFmpeg
    # -y: overwrite, -vf: scale and set fps, -vframes: limit output
    temp_pattern = "/tmp/thumb_%03d.png"
    ffmpeg_cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"fps=1/{interval},scale={width}:-1",
        "-vframes", str(num_thumbs),
        temp_pattern
    ]
    
    print(f"Running FFmpeg: {' '.join(ffmpeg_cmd)}")
    subprocess.run(ffmpeg_cmd, check=True)

    # 3. Create Sprite Sheet via ImageMagick (montage)
    # FIX: We use 'montage' directly (standard on AL2) and shell=True for '*' expansion.
    # -tile x1: creates a single horizontal row.
    # -geometry +0+0: removes spacing between thumbnails.
    montage_cmd = f"montage /tmp/thumb_*.png -tile x1 -geometry +0+0 {output_sprite}"
    
    print(f"Running Montage: {montage_cmd}")
    subprocess.run(montage_cmd, shell=True, check=True)

    # 4. Create Mesh JSON
    # This captures metadata about the sprite generation.
    actual_thumbs = len(glob.glob("/tmp/thumb_*.png"))
    mesh_data = {
        "input_file": os.path.basename(input_path),
        "thumbnail_count": actual_thumbs,
        "width_per_thumb": width,
        "total_width": width * actual_thumbs
    }
    with open(output_mesh, 'w') as f:
        json.dump(mesh_data, f)

    print(f"--- Processing Complete: {output_sprite} ---")
    return {"mesh": output_mesh, "sprite": output_sprite}

# --- 2. AWS LAMBDA HANDLER ---
def handler(event, context):
    """
    AWS Lambda entry point. 
    Expects JSON: {"input_url": "...", "output_bucket": "...", "n": 24, "i": 120, "W": 240}
    """
    s3 = boto3.client('s3')
    
    # Extract params with defaults
    input_url = event.get('input_url')
    bucket = event.get('output_bucket')
    
    # Lambda environment requires writing to /tmp/
    local_input = "/tmp/video_input.mp4"
    local_mesh = "/tmp/output.json"
    local_sprite = "/tmp/output.png"
    
    try:
        # 1. Download source video from URL (S3 public link or other)
        print(f"Downloading source: {input_url}")
        subprocess.run(["curl", "-L", input_url, "-o", local_input], check=True)

        # 2. Execute the generator
        generate_sprite(
            input_path=local_input,
            num_thumbs=event.get('n', 24),
            interval=event.get('i', 120),
            width=event.get('W', 240),
            output_mesh=local_mesh,
            output_sprite=local_sprite
        )

        # 3. Upload Results to S3
        # Using the Lambda Request ID to ensure unique filenames in S3
        job_id = context.aws_request_id
        s3.upload_file(local_mesh, bucket, f"sprites/{job_id}.json")
        s3.upload_file(local_sprite, bucket, f"sprites/{job_id}.png")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Success',
                's3_path': f"s3://{bucket}/sprites/{job_id}.png"
            })
        }

    except Exception as e:
        print(f"FATAL ERROR: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

# --- 3. CLI ENTRY POINT ---
if __name__ == "__main__":
    """
    Runs when executed directly on your Mac.
    Usage: python3 generate_sprite_v2.py input.mp4 -n 24 -W 240
    """
    parser = argparse.ArgumentParser(description="Manual Sprite Generator")
    parser.add_argument("input_path", help="Path to local video file")
    parser.add_argument("-n", type=int, default=24, help="Number of frames")
    parser.add_argument("-i", type=int, default=120, help="Interval (fps 1/i)")
    parser.add_argument("-W", type=int, default=240, help="Thumbnail width")
    parser.add_argument("-om", default="sprite.json", help="Output JSON path")
    parser.add_argument("-os", default="sprite.png", help="Output PNG path")
    
    args = parser.parse_args()
    
    generate_sprite(
        args.input_path, 
        args.n, 
        args.i, 
        args.W, 
        args.om, 
        args.os
    )
