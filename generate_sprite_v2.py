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
    """
    print(f"--- Starting Sprite Generation ---")
    print(f"Input: {input_path}")
    
    # Clean up any old thumbnails from previous 'warm' Lambda starts
    for f in glob.glob("/tmp/thumb_*.png"):
        try:
            os.remove(f)
        except OSError:
            pass

    # 1. Generate Thumbnails via FFmpeg
    temp_pattern = "/tmp/thumb_%03d.png"
    ffmpeg_cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"fps=1/{interval},scale={width}:-1",
        "-vframes", str(num_thumbs),
        temp_pattern
    ]
    
    print(f"Running FFmpeg: {' '.join(ffmpeg_cmd)}")
    subprocess.run(ffmpeg_cmd, check=True)

    # 2. Create Sprite Sheet via ImageMagick
    # CRITICAL: We use shell=True and a string so the '*' wildcard expands correctly
    montage_cmd = f"magick montage /tmp/thumb_*.png -tile x1 -geometry +0+0 {output_sprite}"
    
    print(f"Running Montage: {montage_cmd}")
    subprocess.run(montage_cmd, shell=True, check=True)

    # 3. Create Mesh JSON
    mesh_data = {
        "input_file": os.path.basename(input_path),
        "thumbnail_count": len(glob.glob("/tmp/thumb_*.png")),
        "width_per_thumb": width
    }
    with open(output_mesh, 'w') as f:
        json.dump(mesh_data, f)

    print(f"--- Processing Complete ---")
    return {"mesh": output_mesh, "sprite": output_sprite}

# --- 2. AWS LAMBDA HANDLER ---
def handler(event, context):
    """
    AWS Lambda entry point. Translates JSON payload to the processing logic.
    """
    s3 = boto3.client('s3')
    
    # Extract params from Lambda 'Test' payload or S3 trigger
    input_url = event.get('input_url')
    bucket = event.get('output_bucket')
    
    # Lambda requires using /tmp/ for all file writes
    local_input = "/tmp/video_input.mp4"
    local_mesh = "/tmp/output.json"
    local_sprite = "/tmp/output.png"
    
    try:
        # Download the source video
        print(f"Downloading: {input_url}")
        subprocess.run(["curl", "-L", input_url, "-o", local_input], check=True)

        # Run the core logic
        generate_sprite(
            input_path=local_input,
            num_thumbs=event.get('n', 24),
            interval=event.get('i', 120),
            width=event.get('W', 240),
            output_mesh=local_mesh,
            output_sprite=local_sprite
        )

        # Upload results to S3 (using Request ID to ensure unique filenames)
        job_id = context.aws_request_id
        s3.upload_file(local_mesh, bucket, f"outputs/{job_id}.json")
        s3.upload_file(local_sprite, bucket, f"outputs/{job_id}.png")

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Success', 'file': f"outputs/{job_id}.png"})
        }

    except Exception as e:
        print(f"FATAL ERROR: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

# --- 3. CLI ENTRY POINT ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manual Sprite Generator")
    parser.add_argument("input_path", help="Path to local video file")
    parser.add_argument("-n", type=int, default=24, help="Number of frames")
    parser.add_argument("-i", type=int, default=120, help="Interval")
    parser.add_argument("-W", type=int, default=240, help="Width")
    parser.add_argument("-om", default="sprite.json", help="Output JSON path")
    parser.add_argument("-os", default="sprite.png", help="Output PNG path")
    
    args = parser.parse_args()
    generate_sprite(args.input_path, args.n, args.i, args.W, args.om, args.os)
