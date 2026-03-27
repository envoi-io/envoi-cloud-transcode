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
from boto3.s3.transfer import TransferConfig

# Global dimensions
W = 240
H = 135 
MAX_WORKERS = 8 

# --- 1. DOWNLOAD UTILITIES ---

def get_input_file(input_url):
    """Handles S3 and HTTPS, optimized for files > 5GB."""
    parsed = urlparse(input_url)
    base_name = os.path.basename(parsed.path) or "input_file"
    local_path = os.path.join("/tmp", base_name)
    
    if input_url.startswith("s3://"):
        s3 = boto3.resource('s3')
        bucket_name = parsed.netloc
        key = parsed.path.lstrip('/')
        
        # Managed transfer config for large files
        config = TransferConfig(multipart_threshold=1024 * 25, max_concurrency=10,
                                multipart_chunksize=1024 * 25, use_threads=True)
        
        print(f"Downloading S3 object: {input_url} to {local_path}")
        s3.Bucket(bucket_name).download_file(key, local_path, Config=config)
    else:
        print(f"Downloading HTTPS: {input_url}")
        subprocess.run(["curl", "-L", input_url, "-o", local_path], check=True)
        
    return local_path, base_name

# --- 2. METADATA LOGIC ---

def get_complete_metadata_report(file_path):
    report = {"file_name": os.path.basename(file_path), "exiftool": {}, "ffprobe": {}, "mediainfo": {}}
    try:
        res = subprocess.run(['exiftool', '-j', file_path], capture_output=True, text=True)
        report['exiftool'] = json.loads(res.stdout)[0]
    except: pass
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', file_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        report['ffprobe'] = json.loads(res.stdout)
    except: pass
    try:
        res = subprocess.run(['mediainfo', '--Output=JSON', file_path], capture_output=True, text=True)
        report['mediainfo'] = json.loads(res.stdout)
    except: pass
    return report

# --- 3. SPRITE & THREADING LOGIC ---

def run_ffmpeg_task(task_args):
    """Saves stills as JPG to save disk space on large files."""
    output_path, seek_time, input_path = task_args
    # Using -q:v 2 for high quality JPG stills, much smaller than PNG
    cmd = ["ffmpeg", "-loglevel", "error", "-accurate_seek", "-ss", "{:.9f}".format(seek_time), 
           "-i", input_path, "-vf", f"scale={W}:{H}", "-frames:v", "1", "-q:v", "2", output_path]
    subprocess.run(cmd)
    return output_path if os.path.exists(output_path) else None

def extract_stills_multithreaded(input_path, output_dir, num, den, interval):
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                            "-of", "default=noprint_wrappers=1:nokey=1", input_path], 
                           capture_output=True, text=True)
    duration_str = probe.stdout.strip()
    duration = float(duration_str) if duration_str else 0
    total_stills = int((duration * num / den) / interval)
    
    # Changed extension to .jpg for temporary stills
    tasks = [(os.path.join(output_dir, f"still{i}.jpg"), (den * interval * (i - 0.5)) / num + 0.000000999, input_path) 
             for i in range(1, total_stills + 1)]
    
    paths = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(run_ffmpeg_task, t) for t in tasks]
        for f in as_completed(futures):
            res = f.result()
            if res: paths.append(res)
    return sorted(paths)

def build_sprite_map_multithreaded(paths, output_spritemap):
    if not paths: return
    count = len(paths)
    rows = int(math.ceil(math.sqrt(count)))
    cols = int(math.ceil(count / rows))
    
    row_tasks = []
    for i in range(rows):
        temp_row = f"/tmp/row_{i}_{uuid.uuid4()}.jpg"
        batch = paths[i*cols : (i+1)*cols]
        if batch: row_tasks.append((batch, temp_row))

    def stitch_row(args):
        batch, out = args
        subprocess.run(["convert"] + batch + ["+append", out])
        return out

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        row_paths = list(executor.map(stitch_row, row_tasks))
    
    if row_paths:
        subprocess.run(["convert"] + row_paths + ["-append", "-quality", "80", "-interlace", "Plane", output_spritemap])
    
    # Aggressive Cleanup
    for p in row_paths + paths: 
        if os.path.exists(p): os.remove(p)

