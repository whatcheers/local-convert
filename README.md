# Local Video Converter

A web-based tool for converting videos to GIF and WebM formats locally. Built with Flask and FFmpeg.

## Features

- Convert videos to GIF or WebM format
- Adjustable frame rate (5-30 FPS)
- Multiple resolution options (320p to 720p)
- Real-time conversion progress
- Live preview of uploaded video
- Console output display

## Requirements

- Python 3.x
- FFmpeg
- Flask

## Installation

1. Clone the repository:
```bash
git clone https://github.com/whatcheers/local-convert.git
cd local-convert
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Make sure FFmpeg is installed on your system

## Usage

1. Start the server:
```bash
python app.py
```

2. Open your browser and go to `http://localhost:8000`
3. Upload a video file
4. Select output format (GIF/WebM)
5. Choose frame rate and resolution
6. Click "Convert Video"

## License

MIT License - See LICENSE file for details 