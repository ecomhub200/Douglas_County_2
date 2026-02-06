#!/usr/bin/env python3
"""
CRASH LENS - Pipeline Server

Lightweight HTTP server that bridges the browser UI to the Python data
processing pipeline. Accepts file uploads + state/jurisdiction from the
Upload Crash Data UI and runs process_crash_data.py.

Usage:
    python scripts/pipeline_server.py              # Default port 5050
    python scripts/pipeline_server.py --port 8080  # Custom port

Endpoints:
    POST /api/pipeline/run    - Upload CSV + trigger pipeline
    GET  /api/pipeline/status - Check pipeline progress
    GET  /api/pipeline/states - List supported states & their DOT folders
    GET  /health              - Health check
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import cgi

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
STATES_DIR = PROJECT_ROOT / 'states'
DATA_DIR = PROJECT_ROOT / 'data'

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('pipeline-server')

# Global pipeline state (single-user server)
pipeline_state = {
    'running': False,
    'stage': '',
    'progress': 0,
    'message': '',
    'result': None,
    'error': None,
    'started_at': None,
}


def get_state_dot_name(state_key):
    """Get the DOT folder name for a state from its config.json."""
    config_path = STATES_DIR / state_key / 'config.json'
    if config_path.exists():
        with open(config_path) as f:
            cfg = json.load(f)
        return cfg.get('state', {}).get('dotName', state_key.upper())
    # Fallback mapping for states without a config yet
    fallback = {
        'colorado': 'CDOT', 'virginia': 'VDOT', 'texas': 'TxDOT',
        'maryland': 'MDOT', 'northcarolina': 'NCDOT', 'pennsylvania': 'PennDOT',
    }
    return fallback.get(state_key, state_key.upper())


def get_supported_states():
    """Get list of supported states with config files."""
    states = {}
    for d in STATES_DIR.iterdir():
        if d.is_dir() and (d / 'config.json').exists():
            with open(d / 'config.json') as f:
                cfg = json.load(f)
            st = cfg.get('state', {})
            states[d.name] = {
                'key': d.name,
                'name': st.get('name', d.name.title()),
                'abbreviation': st.get('abbreviation', ''),
                'fips': st.get('fips', ''),
                'dotName': st.get('dotName', d.name.upper()),
                'dataFolder': f"data/{st.get('dotName', d.name.upper())}/",
            }
    return states


def run_pipeline(file_path, state_key, jurisdiction, dot_name):
    """Run the pipeline in a background thread."""
    global pipeline_state

    output_dir = str(DATA_DIR / dot_name)
    os.makedirs(output_dir, exist_ok=True)

    pipeline_state.update({
        'running': True,
        'stage': 'starting',
        'progress': 0,
        'message': 'Pipeline starting...',
        'result': None,
        'error': None,
        'started_at': time.time(),
    })

    cmd = [
        sys.executable,
        str(SCRIPT_DIR / 'process_crash_data.py'),
        '-i', file_path,
        '-s', state_key,
        '-j', jurisdiction,
        '-o', output_dir,
    ]

    logger.info("Running pipeline: %s", ' '.join(cmd))

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        output_lines = []
        for line in proc.stdout:
            line = line.strip()
            output_lines.append(line)
            logger.info("[pipeline] %s", line)

            # Parse stage progress from log output
            if 'STAGE 1: CONVERT' in line:
                pipeline_state['stage'] = 'convert'
                pipeline_state['progress'] = 10
                pipeline_state['message'] = 'Converting state format to standard...'
            elif 'STAGE 2: VALIDATE' in line:
                pipeline_state['stage'] = 'validate'
                pipeline_state['progress'] = 30
                pipeline_state['message'] = 'Validating data quality...'
            elif 'STAGE 3: GEOCODE' in line:
                pipeline_state['stage'] = 'geocode'
                pipeline_state['progress'] = 50
                pipeline_state['message'] = 'Geocoding missing GPS coordinates...'
            elif 'STAGE 4: SPLIT' in line:
                pipeline_state['stage'] = 'split'
                pipeline_state['progress'] = 80
                pipeline_state['message'] = 'Splitting into road-type files...'
            elif 'PIPELINE SUMMARY' in line:
                pipeline_state['progress'] = 95
                pipeline_state['message'] = 'Finalizing...'
            elif 'Node lookup:' in line:
                pipeline_state['message'] = line.split(']')[-1].strip() if ']' in line else line
            elif 'Nominatim' in line and 'progress' in line:
                pipeline_state['message'] = line.split(']')[-1].strip() if ']' in line else line

        proc.wait()

        if proc.returncode == 0:
            # Read pipeline report
            report_path = Path(output_dir) / '.validation' / 'pipeline_report.json'
            report = {}
            if report_path.exists():
                with open(report_path) as f:
                    report = json.load(f)

            # List output files
            output_files = []
            for pattern in [f'{jurisdiction}_all_roads.csv',
                            f'{jurisdiction}_county_roads.csv',
                            f'{jurisdiction}_no_interstate.csv',
                            f'{jurisdiction}_standardized.csv']:
                fp = Path(output_dir) / pattern
                if fp.exists():
                    output_files.append({
                        'name': pattern,
                        'path': str(fp.relative_to(PROJECT_ROOT)),
                        'size_mb': round(fp.stat().st_size / (1024 * 1024), 1),
                    })

            pipeline_state.update({
                'running': False,
                'stage': 'complete',
                'progress': 100,
                'message': 'Pipeline completed successfully',
                'result': {
                    'report': report,
                    'outputFiles': output_files,
                    'outputDir': str(Path(output_dir).relative_to(PROJECT_ROOT)),
                    'duration': round(time.time() - pipeline_state['started_at'], 1),
                },
            })
        else:
            pipeline_state.update({
                'running': False,
                'stage': 'error',
                'progress': 0,
                'message': f'Pipeline failed (exit code {proc.returncode})',
                'error': '\n'.join(output_lines[-20:]),
            })

    except Exception as e:
        logger.error("Pipeline error: %s", e)
        pipeline_state.update({
            'running': False,
            'stage': 'error',
            'progress': 0,
            'message': f'Pipeline error: {str(e)}',
            'error': str(e),
        })

    # Clean up temp file
    try:
        if os.path.exists(file_path) and '/tmp/' in file_path:
            os.remove(file_path)
    except OSError:
        pass


class PipelineHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the pipeline server."""

    def _cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/health':
            self._json_response({'status': 'ok', 'timestamp': datetime.utcnow().isoformat()})

        elif path == '/api/pipeline/status':
            self._json_response(pipeline_state)

        elif path == '/api/pipeline/states':
            self._json_response(get_supported_states())

        else:
            self._json_response({'error': 'Not found'}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/pipeline/run':
            self._handle_pipeline_run()
        else:
            self._json_response({'error': 'Not found'}, 404)

    def _handle_pipeline_run(self):
        global pipeline_state

        if pipeline_state['running']:
            self._json_response({
                'error': 'Pipeline already running',
                'stage': pipeline_state['stage'],
                'progress': pipeline_state['progress'],
            }, 409)
            return

        # Parse multipart form data
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            self._json_response({'error': 'Expected multipart/form-data'}, 400)
            return

        try:
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    'REQUEST_METHOD': 'POST',
                    'CONTENT_TYPE': content_type,
                }
            )

            # Extract fields
            state_key = form.getvalue('state', '').strip()
            jurisdiction = form.getvalue('jurisdiction', '').strip()
            file_item = form['file']

            if not state_key:
                self._json_response({'error': 'Missing state parameter'}, 400)
                return
            if not jurisdiction:
                self._json_response({'error': 'Missing jurisdiction parameter'}, 400)
                return
            if not file_item.filename:
                self._json_response({'error': 'Missing file upload'}, 400)
                return

            # Get DOT folder name
            dot_name = get_state_dot_name(state_key)

            # Save uploaded file to temp location
            suffix = os.path.splitext(file_item.filename)[1] or '.csv'
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix='crashlens_')
            with os.fdopen(tmp_fd, 'wb') as tmp_file:
                tmp_file.write(file_item.file.read())

            logger.info("Received: file=%s, state=%s, jurisdiction=%s, dotFolder=%s",
                         file_item.filename, state_key, jurisdiction, dot_name)

            # Start pipeline in background thread
            thread = threading.Thread(
                target=run_pipeline,
                args=(tmp_path, state_key, jurisdiction, dot_name),
                daemon=True,
            )
            thread.start()

            self._json_response({
                'status': 'started',
                'message': f'Pipeline started for {state_key}/{jurisdiction}',
                'outputDir': f'data/{dot_name}/',
                'pollUrl': '/api/pipeline/status',
            })

        except Exception as e:
            logger.error("Pipeline run error: %s", e)
            self._json_response({'error': str(e)}, 500)

    def log_message(self, format, *args):
        logger.info("%s %s", self.client_address[0], format % args)


def main():
    parser = argparse.ArgumentParser(description='CRASH LENS Pipeline Server')
    parser.add_argument('--port', type=int, default=5050, help='Server port (default: 5050)')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Server host (default: 0.0.0.0)')
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), PipelineHandler)
    logger.info("Pipeline server running on http://%s:%d", args.host, args.port)
    logger.info("Supported states: %s", ', '.join(get_supported_states().keys()))
    logger.info("Project root: %s", PROJECT_ROOT)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped")
        server.server_close()


if __name__ == '__main__':
    main()
