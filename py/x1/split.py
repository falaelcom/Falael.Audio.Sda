import os
import subprocess
import glob

def parse_timespan(timespan: str) -> float:
    parts = timespan.strip().split(":")
    if len(parts) == 1:
        seconds = int(parts[0])
    elif len(parts) == 2:
        minutes, seconds = parts
        seconds = int(minutes) * 60 + int(seconds)
    elif len(parts) == 3:
        hours, minutes, seconds = parts
        seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    else:
        raise ValueError(f"Invalid timespan format: {timespan}")
    return float(seconds)

def process(src_file_path: str, out_path: str, config: dict, previous: dict) -> dict:
    duration_str = config.get("split::duration", "30")
    try:
        chunk_length = parse_timespan(duration_str)
    except Exception as e:
        return {"error": f"Invalid duration format: {e}"}
    
    sox_path = config.get("split::sox_path")
    if not sox_path or not os.path.isfile(sox_path):
        return {"error": "Missing or invalid split::sox_path"}
    
    # Get the directory where the source file is located (media directory)
    src_dir = os.path.dirname(src_file_path)
    src_filename = os.path.basename(src_file_path)
    src_ext = os.path.splitext(src_filename)[1].lstrip(".")
    
    # Sox output prefix - chunks will be created in the same directory as source
    out_prefix = os.path.join(src_dir, src_filename + "." + src_ext)
    
    # Delete existing output files before running SoX (same logic as before)
    i = 0
    while True:
        expected_filename = f"{src_filename}.{i:03d}.{src_ext}"
        expected_path = os.path.join(src_dir, expected_filename)
        if os.path.exists(expected_path):
            os.remove(expected_path)
            i += 1
        else:
            break
    
    cmd = [
        sox_path,
        src_file_path,
        out_prefix,
        "trim",
        "0",
        str(chunk_length),
        ":",
        "newfile",
        ":",
        "restart"
    ]
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        return {"error": f"sox failed: {e.stderr.decode(errors='ignore')}"}
    
    # Find all files created by SoX and rename them (same pattern as before)
    sox_pattern = os.path.join(src_dir, f"{src_filename}[0-9][0-9][0-9].{src_ext}")
    sox_files = glob.glob(sox_pattern)
    sox_files.sort()  # Sort by filename
    
    chunk_files = []
    for i, sox_file in enumerate(sox_files):
        # Create new filename with desired format (same as before)
        new_filename = f"{src_filename}.{i:03d}.{src_ext}"
        new_path = os.path.join(src_dir, new_filename)
        
        # Rename the file
        os.rename(sox_file, new_path)
        
        # Add relative path to chunk_files (relative to out_path)
        relative_chunk_path = os.path.relpath(new_path, out_path)
        chunk_files.append(relative_chunk_path)
    
    return {
        "chunks": chunk_files,
        "count": len(chunk_files),
        "duration": chunk_length
    }