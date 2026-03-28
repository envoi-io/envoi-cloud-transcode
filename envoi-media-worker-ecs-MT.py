#!/usr/bin/env python3
import warnings
# Silence Boto3 Python 3.7 deprecation warnings
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

    output_captured = []
    for line in iter(process.stdout.readline, ""):
        clean_line = line.strip()
        if clean_line:
            logger.info(f"{module_name}-RAW", clean_line)
            output_captured.append(clean_line)

    process.stdout.close()
    return_code = process.wait()
    duration = time.time() - start_time

    if return_code != 0:
        logger.error(module_name, f"CRITICAL FAILURE: Exit Code {return_code}")
        raise subprocess.CalledProcessError(return_code, cmd)
    
    logger.info(module_name, f"EXEC END | Duration: {duration:.2f}s")
    return "\n".join(output_captured)

# --- 2. S3 PROGRESS TRACKING ---

class S3Progress(object):
    def __init__(self, filename, size, module, context_id):
        self._filename = filename
        self._size = size
        self._seen = 0
        self._lock = threading.Lock()
        self._module = module
        self._context_id = context_id
        self._last_report_time = time.time()
        self._last_report_bytes = 0

    def __call__(self, bytes_amount):
        with self._lock:
            self._seen += bytes_amount
            now = time.time()
            delta_time = now - self._last_report_time
            
            if delta_time >= 2.0 or self._seen == self._size:
                percent = (self._seen / self._size) * 100
                speed = ((self._seen - self._last_report_bytes) / delta_time) / (1024 * 1024) if delta_time > 0 else 0
                logger.info(self._module, f"[{self._context_id}] Transfer: {percent:.1f}% | {speed:.2f} MB/s")
                self._last_report_time, self._last_report_bytes = now, self._seen

# --- 3. CORE FUNCTIONS ---

def get_input_file(input_url, output_key):
    module = "DOWNLOAD"
    parsed = urlparse(input_url)
    base_name = os.path.basename(parsed.path) or f"input_{uuid.uuid4().hex[:8]}"
    local_path = os.path.join("/tmp", base_name)
    
    logger.info(module, f"[{output_key}] Input: {input_url} -> Local: {local_path}")
    
    if input_url.startswith("s3://"):
        s3 = boto3.resource('s3')
        bucket_name, key = parsed.netloc, parsed.path.lstrip('/')
        obj = s3.Object(bucket_name, key)
        size = obj.content_length
        progress = S3Progress(base_name, size, module, output_key)
        config = TransferConfig(multipart_threshold=1024*25, max_concurrency=10, use_threads=True)
        obj.download_file(local_path, Config=config, Callback=progress)
    else:
        run_command_streaming(["curl", "-f", "-L", "-v", "-#", input_url, "-o", local_path], module)
        
    return local_path, base_name

def get_complete_metadata_report(file_path, output_key):
    module = "METADATA-GEN"
    logger.info(module, f"[{output_key}] Running comprehensive metadata scan on {file_path}")
    
    report = {"file_name": os.path.basename(file_path), "exiftool": {}, "ffprobe": {}, "mediainfo": {}}

    # 1. ExifTool
    try:
        raw = run_command_streaming(['exiftool', '-j', file_path], "EXIFTOOL")
        report['exiftool'] = json.loads(raw)[0]
    except Exception as e: report['exiftool'] = {"error": str(e)}

    # 2. FFprobe
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', file_path]
        raw = run_command_streaming(cmd, "FFPROBE")
        report['ffprobe'] = json.loads(raw)
    except Exception as e: report['ffprobe'] = {"error": str(e)}

    # 3. MediaInfo
    try:
        raw = run_command_streaming(['mediainfo', '--Output=JSON', file_path], "MEDIAINFO")
        report['mediainfo'] = json.loads(raw)
    except Exception as e: report['mediainfo'] = {"error": str(e)}

    return report

def run_ffmpeg_task(task_args):
    output_path, seek_time, input_path = task_args
    # loglevel info provides the "Full Output" requested
    cmd = ["ffmpeg", "-loglevel", "info", "-accurate_seek", "-ss", f"{seek_time:.6f}", 
           "-i", input_path, "-vf", f"scale={W}:{H}", "-frames:v", "1", "-q:v", "2", output_path]
    try:
        run_command_streaming(cmd, "FFMPEG-THUMB")
        return output_path
    except: return None

def extract_stills_multithreaded(input_path, output_dir, num, den, interval, output_key):
    module = "STILLS-ORCH"
    logger.info(module, f"[{output_key}] Probing duration for extraction...")
    res = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_path], capture_output=True, text=True)
    duration = float(res.stdout.strip() or 0)
    total_stills = int((duration * num / den) / interval)
    
    logger.info(module, f"[{output_key}] Queuing {total_stills} extraction tasks to ThreadPool.")
    tasks = [(os.path.join(output_dir, f"still_{i}.jpg"), (den * interval * (i - 0.5)) / num, input_path) for i in range(1, total_stills + 1)]
    
    paths = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="Extract") as executor:
        futures = {executor.submit(run_ffmpeg_task, t): t for t in tasks}
        logger.info(module, f"[{output_key}] All {len(futures)} threads submitted.")
        for f in as_completed(futures):
            res = f.result()
            if res: paths.append(res)
    return sorted(paths)

