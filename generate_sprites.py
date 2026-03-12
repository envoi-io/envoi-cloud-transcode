#!/usr/bin/env python3

W = 240
H = -1

import argparse
import json
import math
import os
import subprocess
import sys
import uuid
from decimal import Decimal, ROUND_HALF_UP
from itertools import count

def extract_stills(input_path, output_path, fps_numerator, fps_denominator, frame_interval):
    """Extracts frames using FFmpeg with cleaner logging."""
    for i in range(1, 1000000):
        output = os.path.join(output_path, "still%d.png" % i)
        if os.path.exists(output):
            os.remove(output)
            
        seek_time = (fps_denominator * frame_interval * (i - 0.5)) / fps_numerator + 0.000000999
        
        # Added '-loglevel error' to stop the 'No filtered frames' noise
        cmd = [
            "ffmpeg", "-loglevel", "error", "-accurate_seek",
            "-ss", "{:.9f}".format(seek_time), 
            "-i", input_path,
            "-vf", "scale=%d:%d" % (W, H), 
            "-frames:v", "1", 
            "-update", "1", 
            output
        ]
        
        ps = subprocess.run(cmd)
        
        # If the file wasn't created, we've likely hit the end of the video
        if not os.path.isfile(output):
            break

def collect_images(base_path):
    paths = []
    for i in count(1):
        f = os.path.join(base_path, "still%d.png" % i)
        if not os.path.isfile(f):
            break
        paths.append(f)
    return paths

def get_rows_and_columns(paths):
    rows = int(math.ceil(math.sqrt(len(paths))))
    columns = int(math.ceil(len(paths) / rows))
    return rows, columns

def build_sprite_map(paths, output_spritemap):
    """
    Stitches images using '+append' and '-append' to avoid 
    ImageMagick's font/label system entirely.
    """
    rows, columns = get_rows_and_columns(paths)
    row_paths = []
    
    # 1. Create horizontal rows
    for i in range(rows):
        temp_row = "row_%s_%s.png" % (i, uuid.uuid4())
        start = i * columns
        end = start + columns
        current_batch = paths[start:end]
        
        if not current_batch:
            continue
            
        # '+append' puts images side-by-side horizontally
        subprocess.run(["magick"] + current_batch + ["+append", temp_row])
        row_paths.append(temp_row)
    
    # 2. Stack the rows vertically
    # '-append' stacks images top-to-bottom
    if row_paths:
        subprocess.run(["magick"] + row_paths + ["-append", output_spritemap])
    
    # 3. Cleanup temporary files
    for path in paths + row_paths:
        if os.path.exists(path):
            os.remove(path)

def get_height(paths):
    r = subprocess.check_output(['magick', 'identify', '-format', '%h', paths[0]])
    return int(r)

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input', metavar='VIDEO_FILE', nargs=1)
    parser.add_argument('-n', dest='fps_numerator', type=int, required=True)
    parser.add_argument('-d', dest='fps_denominator', type=int, required=True)
    parser.add_argument('-W', dest='image_width', type=int, required=True)
    parser.add_argument('-i', dest='interval', type=float, required=True)
    parser.add_argument('-om', dest='output_manifest', default="manifest.json", type=str)
    parser.add_argument('-os', dest='output_spritemap', default="spritemap.jpg", type=str)
    
    args = parser.parse_args()
    W = args.image_width
    interval = max(2 * math.ceil(args.interval / 2), 2)
    
    print("--- Extracting frames...")
    extract_stills(args.input[0], "./", args.fps_numerator, args.fps_denominator, interval)
    
    paths = collect_images("./")
    if not paths:
        print("Error: No frames were extracted. Check your video file or interval.")
        sys.exit(1)
        
    H = get_height(paths)
    
    print(f"--- Building spritemap ({len(paths)} frames)...")
    build_sprite_map(paths, args.output_spritemap)
    
    print("--- Generating manifest...")
    sprites = build_manifest(paths, args.fps_numerator, args.fps_denominator, interval)
    json.dump(sprites, open(args.output_manifest, "w"), indent=2)
    
    print("Done! Files created: %s, %s" % (args.output_spritemap, args.output_manifest))
