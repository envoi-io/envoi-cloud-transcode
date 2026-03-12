#!/usr/bin/env python3

# Global configuration: W is the target width for each thumbnail.
# H is set to -1 so FFmpeg maintains the original aspect ratio automatically.
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
    """
    Extracts individual frames from the source video at a specific cadence.
    
    Logic:
    Instead of 'piping' frames (which can be memory intensive), we seek to 
    specific timestamps and save them as individual PNGs for later stitching.
    """
    for i in range(1, 1000000):
        output = os.path.join(output_path, "still%d.png" % i)
        if os.path.exists(output):
            os.remove(output)
            
        # TIMESTAMP CALCULATION:
        # We target the middle of the interval (i - 0.5) to get a 'representative' frame.
        # Logic: (Denominator * Interval * FrameIndex) / Numerator
        seek_time = (fps_denominator * frame_interval * (i - 0.5)) / fps_numerator + 0.000000999
        
        # FFMPEG COMMAND:
        # -loglevel error: Suppresses 'No filtered frames' warnings at video EOF.
        # -ss: Placed BEFORE -i for 'fast seeking' (jumping to keyframes near the target).
        # -vf scale: Resizes the frame to our global W (240px).
        # -update 1: Explicitly tells FFmpeg we are writing a single image file.
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
        
        # If no file was created, FFmpeg likely couldn't find a frame at that timestamp
        # (meaning we've reached the end of the video).
        if not os.path.isfile(output):
            break

def collect_images(base_path):
    """Gathers all 'stillN.png' files in order to prepare for the grid assembly."""
    paths = []
    for i in count(1):
        f = os.path.join(base_path, "still%d.png" % i)
        if not os.path.isfile(f):
            break
        paths.append(f)
    return paths

def get_rows_and_columns(paths):
    """
    Calculates the most 'square' grid possible for the number of frames we have.
    Example: 10 frames = 4 rows, 3 columns (total grid size 12).
    """
    rows = int(math.ceil(math.sqrt(len(paths))))
    columns = int(math.ceil(len(paths) / rows))
    return rows, columns

def build_sprite_map(paths, output_spritemap):
    """
    Stitches individual images into a single spritemap.
    
    STRATEGY:
    We avoid the 'montage' tool because it often requires system fonts for 
    labeling. Instead, we use 'magick +append' (horizontal join) to create rows, 
    and 'magick -append' (vertical join) to stack those rows into the final grid.
    """
    rows, columns = get_rows_and_columns(paths)
    row_paths = []
    
    # STEP 1: Create horizontal rows
    for i in range(rows):
        temp_row = "row_%s_%s.png" % (i, uuid.uuid4())
        start = i * columns
        end = start + columns
        current_batch = paths[start:end]
        
        if not current_batch:
            continue
            
        # '+append' glues images together left-to-right
        subprocess.run(["magick"] + current_batch + ["+append", temp_row])
        row_paths.append(temp_row)
    
    # STEP 2: Stack the rows into the final image
    # '-append' glues images together top-to-bottom
    if row_paths:
        subprocess.run(["magick"] + row_paths + ["-append", output_spritemap])
    
    # STEP 3: Cleanup temporary artifacts
    for path in paths + row_paths:
        if os.path.exists(path):
            os.remove(path)

def get_height(paths):
    """Uses ImageMagick's identify tool to get the pixel height of the resized frames."""
    r = subprocess.check_output(['magick', 'identify', '-format', '%h', paths[0]])
    return int(r)

def build_manifest(paths, fps_numerator, fps_denominator, frame_interval):
    """
    Creates a JSON object that maps every thumbnail to its coordinates and time.
    
    The time 't' is calculated in 'Flicks' (1/705,600,000 of a second).
    This unit is used by media tools to avoid floating-point errors.
    """
    sprites = []
    rows, columns = get_rows_and_columns(paths)
    for i in range(0, len(paths)):
        x = W * (i % columns)      # Horizontal pixel offset
        y = H * int(i / columns)   # Vertical pixel offset
        
        # TIME CALCULATION (in Flicks):
        # Formula: $Flicks = \text{round}\left(\frac{705,600,000 \times \text{frame} \times \text{denominator}}{\text{numerator}}\right)$
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

if __name__ == "__main__":
    # Setup CLI flags
    parser = argparse.ArgumentParser(description="Generate video scrubbing sprites.")
    parser.add_argument('input', metavar='VIDEO_FILE', nargs=1, help='Source video')
    parser.add_argument('-n', dest='fps_numerator', type=int, required=True, help='FPS Numerator (e.g. 24)')
    parser.add_argument('-d', dest='fps_denominator', type=int, required=True, help='FPS Denominator (e.g. 1)')
    parser.add_argument('-W', dest='image_width', type=int, required=True, help='Pixel width of each sprite')
    parser.add_argument('-i', dest='interval', type=float, required=True, help='Frame interval')
    parser.add_argument('-om', dest='output_manifest', default="manifest.json", type=str)
    parser.add_argument('-os', dest='output_spritemap', default="spritemap.jpg", type=str)
    
    args = parser.parse_args()
    
    # Setup global width and ensure the frame interval is an even number (helps with media alignment)
    W = args.image_width
    interval = max(2 * math.ceil(args.interval / 2), 2)
    
    # WORKFLOW EXECUTION:
    print("--- 1. Extracting frames via FFmpeg...")
    extract_stills(args.input[0], "./", args.fps_numerator, args.fps_denominator, interval)
    
    paths = collect_images("./")
    if not paths:
        print("Error: Extraction failed. Verify video file path and FPS settings.")
        sys.exit(1)
        
    H = get_height(paths) # Update H with the actual height after aspect-ratio scaling
    
    print(f"--- 2. Stitching {len(paths)} frames into spritemap...")
    build_sprite_map(paths, args.output_spritemap)
    
    print("--- 3. Generating JSON manifest...")
    sprites = build_manifest(paths, args.fps_numerator, args.fps_denominator, interval)
    
    # Save the JSON with an indent for easier reading
    with open(args.output_manifest, "w") as f:
        json.dump(sprites, f, indent=2)
    
    print(f"\nSuccess! Generated:\n- {args.output_spritemap}\n- {args.output_manifest}")
