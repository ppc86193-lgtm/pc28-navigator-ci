from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'PC28 Agent',
        'project_id': os.getenv('PROJECT_ID', 'unknown'),
        'work_mode': os.getenv('WORK_MODE', 'unknown')
    })

@app.route('/')
def home():
    return jsonify({
        'message': 'PC28 Agent is running in the cloud!',
        'project_id': os.getenv('PROJECT_ID'),
        'location': os.getenv('LOCATION'),
        'work_mode': os.getenv('WORK_MODE')
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
