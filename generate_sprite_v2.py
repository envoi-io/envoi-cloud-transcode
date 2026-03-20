#!/usr/bin/env python3

import os
import subprocess
import json
import argparse
import sys
import boto3

# --- 1. CORE PROCESSING LOGIC ---
def generate_sprite(input_path, num_thumbs, interval, width, output_mesh, output_sprite):
    """
    Core logic used by both CLI and Lambda.
    """
    print(f"Processing: {input_path}")
    
    # 1. Generate Thumbnails (Example FFmpeg command)
    # Note: In Lambda, input_path must be a local file in /tmp/
    temp_pattern = "/tmp/thumb_%03d.png"
    ffmpeg_cmd = [
        "ffmpeg", "-i", input_path,
        "-vf", f"fps=1/{interval},scale={width}:-1",
        "-vframes", str(num_thumbs),
        temp_pattern
    ]
    
    print("Running FFmpeg...")
    subprocess.run(ffmpeg_cmd, check=True)

    # 2. Create Sprite Sheet using ImageMagick (magick)
    # This assumes 'magick' is in the path (from your Dockerfile)
    montage_cmd = [
        "magick", "montage", "/tmp/thumb_*.png",
        "-tile", "x1", "-geometry", "+0+0",
        output_sprite
    ]
    
    print("Creating Sprite Sheet...")
    subprocess.run(montage_cmd, check=True)

    # 3. Create Mesh JSON
    mesh_data = {
        "input": input_path,
        "thumbnails": num_thumbs,
        "sprite": output_sprite
    }
    with open(output_mesh, 'w') as f:
        json.dump(mesh_data, f)

    return {"mesh": output_mesh, "sprite": output_sprite}

# --- 2. AWS LAMBDA HANDLER ---
def handler(event, context):
    """
    Entry point for AWS Lambda.
    Expects event: {"input_url": "...", "output_bucket": "...", "n": 24, ...}
    """
    s3 = boto3.client('s3')
    
    # Parameters from Lambda Event
    input_url = event.get('input_url')
    bucket = event.get('output_bucket')
    
    # Local paths (Lambda requires /tmp)
    local_input = "/tmp/input_video.mp4"
    local_mesh = "/tmp/output.json"
    local_sprite = "/tmp/output.png"
    
    try:
        # Download from URL/S3 if needed
        print(f"Downloading {input_url}...")
        subprocess.run(["curl", "-L", input_url, "-o", local_input], check=True)

        # Process
        generate_sprite(
            input_path=local_input,
            num_thumbs=event.get('n', 24),
            interval=event.get('i', 120),
            width=event.get('W', 240),
            output_mesh=local_mesh,
            output_sprite=local_sprite
        )

        # Upload Results to S3
        print(f"Uploading results to {bucket}...")
        s3.upload_file(local_mesh, bucket, "sprites/output.json")
        s3.upload_file(local_sprite, bucket, "sprites/output.png")

        return {'statusCode': 200, 'body': 'Process Complete'}

    except Exception as e:
        print(f"Error: {str(e)}")
        return {'statusCode': 500, 'body': str(e)}

# --- 3. CLI ENTRY POINT ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path")
    parser.add_argument("-n", type=int, default=24)
    parser.add_argument("-i", type=int, default=120)
    parser.add_argument("-W", type=int, default=240)
    parser.add_argument("-om", default="sprite.json")
    parser.add_argument("-os", default="sprite.png")
    
    args = parser.parse_args()
    
    generate_sprite(args.input_path, args.n, args.i, args.W, args.om, args.os)
