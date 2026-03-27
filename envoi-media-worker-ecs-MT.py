#!/usr/bin/env python3
import os
import subprocess
import json
import boto3
import math
import uuid
import sys
import time
from datetime import datetime
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from boto3.s3.transfer import TransferConfig

# Global dimensions
W = 240
H = 135 
MAX_WORKERS = 8 

# --- LOGGING UTILITIES ---

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

class Timer:
    def __init__(self, name):
        self.name = name
    def __enter__(self):
        self.start = time.time()
        log(f"STARTING: {self.name}")
        return self
    def __exit__(self, *args):
        self.end = time.time()
        duration = self.end - self.start
        log(f"COMPLETED: {self.name} | Duration: {duration:.2f}s")

def s3_progress_log(bytes_transferred):
    # This can be noisy for small files, but helpful for 5GB+ tracking
    pass 

# --- 1. DOWNLOAD UTILITIES ---

def get_input_file(input_url):
    with Timer(f"Download Input: {input_url}"):
        parsed = urlparse(input_url)
        base_name = os.path.basename(parsed.path) or "input_file"
        local_path = os.path.join("/tmp", base_name)
        
        if input_url.startswith("s3://"):
            s3 = boto3.resource('s3')
            bucket_name = parsed.netloc
            key = parsed.path.lstrip('/')
            
            config = TransferConfig(
                multipart_threshold=1024 * 25, 
                max_concurrency=10,
                multipart_chunksize=1024 * 25, 
                use_threads=True
            )
            
            log(f"Initiating S3 Transfer via Boto3 (Managed Multi-part)")
            s3.Bucket(bucket_name).download_file(key, local_path, Config=config)
        else:
            log(f"Initiating HTTPS Transfer via Curl")
            # Added -v for verbose headers, -L for redirects
            subprocess.run(["curl", "-v", "-L", input_url, "-o", local_path], check=True)
            
        file_size = os.path.getsize(local_path) / (1024 * 1024)
        log(f"File downloaded to {local_path} ({file_size:.2f} MB)")
        return local_path, base_name

# --- 2. METADATA LOGIC ---

def get_complete_metadata_report(file_path):
    with Timer("Metadata Extraction (Exif/FFprobe/MediaInfo)"):
        report = {"file_name": os.path.basename(file_path), "exiftool": {}, "ffprobe": {}, "mediainfo": {}}
        try:
            res = subprocess.run(['exiftool', '-j', file_path], capture_output=True, text=True)
            report['exiftool'] = json.loads(res.stdout)[0]
        except Exception as e: log(f"ExifTool Error: {e}", "WARN")
        
        try:
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', file_path]
            res = subprocess.run(cmd, capture_output=True, text=True)
            report['ffprobe'] = json.loads(res.stdout)
        except Exception as e: log(f"FFprobe Error: {e}", "WARN")
        
        try:
            res = subprocess.run(['mediainfo', '--Output=JSON', file_path], capture_output=True, text=True)
            report['mediainfo'] = json.loads(res.stdout)
        except Exception as e: log(f"MediaInfo Error: {e}", "WARN")
        
        return report

# --- 3. SPRITE & THREADING LOGIC ---

def run_ffmpeg_task(task_args):
    output_path, seek_time, input_path = task_args
    cmd = ["ffmpeg", "-loglevel", "error", "-accurate_seek", "-ss", "{:.9f}".format(seek_time), 
           "-i", input_path, "-vf", f"scale={W}:{H}", "-frames:v", "1", "-q:v", "2", output_path]
    subprocess.run(cmd)
    return output_path if os.path.exists(output_path) else None

