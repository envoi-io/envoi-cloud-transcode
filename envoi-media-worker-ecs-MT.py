#!/usr/bin/env python3
import warnings
# --- 0. SILENCE DEPRECATION WARNINGS ---
# This suppresses the Boto3 Python 3.7 end-of-life warning
warnings.filterwarnings("ignore", category=PythonDeprecationWarning) if 'PythonDeprecationWarning' in globals() else None
warnings.filterwarnings("ignore", message=".*Boto3 will no longer support Python 3.7.*")

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

# Global Settings
W = 240
H = 135 
MAX_WORKERS = 8 

# --- 1. REAL-TIME LOGGING ENGINE ---

class RobustLogger:
    def __init__(self):
        self._lock = threading.Lock()

    def emit(self, level, module, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        t_name = threading.current_thread().name
        with self._lock:
            # Explicitly writing to stdout and flushing immediately for CloudWatch
            sys.stdout.write(f"[{timestamp}] [{level:7}] [{t_name:12}] [{module:12}] {message}\n")
            sys.stdout.flush()

    def info(self, module, msg): self.emit("INFO", module, msg)
    def warn(self, module, msg): self.emit("WARNING", module, msg)
    def error(self, module, msg): self.emit("ERROR", module, msg)

logger = RobustLogger()

def run_command_streaming(cmd, module_name, shell=False):
    """Executes a command and streams STDOUT/STDERR to logs line-by-line."""
    start_time = time.time()
    cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
    logger.info(module_name, f"EXEC START: {cmd_str}")

    process = subprocess.Popen(
        cmd,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, 
        text=True,
        bufsize=1,
        universal_newlines=True
    )

    for line in iter(process.stdout.readline, ""):
        clean_line = line.strip()
        if clean_line:
            logger.info(f"{module_name}-RAW", clean_line)

    process.stdout.close()
    return_code = process.wait()
    duration = time.time() - start_time

    if return_code != 0:
        logger.error(module_name, f"CRITICAL FAILURE: Exit Code {return_code}")
        raise subprocess.CalledProcessError(return_code, cmd)
    
    logger.info(module_name, f"EXEC END | Duration: {duration:.2f}s")
    return True

# --- 2. DETAILED S3 PROGRESS TRACKING ---

class S3Progress(object):
    def __init__(self, filename, size, module):
        self._filename = filename
        self._size = size
        self._seen = 0
        self._lock = threading.Lock()
        self._module = module
        self._last_report_time = time.time()
        self._last_report_bytes = 0

    def __call__(self, bytes_amount):
        with self._lock:
            self._seen += bytes_amount
            now = time.time()
            delta_time = now - self._last_report_time
            
            # Report every 2 seconds for visibility
            if delta_time >= 2.0 or self._seen == self._size:
                percent = (self._seen / self._size) * 100
                bytes_since_last = self._seen - self._last_report_bytes
                speed = (bytes_since_last / delta_time) / (1024 * 1024) if delta_time > 0 else 0
                
                logger.info(self._module, 
                    f"Transfer: {percent:.1f}% | "
                    f"{self._seen // (1024*1024)}MB / {self._size // (1024*1024)}MB | "
                    f"Speed: {speed:.2f} MB/s"
                )
                
                self._last_report_time = now
                self._last_report_bytes = self._seen

# --- 3. CORE LOGIC FUNCTIONS ---

def get_input_file(input_url):
    module = "DOWNLOAD"
    parsed = urlparse(input_url)
    base_name = os.path.basename(parsed.path) or f"input_{uuid.uuid4().hex[:8]}"
    local_path = os.path.join("/tmp", base_name)
    
    if input_url.startswith("s3://"):
        s3 = boto3.resource('s3')
        bucket_name = parsed.netloc
        key = parsed.path.lstrip('/')
        
        obj = s3.Object(bucket_name, key)
        size = obj.content_length
        
        logger.info(module, f"S3 Source: s3://{bucket_name}/{key} ({size} bytes)")
        
        config = TransferConfig(
            multipart_threshold=1024 * 25, 
            max_concurrency=10,
            multipart_chunksize=1024 * 25,
            use_threads=True
        )
        
        progress = S3Progress(base_name, size, module)
        obj.download_file(local_path, Config=config, Callback=progress)
        logger.info(module, "S3 Download Complete.")
    else:
        # Curl -v and -# for real-time progress bar streaming
        run_command_streaming(["curl", "-f", "-L", "-v", "-#", input_url, "-o", local_path], module)
        
    return local_path, base_name

def run_ffmpeg_task(task_args):
    output_path, seek_time, input_path = task_args
    module = "FFMPEG-THUMB"
    cmd = ["ffmpeg", "-loglevel", "info", "-accurate_seek", "-ss", f"{seek_time:.6f}", 
           "-i", input_path, "-vf", f"scale={W}:{H}", "-frames:v", "1", "-q:v", "2", output_path]
    
    try:
        run_command_streaming(cmd, module)
        return output_path
    except:
        return None

def extract_stills_multithreaded(input_path, output_dir, num, den, interval):
    module = "STILLS-ORCH"
    logger.info(module, "Probing video duration...")
    
    res = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                          "-of", "default=noprint_wrappers=1:nokey=1", input_path], 
                         capture_output=True, text=True)
    duration = float(res.stdout.strip() or 0)
    total_stills = int((duration * num / den) / interval)
    
    logger.info(module, f"Duration: {duration}s. Target: {total_stills} frames.")

    tasks = [(os.path.join(output_dir, f"still_{i}.jpg"), (den * interval * (i - 0.5)) / num, input_path) 
             for i in range(1, total_stills + 1)]
    
    paths = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="Extract") as executor:
        futures = {executor.submit(run_ffmpeg_task, t): t for t in tasks}
        for f in as_completed(futures):
            res = f.result()
            if res: paths.append(res)

    return sorted(paths)

