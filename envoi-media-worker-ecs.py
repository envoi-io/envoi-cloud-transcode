#!/usr/bin/env python3
import os
import subprocess
import json
import argparse
import glob
import boto3
import sys
import math
import uuid
from itertools import count

# Global dimensions used by your specific extraction logic
W = 240
H = 135 

# --- 1. CORE PIECE-BY-PIECE LOGIC ---

def extract_stills(input_path, output_path, fps_numerator, fps_denominator, frame_interval):
    paths = []
    for i in range(1, 1000000):
        output = os.path.join(output_path, "still%d.png" % i)
        if os.path.exists(output):
            os.remove(output)
            
        seek_time = (fps_denominator * frame_interval * (i - 0.5)) / fps_numerator + 0.000000999
        cmd = [
            "ffmpeg", "-loglevel", "error", "-accurate_seek",
            "-ss", "{:.9f}".format(seek_time), 
            "-i", input_path,
            "-vf", "scale=%d:%d" % (W, H), 
            "-frames:v", "1", 
            "-update", "1", 
            output
        ]
        subprocess.run(cmd)
        if not os.path.isfile(output):
            break
        paths.append(output)
    return paths

def get_rows_and_columns(paths):
    if not paths: return 0, 0
    rows = int(math.ceil(math.sqrt(len(paths))))
    columns = int(math.ceil(len(paths) / rows))
    return rows, columns

def build_sprite_map(paths, output_spritemap):
    """Stitches images into grid and outputs a compressed JPG."""
    rows, columns = get_rows_and_columns(paths)
    row_paths = []
    binary = "convert" 
    
    for i in range(rows):
        temp_row = "/tmp/row_%s_%s.png" % (i, uuid.uuid4())
        start = i * columns
        end = start + columns
        current_batch = paths[start:end]
        if not current_batch:
            continue
        subprocess.run([binary] + current_batch + ["+append", temp_row])
        row_paths.append(temp_row)
    
    if row_paths:
        # Optimization: -quality 80 for high efficiency, -interlace Plane for progressive loading
        cmd = [binary] + row_paths + [
            "-append", 
            "-quality", "80", 
            "-interlace", "Plane", 
            "-sampling-factor", "4:2:0", 
            output_spritemap
        ]
        subprocess.run(cmd)
        
    for path in row_paths:
        if os.path.exists(path):
            os.remove(path)

def build_manifest(paths, fps_numerator, fps_denominator, frame_interval):
    sprites = []
    rows, columns = get_rows_and_columns(paths)
    for i in range(0, len(paths)):
        x = W * (i % columns)
        y = H * int(i / columns)
        frame = frame_interval * (i + 0.5)
        flicks = round((705600000.0 * frame * fps_denominator) / fps_numerator)
        sprites.append({"x": x, "y": y, "t": flicks})
    return {"width": W, "height": H, "sprites": sprites}

def get_complete_metadata_report(file_path):
    if not os.path.exists(file_path):
        return {"error": "File not found"}
    report = {"file_name": os.path.basename(file_path), "exiftool": {}, "ffprobe": {}, "mediainfo": {}}
    try:
        exif_res = subprocess.run(['exiftool', '-j', file_path], capture_output=True, text=True)
        report['exiftool'] = json.loads(exif_res.stdout)[0]
    except: pass
    try:
        ff_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', file_path]
        ff_res = subprocess.run(ff_cmd, capture_output=True, text=True)
        report['ffprobe'] = json.loads(ff_res.stdout)
    except: pass
    try:
        mi_res = subprocess.run(['mediainfo', '--Output=JSON', file_path], capture_output=True, text=True)
        report['mediainfo'] = json.loads(mi_res.stdout)
    except: pass
    return report

# --- 2. UNIFIED MEDIA WORKER LOGIC ---

