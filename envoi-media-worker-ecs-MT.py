#!/usr/bin/env python3
import os
import subprocess
import json
import glob
import boto3
import math
import uuid
import sys
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Global dimensions
W = 240
H = 135 
MAX_WORKERS = 8  # Adjust based on ECS CPU (4 vCPU = ~8-16 workers)

# --- 1. DOWNLOAD UTILITIES ---

def download_s3_chunked(s3_url, local_path):
    """Downloads S3 object using chunked Range requests (up to 5GB chunks)."""
    s3 = boto3.client('s3')
    parsed = urlparse(s3_url)
    bucket = parsed.netloc
    key = parsed.path.lstrip('/')
    
    # Get total file size
    response = s3.head_object(Bucket=bucket, Key=key)
    total_size = response['ContentLength']
    chunk_size = 1024 * 1024 * 1024 # 1GB chunks (safe for memory)
    
    print(f"Downloading s3://{bucket}/{key} ({total_size} bytes) in chunks...")
    
    with open(local_path, 'wb') as f:
        for start in range(0, total_size, chunk_size):
            end = min(start + chunk_size - 1, total_size - 1)
            byte_range = f'bytes={start}-{end}'
            
            chunk_resp = s3.get_object(Bucket=bucket, Key=key, Range=byte_range)
            f.write(chunk_resp['Body'].read())
            print(f"  Downloaded bytes {start} through {end}")

def get_input_file(input_url):
    """Handles both HTTPS and S3 inputs, returns local filename based on basename."""
    parsed = urlparse(input_url)
    base_name = os.path.basename(parsed.path)
    if not base_name:
        base_name = "input_file"
        
    local_path = os.path.join("/tmp", base_name)
    
    if input_url.startswith("s3://"):
        download_s3_chunked(input_url, local_path)
    else:
        print(f"Downloading via HTTPS: {input_url}")
        subprocess.run(["curl", "-L", input_url, "-o", local_path], check=True)
        
    return local_path, base_name

# --- 2. MULTI-THREADED PROCESSING ---

def run_ffmpeg_task(task_args):
    """Helper for threading individual FFmpeg still extractions."""
    output_path, seek_time, input_path = task_args
    cmd = [
        "ffmpeg", "-loglevel", "error", "-accurate_seek",
        "-ss", "{:.9f}".format(seek_time), 
        "-i", input_path,
        "-vf", f"scale={W}:{H}", 
        "-frames:v", "1", "-update", "1", output_path
    ]
    subprocess.run(cmd)
    return output_path if os.path.exists(output_path) else None

def extract_stills_multithreaded(input_path, output_dir, num, den, interval):
    """Extracts stills using a ThreadPool to speed up FFmpeg seeking."""
    # First, probe for total duration to know how many stills to extract
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration", 
        "-of", "default=noprint_wrappers=1:nokey=1", input_path
    ], capture_output=True, text=True)
    
    duration = float(probe.stdout.strip())
    total_stills = int((duration * num / den) / interval)
    print(f"Detected duration {duration}s. Planning {total_stills} stills.")

    tasks = []
    for i in range(1, total_stills + 1):
        output = os.path.join(output_dir, f"still{i}.png")
        seek_time = (den * interval * (i - 0.5)) / num + 0.000000999
        tasks.append((output, seek_time, input_path))

    paths = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(run_ffmpeg_task, t): t for t in tasks}
        for future in as_completed(futures):
            res = future.result()
            if res: paths.append(res)
            
    return sorted(paths)

def build_row(args):
    """Helper for threading ImageMagick row stitching."""
    binary, batch, temp_row = args
    subprocess.run([binary] + batch + ["+append", temp_row])
    return temp_row

