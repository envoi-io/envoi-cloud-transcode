#!/usr/bin/env python3
import os
import subprocess
import json
import glob
import boto3
import math
import uuid

# Global dimensions
W = 240
H = 135 

# --- 1. CORE PIECE-BY-PIECE LOGIC ---

def extract_stills(input_path, output_path, fps_numerator, fps_denominator, frame_interval):
    paths = []
    for i in range(1, 1000000):
        # We keep individual stills as PNG for lossless stitching, but the final map is JPG
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

# (Metadata report function remains unchanged)

# --- 2. UNIFIED MEDIA WORKER LOGIC ---

def get_parameters(event):
    is_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
    params = event if event else {}

    if not is_lambda:
        env_mapping = {
            'input_url': os.environ.get('input_url'),
            'output_bucket': os.environ.get('output_bucket'),
            'output_key': os.environ.get('output_key', 'output/media'),
            'mode': os.environ.get('mode', 'sprite'),
            'zoom': os.environ.get('zoom', '128'),
            'bits': os.environ.get('bits', '8'),
            'fps_num': os.environ.get('fps_num', '24000'),
            'fps_den': os.environ.get('fps_den', '1001'),
            # Default increased to 300 to reduce thumbnail count
            'frame_interval': os.environ.get('frame_interval', '300') 
        }
        for k, v in env_mapping.items():
            if k not in params or params[k] is None:
                if k in ['zoom', 'bits', 'fps_num', 'fps_den', 'frame_interval'] and v is not None:
                    params[k] = int(v)
                else:
                    params[k] = v
    return params

def process_media(event, context=None):
    params = get_parameters(event)
    
    if not params.get('input_url') or not params.get('output_bucket'):
        return {'statusCode': 400, 'body': "Missing input_url or output_bucket"}

    s3 = boto3.client('s3')
    input_url = params.get('input_url')
    bucket = params.get('output_bucket')
    output_key = params.get('output_key', 'output/media')
    mode = params.get('mode', 'sprite')
    
    local_input = "/tmp/video_input.mp4"
    local_sprite = "/tmp/output_sprite.jpg" # Changed to JPG
    local_manifest = "/tmp/output_manifest.json"
    
    # Cleanup logic remains same...
    
    try:
        subprocess.run(["curl", "-L", input_url, "-o", local_input], check=True)

        if mode == 'sprite':
            num = params.get('fps_num', 24000)
            den = params.get('fps_den', 1001)
            interval = params.get('frame_interval', 300) 
            
            stills = extract_stills(local_input, "/tmp/", num, den, interval)
            build_sprite_map(stills, local_sprite)
            
            manifest_data = build_manifest(stills, num, den, interval)
            with open(local_manifest, 'w') as f:
                json.dump(manifest_data, f)

            # Uploading as JPG
            s3.upload_file(local_sprite, bucket, f"{output_key}.jpg")
            s3.upload_file(local_manifest, bucket, f"{output_key}.json")
            
        # (Other modes remain unchanged)
        
        return {'statusCode': 200, 'body': f"Success: {output_key}"}

    except Exception as e:
        return {'statusCode': 500, 'body': str(e)}

def handler(event, context):
    return process_media(event, context)

if __name__ == "__main__":
    handler({}, None)
