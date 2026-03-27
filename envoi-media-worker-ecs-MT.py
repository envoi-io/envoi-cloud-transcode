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
        # Get the name of the current thread (useful for parallel FFmpeg)
        t_name = threading.current_thread().name
        with self._lock:
            print(f"[{timestamp}] [{level:7}] [{t_name:12}] [{module:12}] {message}")
            sys.stdout.flush()

    def info(self, module, msg): self.emit("INFO", module, msg)
    def warn(self, module, msg): self.emit("WARNING", module, msg)
    def error(self, module, msg): self.emit("ERROR", module, msg)

logger = RobustLogger()

def run_command_streaming(cmd, module_name, shell=False):
    """
    Executes a command and streams STDOUT and STDERR to logs in real-time.
    """
    start_time = time.time()
    cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
    logger.info(module_name, f"EXEC START: {cmd_str}")

    process = subprocess.Popen(
        cmd,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, # Merge stderr into stdout for tools like ffmpeg/curl
        text=True,
        bufsize=1,
        universal_newlines=True
    )

    # Stream output line by line
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

# --- 2. S3 PROGRESS TRACKING ---

class S3Progress(object):
    def __init__(self, filename, size, module):
        self._filename = filename
        self._size = size
        self._seen = 0
        self._lock = threading.Lock()
        self._module = module
        self._last_report = -10 # Force immediate 0% report

    def __call__(self, bytes_amount):
        with self._lock:
            self._seen += bytes_amount
            percent = (self._seen / self._size) * 100
            if percent - self._last_report >= 10 or percent >= 100:
                logger.info(self._module, f"Transfer: {percent:.1f}% ({self._seen}/{self._size} bytes)")
                self._last_report = percent

# --- 3. CORE LOGIC FUNCTIONS ---

def get_input_file(input_url):
    module = "DOWNLOAD"
    parsed = urlparse(input_url)
    base_name = os.path.basename(parsed.path) or "input_file"
    local_path = os.path.join("/tmp", base_name)
    
    if input_url.startswith("s3://"):
        s3 = boto3.resource('s3')
        bucket, key = parsed.netloc, parsed.path.lstrip('/')
        obj = s3.Object(bucket, key)
        size = obj.content_length
        
        logger.info(module, f"S3 Source Detected: {size} bytes")
        progress = S3Progress(base_name, size, module)
        config = TransferConfig(multipart_threshold=1024*50, max_concurrency=10)
        obj.download_file(local_path, Config=config, Callback=progress)
    else:
        # Curl -v handles headers, -# handles progress bar in raw output
        run_command_streaming(["curl", "-f", "-L", "-v", "-#", input_url, "-o", local_path], module)
        
    return local_path, base_name

def run_ffmpeg_task(task_args):
    """Note: These run in parallel. Streaming output will be interleaved in logs."""
    output_path, seek_time, input_path = task_args
    module = "FFMPEG-THUMB"
    cmd = ["ffmpeg", "-loglevel", "info", "-accurate_seek", "-ss", f"{seek_time:.6f}", 
           "-i", input_path, "-vf", f"scale={W}:{H}", "-frames:v", "1", "-q:v", "2", output_path]
    
    # We use run_command_streaming here so you see individual frame extraction logs
    try:
        run_command_streaming(cmd, module)
        return output_path
    except:
        return None

def extract_stills_multithreaded(input_path, output_dir, num, den, interval):
    module = "STILLS-ORCH"
    logger.info(module, "Querying video metadata...")
    
    # Capture ffprobe output to get duration
    res = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                          "-of", "default=noprint_wrappers=1:nokey=1", input_path], 
                         capture_output=True, text=True)
    duration = float(res.stdout.strip() or 0)
    total_stills = int((duration * num / den) / interval)
    
    logger.info(module, f"Preparing to extract {total_stills} frames via {MAX_WORKERS} workers")

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
    rows = int(math.ceil(math.sqrt(count)))
    cols = int(math.ceil(count / rows))
    
    row_tasks = []
    for i in range(rows):
        temp_row = f"/tmp/row_{i}_{uuid.uuid4()}.jpg"
        batch = paths[i*cols : (i+1)*cols]
        if batch: row_tasks.append((batch, temp_row))

    def stitch_row(args):
        batch, out = args
        # Streaming the row creation
        run_command_streaming(["convert"] + batch + ["+append", out], "IM-ROW")
        return out

    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="Stitch") as executor:
        row_paths = list(executor.map(stitch_row, row_tasks))
    
    logger.info(module, "Final Assembly: Combining rows into vertical sprite sheet")
    run_command_streaming(["convert"] + row_paths + ["-append", "-quality", "80", "-interlace", "Plane", output_spritemap], module)
    
    for p in row_paths + paths: 
        if os.path.exists(p): os.remove(p)

# --- 4. MAIN PROCESSOR ---

def process_media(event, context=None):
    params = get_parameters(event)
    s3_client = boto3.client('s3')
    
    input_url = params.get('input_url')
    bucket = params.get('output_bucket')
    output_key = params.get('output_key')
    mode = params.get('mode')

    logger.info("MAIN", f"=== STARTING JOB: {output_key} ===")
    
    try:
        local_input, base_name = get_input_file(input_url)
        
        if mode == 'metadata':
            logger.info("METADATA", "Generating Metadata Report")
            # Using the streaming runner for mediainfo/exiftool
            report = {"file_name": base_name}
            run_command_streaming(["mediainfo", "--Output=JSON", local_input], "MEDIAINFO")
            # (Actual report assembly logic goes here)

        elif mode == 'waveform':
            ext = os.path.splitext(local_input)[1].lower()
            local_dat = f"/tmp/{base_name}.dat"
            zoom, bits = params['zoom'], params['bits']
            
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
            
            with open(local_manifest, 'w') as f:
                json.dump({"width": W, "height": H, "count": len(stills)}, f)
            
            logger.info("UPLOAD", "Uploading final artifacts")
            s3_client.upload_file(local_sprite, bucket, f"{output_key}.jpg")
            s3_client.upload_file(local_manifest, bucket, f"{output_key}.json")

        logger.info("MAIN", "=== JOB SUCCESS ===")
        
    except Exception as e:
        logger.error("MAIN", f"JOB FAILED: {str(e)}")
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
