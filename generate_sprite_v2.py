import os
import subprocess
import json
import argparse
import glob
import boto3
import sys

# --- 1. CORE PROCESSING LOGIC ---
def process_media(event, context=None):
    """
    Core logic: Handles both Sprite generation and Audio Waveform generation.
    """
    # Extract params with defaults
    input_url = event.get('input_url')
    bucket = event.get('output_bucket')
    output_key = event.get('output_key', 'output/processed_file')
    mode = event.get('mode', 'sprite')  # Default to sprite if not specified
    
    # Lambda environment requires writing to /tmp/
    local_input = "/tmp/video_input.mp4"
    local_output = "/tmp/output_file" # Generic local output path
    
    # Clean up /tmp/ for warm starts
    for f in glob.glob("/tmp/thumb_*.png") + [local_input, "/tmp/output.json", "/tmp/output.png", "/tmp/output.dat"]:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass

    try:
        # 1. Download source video
        print(f"Downloading source: {input_url}")
        subprocess.run(["curl", "-L", input_url, "-o", local_input], check=True)

        # 2. Branch logic based on Mode
        if mode == 'waveform':
            print("--- Starting Waveform Generation ---")
            local_output = "/tmp/output.dat"
            zoom = event.get('zoom', 128)
            bits = event.get('bits', 8)
            
            # Use the pipe-based command from your Docker execution
            waveform_cmd = (
                f"ffmpeg -i {local_input} -map a:0 -f wav - | "
                f"audiowaveform --input-format wav --output-format dat "
                f"--zoom {zoom} --bits {bits} --split-channels > {local_output}"
            )
            print(f"Running Waveform Command: {waveform_cmd}")
            subprocess.run(waveform_cmd, shell=True, check=True)
            
        else:
            print("--- Starting Sprite Generation ---")
            local_output = "/tmp/output.png"
            local_mesh = "/tmp/output.json"
            num_thumbs = event.get('n', 24)
            interval = event.get('i', 120)
            width = event.get('W', 240)

            # Generate Thumbs
            temp_pattern = "/tmp/thumb_%03d.png"
            ffmpeg_cmd = ["ffmpeg", "-y", "-i", local_input, "-vf", f"fps=1/{interval},scale={width}:-1", "-vframes", str(num_thumbs), temp_pattern]
            subprocess.run(ffmpeg_cmd, check=True)

            # Create Sprite
            montage_cmd = f"montage /tmp/thumb_*.png -tile x1 -geometry +0+0 {local_output}"
            subprocess.run(montage_cmd, shell=True, check=True)
            
            # Create Mesh (Optional for sprites)
            with open(local_mesh, 'w') as f:
                json.dump({"input": input_url, "thumbs": num_thumbs}, f)
            if bucket:
                s3 = boto3.client('s3')
                s3.upload_file(local_mesh, bucket, f"{output_key}.json")

        # 3. Upload Result to S3
        if bucket:
            s3 = boto3.client('s3')
            final_s3_key = output_key if output_key.endswith(('.dat', '.png')) else f"{output_key}.dat" if mode == 'waveform' else f"{output_key}.png"
            print(f"Uploading result to s3://{bucket}/{final_s3_key}")
            s3.upload_file(local_output, bucket, final_s3_key)
            return {'statusCode': 200, 'body': f"Success: {final_s3_key}"}
        
        return {'statusCode': 200, 'body': 'Process complete (No S3 upload requested)'}

    except Exception as e:
        print(f"FATAL ERROR: {str(e)}")
        return {'statusCode': 500, 'body': str(e)}

# --- 2. AWS LAMBDA HANDLER ---
def handler(event, context):
    return process_media(event, context)

# --- 3. CLI ENTRY POINT ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Envoi Media Worker CLI")
    parser.add_argument("input", help="Path or URL to input video")
    parser.add_argument("--mode", choices=['sprite', 'waveform'], default='sprite')
    parser.add_argument("-n", type=int, default=24, help="Number of frames (Sprite)")
    parser.add_argument("-W", type=int, default=240, help="Width (Sprite)")
    parser.add_argument("--zoom", type=int, default=128, help="Zoom (Waveform)")
    parser.add_argument("--bits", type=int, default=8, help="Bits (Waveform)")
    
    args = parser.parse_args()
    
    # Mock an event object for the core logic
    cli_event = {
        "input_url": args.input,
        "mode": args.mode,
        "n": args.n,
        "W": args.W,
        "zoom": args.zoom,
        "bits": args.bits
    }
    process_media(cli_event)