def build_sprite_map_multithreaded(paths, output_spritemap):
    module = "IMAGEMAGICK"
    count = len(paths)
    if count == 0: return
    
    rows = int(math.ceil(math.sqrt(count)))
    cols = int(math.ceil(count / rows))
    
    row_tasks = []
    for i in range(rows):
        temp_row = f"/tmp/row_{i}_{uuid.uuid4().hex}.jpg"
        batch = paths[i*cols : (i+1)*cols]
        if batch: row_tasks.append((batch, temp_row))

    def stitch_row(args):
        batch, out = args
        run_command_streaming(["convert"] + batch + ["+append", out], "IM-ROW")
        return out

    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="Stitch") as executor:
        row_paths = list(executor.map(stitch_row, row_tasks))
    
    logger.info(module, f"Combining {len(row_paths)} rows into final sprite sheet.")
    run_command_streaming(["convert"] + row_paths + ["-append", "-quality", "80", "-interlace", "Plane", output_spritemap], module)
    
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

# --- 4. MAIN ORCHESTRATION ---

def process_media(event, context=None):
    params = get_parameters(event)
    s3_client = boto3.client('s3')
    
    input_url = params.get('input_url')
    bucket = params.get('output_bucket')
    output_key = params.get('output_key')
    mode = params.get('mode')

    logger.info("MAIN", "--- WORKER START ---")
    
    try:
        local_input, base_name = get_input_file(input_url)
        
        if mode == 'metadata':
            logger.info("METADATA", "Generating Metadata...")
            run_command_streaming(["mediainfo", "--Output=JSON", local_input], "MEDIAINFO")
            pass

        elif mode == 'waveform':
            ext = os.path.splitext(local_input)[1].lower()
            local_dat = f"/tmp/{base_name}.dat"
            zoom, bits = params.get('zoom', 128), params.get('bits', 8)
            
            if ext in ['.mp3', '.wav', '.aiff', '.aif']:
                cmd = f"audiowaveform -i {local_input} --output-format dat --zoom {zoom} --bits {bits} -o {local_dat}"
            else:
                cmd = f"ffmpeg -i {local_input} -map a:0 -f wav - | audiowaveform --input-format wav --output-format dat --zoom {zoom} --bits {bits} --split-channels -o {local_dat}"
            
            run_command_streaming(cmd, "WAVEFORM", shell=True)
            s3_client.upload_file(local_dat, bucket, f"{output_key}.dat")

        else: # Sprite mode
            num, den, interval = params['fps_num'], params['fps_den'], params['frame_interval']
            local_sprite = f"/tmp/{base_name}_sprite.jpg"
            local_manifest = f"/tmp/{base_name}_manifest.json"
            
            stills = extract_stills_multithreaded(local_input, "/tmp", num, den, interval)
            build_sprite_map_multithreaded(stills, local_sprite)
            
            manifest_data = build_manifest(stills, num, den, interval)
            with open(local_manifest, 'w') as f:
                json.dump(manifest_data, f)
            
            logger.info("UPLOAD", "Uploading Sprite and Manifest.")
            s3_client.upload_file(local_sprite, bucket, f"{output_key}.jpg")
            s3_client.upload_file(local_manifest, bucket, f"{output_key}.json")

        logger.info("MAIN", "--- JOB FINISHED SUCCESSFULLY ---")
        
    except Exception as e:
        logger.error("MAIN", f"FATAL ERROR: {str(e)}")
        sys.exit(1)
    finally:
        if 'local_input' in locals() and os.path.exists(local_input):
            os.remove(local_input)

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

if __name__ == "__main__":
    process_media({}, None)
