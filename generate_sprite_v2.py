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
H = 135 # Standard 16:9 for 240w, adjusted by identify in script

# --- 1. CORE PIECE-BY-PIECE LOGIC ---

def extract_stills(input_path, output_path, fps_numerator, fps_denominator, frame_interval):
    """Extracts individual frames at specific cadence using fast-seeking SS."""
    paths = []
    for i in range(1, 1000000):
        output = os.path.join(output_path, "still%d.png" % i)
        if os.path.exists(output):
            os.remove(output)
            
        # Precise Seek Time calculation
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
    """Calculates squarest grid possible."""
    if not paths: return 0, 0
    rows = int(math.ceil(math.sqrt(len(paths))))
    columns = int(math.ceil(len(paths) / rows))
    return rows, columns

def build_sprite_map(paths, output_spritemap):
    """Stitches images into grid using +append and -append to avoid font issues."""
    rows, columns = get_rows_and_columns(paths)
    row_paths = []
    
    # Use 'magick' or 'convert' depending on environment
    # On AL2/ImageMagick 6, we use 'convert'
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
        subprocess.run([binary] + row_paths + ["-append", output_spritemap])
    
    # Cleanup rows
    for path in row_paths:
        if os.path.exists(path):
            os.remove(path)

def build_manifest(paths, fps_numerator, fps_denominator, frame_interval):
    """Creates JSON manifest with coordinates and time in Flicks."""
    sprites = []
    rows, columns = get_rows_and_columns(paths)
    for i in range(0, len(paths)):
        x = W * (i % columns)
        y = H * int(i / columns)
        
        # Flicks Calculation: (705,600,000 * frame * denom) / num
        frame = frame_interval * (i + 0.5)
        flicks = round((705600000.0 * frame * fps_denominator) / fps_numerator)
        
        sprites.append({
            "x": x,
            "y": y,
            "t": flicks
        })
    
    return {
        "width": W,
        "height": H,
        "sprites": sprites
    }

# --- 2. UNIFIED MEDIA WORKER LOGIC ---

def process_media(event, context=None):
    s3 = boto3.client('s3')
    input_url = event.get('input_url')
    bucket = event.get('output_bucket')
    output_key = event.get('output_key', 'output/media')
    mode = event.get('mode', 'sprite')
    
    # Setup paths in /tmp/
    local_input = "/tmp/video_input.mp4"
    local_sprite = "/tmp/output_sprite.png"
    local_manifest = "/tmp/output_manifest.json"
    
    # Cleanup old artifacts
    for f in glob.glob("/tmp/still*.png") + glob.glob("/tmp/row_*.png") + [local_input, local_sprite, local_manifest]:
        if os.path.exists(f): 
            try: os.remove(f)
            except: pass

    try:
        print(f"Downloading source: {input_url}")
        subprocess.run(["curl", "-L", input_url, "-o", local_input], check=True)

        if mode == 'waveform':
            print("--- Generating Waveform ---")
            local_output_dat = "/tmp/output.dat"
            waveform_cmd = (
                f"ffmpeg -i {local_input} -map a:0 -f wav - | "
                f"audiowaveform --input-format wav --output-format dat "
                f"--zoom {event.get('zoom', 128)} --bits {event.get('bits', 8)} --split-channels > {local_output_dat}"
            )
            subprocess.run(waveform_cmd, shell=True, check=True)
            s3.upload_file(local_output_dat, bucket, f"{output_key}.dat")
            
        else:
            print("--- Generating Detailed Sprite & Manifest ---")
            # Pull frame timing from event or default to common values
            # (Numerator 24000, Denom 1001 for 23.976fps)
            num = event.get('fps_num', 24000)
            den = event.get('fps_den', 1001)
            interval = event.get('frame_interval', 120)

            # 1. Extract
            stills = extract_stills(local_input, "/tmp/", num, den, interval)
            
            # 2. Stitch
            build_sprite_map(stills, local_sprite)
            
            # 3. Manifest
            manifest_data = build_manifest(stills, num, den, interval)
            with open(local_manifest, 'w') as f:
                json.dump(manifest_data, f)

            # 4. Upload
            s3.upload_file(local_sprite, bucket, f"{output_key}.png")
            s3.upload_file(local_manifest, bucket, f"{output_key}.json")

        return {'statusCode': 200, 'body': f"Success: {output_key}"}

    except Exception as e:
        print(f"FATAL ERROR: {str(e)}")
        return {'statusCode': 500, 'body': str(e)}

def handler(event, context):
    return process_media(event, context)

if __name__ == "__main__":
    # Simplified CLI mock for testing
    if len(sys.argv) > 1:
        test_event = {"input_url": sys.argv[1], "mode": "sprite", "output_bucket": None}
        process_media(test_event)