def extract_stills_multithreaded(input_path, output_dir, num, den, interval):
    with Timer("Multi-threaded Still Extraction"):
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                                "-of", "default=noprint_wrappers=1:nokey=1", input_path], 
                               capture_output=True, text=True)
        duration_str = probe.stdout.strip()
        duration = float(duration_str) if duration_str else 0
        total_stills = int((duration * num / den) / interval)
        
        log(f"Video Duration: {duration}s | Total stills to extract: {total_stills}")

        tasks = [(os.path.join(output_dir, f"still{i}.jpg"), (den * interval * (i - 0.5)) / num + 0.000000999, input_path) 
                 for i in range(1, total_stills + 1)]
        
        paths = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(run_ffmpeg_task, t) for t in tasks]
            for f in as_completed(futures):
                res = f.result()
                if res: paths.append(res)
        
        log(f"Successfully extracted {len(paths)} still frames")
        return sorted(paths)

def build_sprite_map_multithreaded(paths, output_spritemap):
    if not paths: return
    with Timer("Building Sprite Map (ImageMagick)"):
        count = len(paths)
        rows = int(math.ceil(math.sqrt(count)))
        cols = int(math.ceil(count / rows))
        log(f"Grid Layout: {cols} columns x {rows} rows")
        
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
        
        log("Cleaning up temporary row files and stills...")
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

def process_media(event, context=None):
    from __main__ import get_parameters # In case parameters are in same file
    params = get_parameters(event)
    s3_client = boto3.client('s3')
    
    input_url = params.get('input_url')
    bucket = params.get('output_bucket')
    output_key = params.get('output_key')
    mode = params.get('mode')

    log(f"JOB START | Mode: {mode} | Input: {input_url} | Bucket: {bucket}")

    if not input_url or not bucket:
        log("CRITICAL: Missing input_url or output_bucket.", "ERROR")
        return

    local_input, base_name = get_input_file(input_url)
    
    try:
        if mode == 'metadata':
            report = get_complete_metadata_report(local_input)
            local_meta = f"/tmp/{base_name}_meta.json"
            with open(local_meta, 'w') as f: json.dump(report, f, indent=4)
            
            with Timer(f"Upload Metadata: {output_key}.json"):
                s3_client.upload_file(local_meta, bucket, f"{output_key}.json")

        elif mode == 'waveform':
            ext = os.path.splitext(local_input)[1].lower()
            local_dat = f"/tmp/{base_name}.dat"
            zoom, bits = params['zoom'], params['bits']
            
            with Timer(f"Waveform Generation (Ext: {ext})"):
                if ext in ['.mp3', '.wav', '.aiff', '.aif']:
                    cmd = f"audiowaveform -i {local_input} --output-format dat --zoom {zoom} --bits {bits} -o {local_dat}"
                else:
                    cmd = f"ffmpeg -i {local_input} -map a:0 -f wav - | audiowaveform --input-format wav --output-format dat --zoom {zoom} --bits {bits} --split-channels -o {local_dat}"
                subprocess.run(cmd, shell=True, check=True)
            
            with Timer(f"Upload Waveform: {output_key}.dat"):
                s3_client.upload_file(local_dat, bucket, f"{output_key}.dat")
            
        else: # Sprite mode
            num, den, interval = params['fps_num'], params['fps_den'], params['frame_interval']
            local_sprite = f"/tmp/{base_name}_sprite.jpg"
            local_manifest = f"/tmp/{base_name}_manifest.json"
            
            stills = extract_stills_multithreaded(local_input, "/tmp", num, den, interval)
            build_sprite_map_multithreaded(stills, local_sprite)
            
            manifest_json = build_manifest(stills, num, den, interval)
            with open(local_manifest, 'w') as f: json.dump(manifest_json, f)
            
            with Timer(f"Upload Sprite and Manifest: {output_key}"):
                s3_client.upload_file(local_sprite, bucket, f"{output_key}.jpg")
                s3_client.upload_file(local_manifest, bucket, f"{output_key}.json")

        log(f"JOB SUCCESSFUL | Output: {output_key}")
    except Exception as e:
        log(f"JOB FAILED | Error: {e}", "ERROR")
        sys.exit(1)
    finally:
        if os.path.exists(local_input):
            with Timer("Final Cleanup (local input)"):
                os.remove(local_input)

def get_parameters(event):
    # (Same parameter logic as before...)
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

if __name__ == "__main__":
    process_media({}, None)
