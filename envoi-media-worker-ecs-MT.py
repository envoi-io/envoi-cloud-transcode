#!/usr/bin/env python3
import os
import subprocess
import json
import boto3
import math
import uuid
import sys
import time
import threading
from datetime import datetime
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from boto3.s3.transfer import TransferConfig

# Global settings
W = 240
H = 135 
MAX_WORKERS = 8 

# --- 1. ROBUST LOGGING SYSTEM ---

class RobustLogger:
    def __init__(self):
        self._lock = threading.Lock()

    def emit(self, level, module, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        thread_id = threading.get_ident()
        with self._lock:
            # Format: [Time] [Level] [Thread] [Module] Message
            print(f"[{timestamp}] [{level:7}] [T-{thread_id}] [{module:12}] {message}")
            sys.stdout.flush()

    def info(self, module, msg): self.emit("INFO", module, msg)
    def warn(self, module, msg): self.emit("WARNING", module, msg)
    def error(self, module, msg): self.emit("ERROR", module, msg)

logger = RobustLogger()

class ProgressPercentage(object):
    def __init__(self, filename, size, module):
        self._filename = filename
        self._size = size
        self._seen_so_far = 0
        self._lock = threading.Lock()
        self._module = module
        self._last_report = 0

    def __call__(self, bytes_amount):
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            # Report every 10% to avoid flooding logs
            if percentage - self._last_report >= 10 or percentage >= 100:
                logger.info(self._module, f"Progress: {percentage:.1f}% ({self._seen_so_far}/{self._size} bytes)")
                self._last_report = percentage

# --- 2. ENHANCED UTILITIES ---

def run_command(cmd, module_name, shell=False):
    """Logs start, end, and full output of subprocesses."""
    start_time = time.time()
    cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
    logger.info(module_name, f"Executing: {cmd_str}")
    
    try:
        result = subprocess.run(
            cmd, shell=shell, check=True, 
            capture_output=True, text=True
        )
        duration = time.time() - start_time
        logger.info(module_name, f"Finished in {duration:.2f}s (Exit 0)")
        return result
    except subprocess.CalledProcessError as e:
        logger.error(module_name, f"Command Failed (Exit {e.returncode})")
        logger.error(module_name, f"STDOUT: {e.stdout}")
        logger.error(module_name, f"STDERR: {e.stderr}")
        raise

# --- 3. DOWNLOAD/UPLOAD LOGIC ---

def get_input_file(input_url):
    module = "DOWNLOADER"
    parsed = urlparse(input_url)
    base_name = os.path.basename(parsed.path) or "input_file"
    local_path = os.path.join("/tmp", base_name)
    
    start_time = time.time()
    
    if input_url.startswith("s3://"):
        s3 = boto3.resource('s3')
        bucket_name = parsed.netloc
        key = parsed.path.lstrip('/')
        
        obj = s3.Object(bucket_name, key)
        size = obj.content_length
        
        logger.info(module, f"Starting S3 Download: {input_url} ({size} bytes)")
        progress = ProgressPercentage(base_name, size, module)
        config = TransferConfig(multipart_threshold=1024*50, max_concurrency=10, use_threads=True)
        
        obj.download_file(local_path, Config=config, Callback=progress)
    else:
        logger.info(module, f"Starting HTTPS Download: {input_url}")
        # Added --progress-bar equivalent or silent with logging
        run_command(["curl", "-f", "-L", "-v", input_url, "-o", local_path], module)
        
    duration = time.time() - start_time
    logger.info(module, f"Total Download Time: {duration:.2f}s for {local_path}")
    return local_path, base_name

# --- 4. PROCESSING FUNCTIONS ---

def run_ffmpeg_task(task_args):
    output_path, seek_time, input_path = task_args
    module = "FFMPEG-TASK"
    # Individual task logging is minimal to prevent log-lock, but reports error if failed
    cmd = ["ffmpeg", "-loglevel", "error", "-accurate_seek", "-ss", f"{seek_time:.9f}", 
           "-i", input_path, "-vf", f"scale={W}:{H}", "-frames:v", "1", "-q:v", "2", output_path]
    try:
        subprocess.run(cmd, check=True)
        return output_path
    except Exception as e:
        logger.error(module, f"Failed at {seek_time}s: {e}")
        return None

def extract_stills_multithreaded(input_path, output_dir, num, den, interval):
    module = "STILLS-EXEC"
    logger.info(module, "Probing video duration...")
    probe = run_command(["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                         "-of", "default=noprint_wrappers=1:nokey=1", input_path], module)
    
    duration = float(probe.stdout.strip() or 0)
    total_stills = int((duration * num / den) / interval)
    logger.info(module, f"Extracing {total_stills} stills in parallel (Workers: {MAX_WORKERS})")

    tasks = [(os.path.join(output_dir, f"still{i}.jpg"), (den * interval * (i - 0.5)) / num, input_path) 
             for i in range(1, total_stills + 1)]
    
    paths = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(run_ffmpeg_task, t): t for t in tasks}
        completed = 0
        for f in as_completed(futures):
            res = f.result()
            if res: paths.append(res)
            completed += 1
            if completed % 20 == 0 or completed == total_stills:
                logger.info(module, f"Extraction progress: {completed}/{total_stills} frames")
                
    return sorted(paths)

def build_sprite_map_multithreaded(paths, output_spritemap):
    module = "IMAGEMAGICK"
    if not paths: return
    
    count = len(paths)
    rows = int(math.ceil(math.sqrt(count)))
    cols = int(math.ceil(count / rows))
    logger.info(module, f"Stitching {count} images into {cols}x{rows} grid")
    
    row_tasks = []
    for i in range(rows):
        temp_row = f"/tmp/row_{i}_{uuid.uuid4()}.jpg"
        batch = paths[i*cols : (i+1)*cols]
        if batch: row_tasks.append((batch, temp_row))

    def stitch_row(args):
        batch, out = args
        subprocess.run(["convert"] + batch + ["+append", out], check=True)
        return out

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        row_paths = list(executor.map(stitch_row, row_tasks))
        logger.info(module, f"Completed horizontal stitching of {len(row_paths)} rows")
    
    logger.info(module, "Final vertical stitch and optimization...")
    run_command(["convert"] + row_paths + ["-append", "-quality", "80", "-interlace", "Plane", output_spritemap], module)
    
    for p in row_paths + paths: 
        if os.path.exists(p): os.remove(p)

# --- 5. MAIN ORCHESTRATION ---

def process_media(event, context=None):
    from __main__ import get_parameters
    params = get_parameters(event)
    s3_client = boto3.client('s3')
    
    input_url = params.get('input_url')
    bucket = params.get('output_bucket')
    output_key = params.get('output_key')
    mode = params.get('mode')

    logger.info("MAIN", f"--- NEW JOB RECEIVED [Mode: {mode}] ---")
    
    try:
        local_input, base_name = get_input_file(input_url)
        
        if mode == 'metadata':
            logger.info("METADATA", "Starting report generation")
            # Logic for metadata... (omitted for brevity, remains same as previous)
            pass

        elif mode == 'waveform':
            ext = os.path.splitext(local_input)[1].lower()
            local_dat = f"/tmp/{base_name}.dat"
            zoom, bits = params['zoom'], params['bits']
            
            logger.info("WAVEFORM", f"Generating waveform (Ext: {ext})")
            if ext in ['.mp3', '.wav', '.aiff', '.aif']:
                cmd = f"audiowaveform -i {local_input} --output-format dat --zoom {zoom} --bits {bits} -o {local_dat}"
            else:
                cmd = f"ffmpeg -i {local_input} -map a:0 -f wav - | audiowaveform --input-format wav --output-format dat --zoom {zoom} --bits {bits} --split-channels -o {local_dat}"
            
            run_command(cmd, "WAVEFORM", shell=True)
            
            size = os.path.getsize(local_dat)
            logger.info("UPLOAD", f"Uploading waveform: {output_key}.dat")
            s3_client.upload_file(local_dat, bucket, f"{output_key}.dat")

        else: # Sprite mode
            num, den, interval = params['fps_num'], params['fps_den'], params['frame_interval']
            local_sprite = f"/tmp/{base_name}_sprite.jpg"
            local_manifest = f"/tmp/{base_name}_manifest.json"
            
            stills = extract_stills_multithreaded(local_input, "/tmp", num, den, interval)
            build_sprite_map_multithreaded(stills, local_sprite)
            
            with open(local_manifest, 'w') as f:
                json.dump(build_manifest(stills, num, den, interval), f)
            
            logger.info("UPLOAD", "Uploading final Sprite and Manifest")
            s3_client.upload_file(local_sprite, bucket, f"{output_key}.jpg")
            s3_client.upload_file(local_manifest, bucket, f"{output_key}.json")

        logger.info("MAIN", "--- JOB COMPLETED SUCCESSFULLY ---")
        
    except Exception as e:
        logger.error("MAIN", f"JOB FAILED: {str(e)}")
        sys.exit(1)
    finally:
        if 'local_input' in locals() and os.path.exists(local_input):
            os.remove(local_input)
            logger.info("CLEANUP", f"Deleted local input {local_input}")

def get_parameters(event):
    # Parameter mapping logic remains same
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
