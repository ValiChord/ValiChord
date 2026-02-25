import os
import sys
import tempfile
import shutil
import zipfile
from pathlib import Path
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS

# add autogenerate to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'autogenerate'))

from detectors.failure_modes_simple import run_simple_detectors
from generators.report import generate_cleaning_report
from generators.drafts import generate_all_drafts

app = Flask(__name__)
CORS(app)

MAX_SIZE_MB = 100

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '1.0'})

@app.route('/analyse', methods=['POST'])
def analyse():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    f = request.files['file']
    if not f.filename.lower().endswith('.zip'):
        return jsonify({'error': 'File must be a .zip'}), 400

    work_dir = Path(tempfile.mkdtemp(prefix='valichord_'))
    try:
        upload_path = work_dir / 'upload.zip'
        f.save(str(upload_path))

        size_mb = upload_path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_SIZE_MB:
            return jsonify({'error': f'File too large ({size_mb:.0f}MB). Maximum is {MAX_SIZE_MB}MB.'}), 400

        repo_dir = work_dir / 'repository'
        output_dir = work_dir / 'output'
        repo_dir.mkdir()
        output_dir.mkdir()
        (output_dir / 'proposed_corrections').mkdir()

        with zipfile.ZipFile(upload_path, 'r') as zf:
            zf.extractall(repo_dir)

        def extract_nested(directory, depth=0):
            if depth > 3:
                return
            for nested in list(directory.rglob('*.zip')):
                if nested.stat().st_size > 100 * 1024 * 1024:
                    continue
                try:
                    dest = nested.parent / nested.stem
                    dest.mkdir(exist_ok=True)
                    with zipfile.ZipFile(nested, 'r') as zf:
                        zf.extractall(dest)
                    nested.unlink()
                    extract_nested(dest, depth + 1)
                except Exception:
                    pass

        extract_nested(repo_dir)

        all_files = [
            f for f in repo_dir.rglob('*')
            if f.is_file()
            and '.git' not in f.parts
            and '__pycache__' not in f.parts
            and f.name not in {'.DS_Store', 'Thumbs.db'}
        ]

        findings = run_simple_detectors(repo_dir, all_files)
        generate_all_drafts(repo_dir, all_files, findings, output_dir)
        generate_cleaning_report(f.filename, repo_dir, all_files, findings, output_dir)

        stem = Path(f.filename).stem
        output_zip = work_dir / f'valichord_output_{stem}.zip'
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in output_dir.rglob('*'):
                if file.is_file():
                    zf.write(file, file.relative_to(output_dir))

        return send_file(
            str(output_zip),
            as_attachment=True,
            download_name=f'valichord_output_{stem}.zip',
            mimetype='application/zip'
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
