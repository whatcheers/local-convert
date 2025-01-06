from flask import Flask, render_template, request, send_file, url_for, redirect, Response, stream_with_context
import os
from werkzeug.utils import secure_filename
import subprocess
from pathlib import Path
import time
import json
from queue import Queue
from threading import Thread
import sys
import re

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Ensure upload and output directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/output', exist_ok=True)

# FFmpeg options
FPS_OPTIONS = [5, 10, 15, 20, 25, 30]
SCALE_OPTIONS = [
    ('320:-1', '320p'),
    ('480:-1', '480p'),
    ('640:-1', '640p'),
    ('800:-1', '800p'),
    ('1280:-1', '720p'),
]
FORMAT_OPTIONS = [
    ('gif', 'GIF'),
    ('webm', 'WebM'),
]

# Global queue for FFmpeg output
ffmpeg_output_queue = Queue()
video_duration = None

def get_video_duration(video_path):
    """Get video duration in seconds using ffprobe"""
    cmd = [
        'ffprobe', 
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    try:
        output = subprocess.check_output(cmd).decode().strip()
        return float(output)
    except:
        return None

def process_ffmpeg_output(process):
    """Process FFmpeg output and put it in the queue"""
    global video_duration
    time_pattern = re.compile(r'time=(\d+:\d+:\d+.\d+)')
    
    for line in iter(process.stderr.readline, b''):
        decoded_line = line.decode()
        # Print to terminal
        print(decoded_line, end='', file=sys.stderr)
        sys.stderr.flush()

        # Extract time progress if available
        if video_duration:
            match = time_pattern.search(decoded_line)
            if match:
                time_str = match.group(1)
                h, m, s = map(float, time_str.replace('.', ':').split(':'))
                current_time = h * 3600 + m * 60 + s
                progress = min(100, int((current_time / video_duration) * 100))
                decoded_line = f"Progress: {progress}% - {decoded_line}"

        # Add to web queue
        ffmpeg_output_queue.put(decoded_line)
    process.stderr.close()

@app.route('/stream-output')
def stream_output():
    """Stream FFmpeg output to the client"""
    def generate():
        last_output_time = time.time()
        
        while True:
            current_time = time.time()
            # Check if there's output in the queue
            try:
                output = ffmpeg_output_queue.get_nowait()
                last_output_time = current_time
                yield f"data: {json.dumps({'output': output})}\n\n"
            except:
                # No output available, check if we should stop
                if current_time - last_output_time > 2.0:  # Stop if no output for 2 seconds
                    yield f"data: {json.dumps({'status': 'complete'})}\n\n"
                    break
                # Send heartbeat
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"
            time.sleep(0.1)
    
    return Response(stream_with_context(generate()), 
                   mimetype='text/event-stream')

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html',
                         fps_options=FPS_OPTIONS,
                         scale_options=SCALE_OPTIONS,
                         format_options=FORMAT_OPTIONS)

@app.route('/convert', methods=['POST'])
def convert():
    if 'video' not in request.files:
        return redirect(url_for('index'))
    
    video = request.files['video']
    if video.filename == '':
        return redirect(url_for('index'))

    if video:
        # Save uploaded video
        filename = secure_filename(video.filename)
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        video.save(video_path)

        print(f"\nStarting conversion of {filename}...", file=sys.stderr)
        sys.stderr.flush()

        # Get video duration for progress calculation
        global video_duration
        video_duration = get_video_duration(video_path)
        if video_duration:
            print(f"Video duration: {video_duration:.2f} seconds", file=sys.stderr)

        # Get conversion parameters
        fps = request.form.get('fps', '10')
        scale = request.form.get('scale', '480:-1')
        output_format = request.form.get('format', 'gif')
        
        # Generate output filename
        output_filename = f"output_{Path(filename).stem}.{output_format}"
        output_path = os.path.join('static/output', output_filename)

        # Base FFmpeg command with overwrite option
        cmd = ['ffmpeg', '-y', '-i', video_path]

        # Add format-specific options
        if output_format == 'gif':
            cmd.extend([
                '-vf', f'fps={fps},scale={scale}:flags=lanczos',
                '-c:v', 'gif'
            ])
        else:  # webm
            cmd.extend([
                '-vf', f'fps={fps},scale={scale}:flags=lanczos',
                '-c:v', 'libvpx',
                '-crf', '10',
                '-b:v', '1M',
                '-c:a', 'libvorbis',
                '-auto-alt-ref', '0',
                '-deadline', 'realtime',
                '-cpu-used', '8',
                '-progress', 'pipe:1'
            ])
        
        # Add output path
        cmd.append(output_path)

        print(f"Running command: {' '.join(cmd)}", file=sys.stderr)
        sys.stderr.flush()

        try:
            # Clear any previous output from the queue
            while not ffmpeg_output_queue.empty():
                ffmpeg_output_queue.get()

            # Run FFmpeg with output capture
            process = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                universal_newlines=False
            )

            # Start thread to process FFmpeg output
            output_thread = Thread(target=process_ffmpeg_output, args=(process,))
            output_thread.daemon = True
            output_thread.start()

            # Wait for conversion to complete
            process.wait()

            if process.returncode != 0:
                print(f"Conversion failed with return code {process.returncode}", file=sys.stderr)
                sys.stderr.flush()
                raise subprocess.CalledProcessError(process.returncode, cmd)

            print(f"Conversion completed successfully", file=sys.stderr)
            sys.stderr.flush()

            # Clean up uploaded video
            os.remove(video_path)
            
            return render_template('result.html', 
                                output_path=url_for('static', filename=f'output/{output_filename}'),
                                format=output_format)
        except subprocess.CalledProcessError:
            return "Conversion failed", 500

if __name__ == '__main__':
    app.run(debug=True, port=8000) 