def get_parameters(event):
    """
    Detects platform (Lambda vs ECS) and merges event data with Env Vars.
    """
    is_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
    params = event if event else {}

    if not is_lambda:
        print("Context: ECS/Container detected. Mapping Environment Variables...")
        # Map environment variables directly
        env_mapping = {
            'input_url': os.environ.get('input_url'),
            'output_bucket': os.environ.get('output_bucket'),
            'output_key': os.environ.get('output_key', 'output/media'),
            'mode': os.environ.get('mode', 'sprite'),
            'zoom': os.environ.get('zoom', '128'),
            'bits': os.environ.get('bits', '8'),
            'fps_num': os.environ.get('fps_num', '24000'),
            'fps_den': os.environ.get('fps_den', '1001'),
            'frame_interval': os.environ.get('frame_interval', '120')
        }
        for k, v in env_mapping.items():
            if k not in params or params[k] is None:
                # Convert numeric strings to actual integers
                if k in ['zoom', 'bits', 'fps_num', 'fps_den', 'frame_interval'] and v is not None:
                    params[k] = int(v)
                else:
                    params[k] = v
                
    return params

def process_media(event, context=None):
    params = get_parameters(event)
    
    # Validation
    if not params.get('input_url') or not params.get('output_bucket'):
        print("MISSING REQUIRED PARAMETERS: input_url or output_bucket")
        return {'statusCode': 400, 'body': "Missing input_url or output_bucket"}

    s3 = boto3.client('s3')
    input_url = params.get('input_url')
    bucket = params.get('output_bucket')
    output_key = params.get('output_key', 'output/media')
    mode = params.get('mode', 'sprite')
    
    local_input = "/tmp/video_input.mp4"
    local_sprite = "/tmp/output_sprite.png"
    local_manifest = "/tmp/output_manifest.json"
    local_dat = "/tmp/output.dat"
    local_meta = "/tmp/metadata.json"
    
    # Cleanup old artifacts
    all_tmp = glob.glob("/tmp/still*.png") + glob.glob("/tmp/row_*.png") + \
              [local_input, local_sprite, local_manifest, local_dat, local_meta]
    for f in all_tmp:
        if os.path.exists(f): 
            try: os.remove(f)
            except: pass

    try:
        print(f"Downloading source: {input_url}")
        subprocess.run(["curl", "-L", input_url, "-o", local_input], check=True)

        if mode == 'metadata':
            print("--- Generating Complete Metadata Report ---")
            metadata_report = get_complete_metadata_report(local_input)
            with open(local_meta, 'w') as f:
                json.dump(metadata_report, f, indent=4)
            s3_key = f"{output_key}.json" if not output_key.endswith(".json") else output_key
            s3.upload_file(local_meta, bucket, s3_key)

        elif mode == 'waveform':
            print("--- Generating Waveform ---")
            zoom = params.get('zoom', 128)
            bits = params.get('bits', 8)
            waveform_cmd = (
                f"ffmpeg -i {local_input} -map a:0 -f wav - | "
                f"audiowaveform --input-format wav --output-format dat "
                f"--zoom {zoom} --bits {bits} --split-channels -o {local_dat}"
            )
            subprocess.run(waveform_cmd, shell=True, check=True)
            s3_key = f"{output_key}.dat" if not output_key.endswith(".dat") else output_key
            s3.upload_file(local_dat, bucket, s3_key)
            
        else:
            print("--- Generating Detailed Sprite & Manifest ---")
            num = params.get('fps_num', 24000)
            den = params.get('fps_den', 1001)
            interval = params.get('frame_interval', 360)
            stills = extract_stills(local_input, "/tmp/", num, den, interval)
            build_sprite_map(stills, local_sprite)
            manifest_data = build_manifest(stills, num, den, interval)
            with open(local_manifest, 'w') as f:
                json.dump(manifest_data, f)
            s3.upload_file(local_sprite, bucket, f"{output_key}.jpg")
            s3.upload_file(local_manifest, bucket, f"{output_key}.json")

        print(f"COMPLETED SUCCESSFULLY: {output_key}")
        return {'statusCode': 200, 'body': f"Success: {output_key}"}

    except Exception as e:
        print(f"FATAL ERROR: {str(e)}")
        return {'statusCode': 500, 'body': str(e)}

def handler(event, context):
    return process_media(event, context)

if __name__ == "__main__":
    # In ECS, this block runs immediately because of the python3 worker.py ENTRYPOINT.
    # We pass empty event/context; get_parameters will pull from ENV instead.
    print("Worker started via ENTRYPOINT.")
    handler({}, None)