def build_sprite_map_multithreaded(paths, output_spritemap):
    """Stitches rows in parallel, then combines into final JPG."""
    if not paths: return
    
    rows, columns = get_rows_and_columns(paths)
    binary = "convert" 
    row_tasks = []
    
    for i in range(rows):
        temp_row = f"/tmp/row_{i}_{uuid.uuid4()}.png"
        start = i * columns
        current_batch = paths[start:start + columns]
        if current_batch:
            row_tasks.append((binary, current_batch, temp_row))

    # Parallelize Row Generation
    row_paths = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        row_paths = list(executor.map(build_row, row_tasks))
    
    # Final Vertical Stitch
    if row_paths:
        cmd = [binary] + row_paths + [
            "-append", "-quality", "80", "-interlace", "Plane", 
            "-sampling-factor", "4:2:0", output_spritemap
        ]
        subprocess.run(cmd)
        
    for p in row_paths:
        if os.path.exists(p): os.remove(p)

# --- 3. HELPER FUNCTIONS ---

def get_rows_and_columns(paths):
    count = len(paths)
    rows = int(math.ceil(math.sqrt(count)))
    columns = int(math.ceil(count / rows))
    return rows, columns

# --- 4. MAIN HANDLER ---

def process_media(event, context=None):
    from generate_sprite_v2 import get_parameters # assuming standard helper
    params = get_parameters(event)
    
    s3 = boto3.client('s3')
    input_url = params.get('input_url')
    bucket = params.get('output_bucket')
    output_key = params.get('output_key', 'output/media')
    mode = params.get('mode', 'sprite')

    # 1. Download and get smart basenames
    local_input, base_name = get_input_file(input_url)
    
    # Define outputs based on the basename
    local_sprite = f"/tmp/{base_name}_sprite.jpg"
    local_manifest = f"/tmp/{base_name}_manifest.json"
    local_dat = f"/tmp/{base_name}.dat"
    local_meta = f"/tmp/{base_name}_metadata.json"

    try:
        if mode == 'metadata':
            from generate_sprite_v2 import get_complete_metadata_report
            report = get_complete_metadata_report(local_input)
            with open(local_meta, 'w') as f:
                json.dump(report, f, indent=4)
            s3.upload_file(local_meta, bucket, f"{output_key}.json")

        elif mode == 'waveform':
            print("--- Generating Waveform ---")
            zoom = params.get('zoom', 128)
            bits = params.get('bits', 8)
            ext = os.path.splitext(local_input)[1].lower()
            
            # Logic for direct vs piped FFmpeg
            if ext in ['.mp3', '.wav', '.aiff', '.aif']:
                waveform_cmd = f"audiowaveform -i {local_input} --output-format dat --zoom {zoom} --bits {bits} -o {local_dat}"
            else:
                waveform_cmd = (
                    f"ffmpeg -i {local_input} -map a:0 -f wav - | "
                    f"audiowaveform --input-format wav --output-format dat "
                    f"--zoom {zoom} --bits {bits} --split-channels -o {local_dat}"
                )
            
            subprocess.run(waveform_cmd, shell=True, check=True)
            s3.upload_file(local_dat, bucket, f"{output_key}.dat")
            
        else: # Sprite mode
            print("--- Generating Parallelized Sprite ---")
            num, den = params.get('fps_num', 24000), params.get('fps_den', 1001)
            interval = params.get('frame_interval', 300)

            stills = extract_stills_multithreaded(local_input, "/tmp", num, den, interval)
            build_sprite_map_multithreaded(stills, local_sprite)
            
            from generate_sprite_v2 import build_manifest
            manifest = build_manifest(stills, num, den, interval)
            with open(local_manifest, 'w') as f:
                json.dump(manifest, f)

            s3.upload_file(local_sprite, bucket, f"{output_key}.jpg")
            s3.upload_file(local_manifest, bucket, f"{output_key}.json")

        return {'statusCode': 200, 'body': f"Success: {output_key}"}

    except Exception as e:
        print(f"FATAL ERROR: {e}")
        return {'statusCode': 500, 'body': str(e)}

if __name__ == "__main__":
    process_media({}, None)