def build_sprite_map_multithreaded(paths, output_spritemap, output_key):
    module = "IMAGEMAGICK"
    count = len(paths)
    rows = int(math.ceil(math.sqrt(count)))
    cols = int(math.ceil(count / rows))
    
    logger.info(module, f"[{output_key}] Starting Sprite Generation ({count} images into {cols}x{rows} grid)")
    row_tasks = []
    for i in range(rows):
        temp_row = f"/tmp/row_{i}_{uuid.uuid4().hex}.jpg"
        batch = paths[i*cols : (i+1)*cols]
        if batch: row_tasks.append((batch, temp_row))

    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="Stitch") as executor:
        row_paths = list(executor.map(lambda args: run_command_streaming(["convert"] + args[0] + ["+append", args[1]], "IM-ROW"), row_tasks))
        # Logic fix: executor.map returns results, but we need the paths
        row_paths = [t[1] for t in row_tasks]

    run_command_streaming(["convert"] + row_paths + ["-append", "-quality", "80", "-interlace", "Plane", output_spritemap], module)
    for p in row_paths + paths: 
        if os.path.exists(p): os.remove(p)

def build_manifest(paths, num, den, interval, output_key):
    module = "MANIFEST"
    count = len(paths)
    rows = int(math.ceil(math.sqrt(count)))
    cols = int(math.ceil(count / rows))
    logger.info(module, f"[{output_key}] Generating manifest for {count} sprites ({cols} cols, {rows} rows)")
    
    sprites = []
    for i in range(count):
        sprites.append({
            "x": W * (i % cols), "y": H * int(i / cols),
            "t": round((705600000.0 * interval * (i + 0.5) * den) / num)
        })
    return {"width": W, "height": H, "sprites": sprites}

# --- 4. RUNTIME ---

def process_media(event, context=None):
    from __main__ import get_parameters
    params = get_parameters(event)
    s3_client = boto3.client('s3')
    
    input_url, bucket, output_key, mode = params.get('input_url'), params.get('output_bucket'), params.get('output_key'), params.get('mode')

    logger.info("MAIN", f"[{output_key}] Starting process_media. Mode: {mode}")
    
    try:
        local_input, base_name = get_input_file(input_url, output_key)
        
        if mode == 'metadata':
            report = get_complete_metadata_report(local_input, output_key)
            local_meta = f"/tmp/{base_name}_meta.json"
            with open(local_meta, 'w') as f: json.dump(report, f, indent=4)
            logger.info("UPLOAD", f"[{output_key}] Uploading metadata report.")
            s3_client.upload_file(local_meta, bucket, f"{output_key}.json")

        elif mode == 'waveform':
            ext, local_dat = os.path.splitext(local_input)[1].lower(), f"/tmp/{base_name}.dat"
            zoom, bits = params.get('zoom', 128), params.get('bits', 8)
            logger.info("WAVEFORM", f"[{output_key}] Triggering audiowaveform for {ext}")
            cmd = f"audiowaveform -i {local_input} --output-format dat --zoom {zoom} --bits {bits} -o {local_dat}" if ext in ['.mp3', '.wav', '.aiff', '.aif'] else f"ffmpeg -i {local_input} -map a:0 -f wav - | audiowaveform --input-format wav --output-format dat --zoom {zoom} --bits {bits} --split-channels -o {local_dat}"
            run_command_streaming(cmd, "WAVEFORM", shell=True)
            s3_client.upload_file(local_dat, bucket, f"{output_key}.dat")

        else: # Sprite mode
            num, den, interval = params['fps_num'], params['fps_den'], params['frame_interval']
            local_sprite, local_manifest = f"/tmp/{base_name}_sprite.jpg", f"/tmp/{base_name}_manifest.json"
            
            stills = extract_stills_multithreaded(local_input, "/tmp", num, den, interval, output_key)
            build_sprite_map_multithreaded(stills, local_sprite, output_key)
            
            manifest_json = build_manifest(stills, num, den, interval, output_key)
            with open(local_manifest, 'w') as f: json.dump(manifest_json, f)
            
            logger.info("UPLOAD", f"[{output_key}] Finalizing S3 uploads for Sprite/Manifest.")
            s3_client.upload_file(local_sprite, bucket, f"{output_key}.jpg")
            s3_client.upload_file(local_manifest, bucket, f"{output_key}.json")

        logger.info("MAIN", f"[{output_key}] JOB COMPLETED SUCCESSFULLY.")
        
    except Exception as e:
        logger.error("MAIN", f"[{output_key}] FATAL ERROR: {str(e)}")
        sys.exit(1)
    finally:
        if 'local_input' in locals() and os.path.exists(local_input):
            os.remove(local_input)

def get_parameters(event):
    params = event if event else {}
    env_mapping = {'input_url': os.environ.get('input_url'), 'output_bucket': os.environ.get('output_bucket'), 'output_key': os.environ.get('output_key', 'output/media'), 'mode': os.environ.get('mode', 'sprite'), 'zoom': os.environ.get('zoom', '128'), 'bits': os.environ.get('bits', '8'), 'fps_num': os.environ.get('fps_num', '24000'), 'fps_den': os.environ.get('fps_den', '1001'), 'frame_interval': os.environ.get('frame_interval', '300')}
    for k, v in env_mapping.items():
        if k not in params or params[k] is None:
            params[k] = int(v) if k in ['zoom', 'bits', 'fps_num', 'fps_den', 'frame_interval'] and v else v
    return params

if __name__ == "__main__":
    process_media({}, None)