def build_manifest(paths, num, den, interval):
    count = len(paths)
    rows = int(math.ceil(math.sqrt(count)))
    cols = int(math.ceil(count / rows))
    sprites = []
    for i in range(count):
        sprites.append({
            "x": W * (i % cols), "y": H * int(i / cols),
            "t": round((705600000.0 * interval * (i + 0.5) * den) / num)
        })
    return {"width": W, "height": H, "sprites": sprites}

# --- 4. RUNTIME LOGIC ---

def get_parameters(event):
    params = event if event else {}
    env_mapping = {
        'input_url': os.environ.get('input_url'), 
        'output_bucket': os.environ.get('output_bucket'),
        'output_key': os.environ.get('output_key', 'output/media'), 
        'mode': os.environ.get('mode', 'sprite'),
        'zoom': os.environ.get('zoom', '128'), 
        'bits': os.environ.get('bits', '8'),
        'fps_num': os.environ.get('fps_num', '24000'), 
        'fps_den': os.environ.get('fps_den', '1001'),
        'frame_interval': os.environ.get('frame_interval', '300')
    }
    for k, v in env_mapping.items():
        if k not in params or params[k] is None:
            if k in ['zoom', 'bits', 'fps_num', 'fps_den', 'frame_interval'] and v: 
                params[k] = int(v)
            else: 
                params[k] = v
    return params

def process_media(event, context=None):
    params = get_parameters(event)
    s3_client = boto3.client('s3')
    
    input_url = params.get('input_url')
    bucket = params.get('output_bucket')
    output_key = params.get('output_key')
    mode = params.get('mode')

    if not input_url or not bucket:
        print("Missing input_url or output_bucket.")
        return

    local_input, base_name = get_input_file(input_url)
    
    try:
        if mode == 'metadata':
            report = get_complete_metadata_report(local_input)
            local_meta = f"/tmp/{base_name}_meta.json"
            with open(local_meta, 'w') as f: json.dump(report, f, indent=4)
            s3_client.upload_file(local_meta, bucket, f"{output_key}.json")

        elif mode == 'waveform':
            ext = os.path.splitext(local_input).lower()
            local_dat = f"/tmp/{base_name}.dat"
            zoom, bits = params['zoom'], params['bits']
            if ext in ['.mp3', '.wav', '.aiff', '.aif']:
                cmd = f"audiowaveform -i {local_input} --output-format dat --zoom {zoom} --bits {bits} -o {local_dat}"
            else:
                cmd = f"ffmpeg -i {local_input} -map a:0 -f wav - | audiowaveform --input-format wav --output-format dat --zoom {zoom} --bits {bits} --split-channels -o {local_dat}"
            subprocess.run(cmd, shell=True, check=True)
            s3_client.upload_file(local_dat, bucket, f"{output_key}.dat")
            
        else: # Sprite mode
            num, den, interval = params['fps_num'], params['fps_den'], params['frame_interval']
            local_sprite = f"/tmp/{base_name}_sprite.jpg"
            local_manifest = f"/tmp/{base_name}_manifest.json"
            
            stills = extract_stills_multithreaded(local_input, "/tmp", num, den, interval)
            build_sprite_map_multithreaded(stills, local_sprite)
            
            manifest_json = build_manifest(stills, num, den, interval)
            with open(local_manifest, 'w') as f: json.dump(manifest_json, f)
            
            s3_client.upload_file(local_sprite, bucket, f"{output_key}.jpg")
            s3_client.upload_file(local_manifest, bucket, f"{output_key}.json")

        print(f"Job successfully finished: {output_key}")
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        sys.exit(1)
    finally:
        # Final cleanup of the big video file
        if os.path.exists(local_input):
            os.remove(local_input)

if __name__ == "__main__":
    process_media({}, None)
