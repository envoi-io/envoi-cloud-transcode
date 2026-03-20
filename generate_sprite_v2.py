#!/usr/bin/env python3

import argparse
import json
import math
import os
import subprocess
import sys
import uuid
from itertools import count

# Global configuration defaults
W = 240 # Default thumbnail width
H = -1  # Placeholder for height, calculated via ffprobe after extraction

def get_height(path):
    """
    Uses ffprobe to extract the pixel height of a generated frame.
    This is much more reliable than ImageMagick on headless Linux servers.
    """
    cmd = [
        'ffprobe', '-v', 'error', 
        '-select_streams', 'v:0', 
        '-show_entries', 'stream=height', 
        '-of', 'csv=s=x:p=0', 
        path
    ]
    try:
        result = subprocess.check_output(cmd).decode("utf-8").strip()
        return int(result)
    except Exception as e:
        print(f"CRITICAL: Could not determine height of {path}. ffprobe error: {e}")
        sys.exit(1)

def extract_stills(input_path, output_path, fps_numerator, fps_denominator, frame_interval):
    """
    Tells FFmpeg to jump to specific timestamps and 'snapshot' a frame.
    
    Fixes included:
    - '-update 1': Prevents 'image sequence pattern' errors.
    - '-loglevel error': Silences the 'No filtered frames' noise.
    """
    print(f"--- 1. Starting frame extraction from: {input_path}")
    
    for i in range(1, 1000000):
        output = os.path.join(output_path, "still%d.png" % i)
        
        # Clean up any leftover files from previous failed runs
        if os.path.exists(output):
            os.remove(output)
            
        # SEEK LOGIC:
        # We target the center of the interval for the best visual representation.
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
        
        # If no file is produced, we've reached the end of the video timeline.
        if not os.path.isfile(output):
            if i == 1:
                print("ERROR: FFmpeg failed to extract the very first frame. Check your FPS/Interval.")
                sys.exit(1)
            break
    
    print(f"--- Successfully extracted {i-1} frames.")

def build_sprite_map(paths, output_spritemap):
    """
    Stitches frames into a grid using ImageMagick 'magick' commands.
    
    Using '+append' (horizontal) and '-append' (vertical) avoids the 
    font-dependency errors common with the 'montage' command.
    """
    rows, columns = get_rows_and_columns(paths)
    row_paths = []
    
    print(f"--- 2. Stitching into {rows}x{columns} grid...")
    
    try:
        # Step A: Create horizontal rows
        for i in range(rows):
            temp_row = "row_%s_%s.png" % (i, uuid.uuid4())
            start = i * columns
            end = start + columns
            current_batch = paths[start:end]
            
            if not current_batch:
                continue
                
            subprocess.run(["magick"] + current_batch + ["+append", temp_row], check=True)
            row_paths.append(temp_row)
        
        # Step B: Stack the rows vertically into the final JPG
        if row_paths:
            subprocess.run(["magick"] + row_paths + ["-append", output_spritemap], check=True)
            
    except subprocess.CalledProcessError as e:
        print(f"CRITICAL: ImageMagick failed. Ensure 'magick' is installed. Error: {e}")
        sys.exit(1)
    finally:
        # Cleanup temporary files
        for path in paths + row_paths:
            if os.path.exists(path):
                os.remove(path)

def get_rows_and_columns(paths):
    """Calculates a balanced grid layout."""
    rows = int(math.ceil(math.sqrt(len(paths))))
    columns = int(math.ceil(len(paths) / rows))
    return rows, columns

def build_manifest(paths, fps_numerator, fps_denominator, frame_interval):
    """
    Generates the JSON data mapping.
    Time 't' is in 'Flicks' (1/705,600,000 sec) for high-precision media sync.
    """
    sprites = []
    rows, columns = get_rows_and_columns(paths)
    for i in range(0, len(paths)):
        x = W * (i % columns)
        y = H * int(i / columns)
        
        # Calculate time in Flicks
        frame = frame_interval * (i + 0.5)
        flicks = round((705600000.0 * frame * fps_denominator) / fps_numerator)
        
        sprites.append({"x": x, "y": y, "t": flicks})
        
    return {"width": W, "height": H, "sprites": sprites}

def collect_images(base_path):
    """Helper to find all generated stills."""
    imgs = []
    for i in count(1):
        f = os.path.join(base_path, "still%d.png" % i)
        if not os.path.isfile(f):
            break
        imgs.append(f)
    return imgs

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Professional Video Spritemap Generator")
    parser.add_argument('input', metavar='VIDEO_FILE', nargs=1)
    parser.add_argument('-n', dest='fps_numerator', type=int, required=True, help='FPS Numerator')
    parser.add_argument('-d', dest='fps_denominator', type=int, required=True, help='FPS Denominator')
    parser.add_argument('-W', dest='image_width', type=int, required=True, help='Sprite width')
    parser.add_argument('-i', dest='interval', type=float, required=True, help='Frame interval')
    parser.add_argument('-om', dest='output_manifest', default="manifest.json", type=str)
    parser.add_argument('-os', dest='output_spritemap', default="spritemap.jpg", type=str)
    
    args = parser.parse_args()
    W = args.image_width
    
    # Interval must be even to ensure clean seeks in most video codecs
    interval = max(2 * math.ceil(args.interval / 2), 2)
    
    # Process
    extract_stills(args.input[0], "./", args.fps_numerator, args.fps_denominator, interval)
    
    paths = collect_images("./")
    if not paths:
        sys.exit(1)
        
    H = get_height(paths[0])
    build_sprite_map(paths, args.output_spritemap)
    
    print("--- 3. Saving manifest.json...")
    manifest_data = build_manifest(paths, args.fps_numerator, args.fps_denominator, interval)
    with open(args.output_manifest, "w") as f:
        json.dump(manifest_data, f, indent=2)
    
    print(f"\nDONE!\nCreated: {args.output_spritemap}\nCreated: {args.output_manifest}")