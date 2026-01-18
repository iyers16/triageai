from flask import Flask, jsonify, request, render_template
import sys

app = Flask(__name__)

# Log every single request
@app.before_request
def log_request():
    print("\n" + "=" * 60, file=sys.stderr, flush=True)
    print(f"INCOMING REQUEST: {request.method} {request.path}", file=sys.stderr, flush=True)
    print(f"Headers: {dict(request.headers)}", file=sys.stderr, flush=True)
    print("=" * 60 + "\n", file=sys.stderr, flush=True)

@app.route('/')
def home():
    print("HOMEPAGE HANDLER CALLED", file=sys.stderr, flush=True)
    return render_template('index.html')

@app.route('/api/data', methods=['POST'])
def get_data():
    print("API HANDLER CALLED!!!", file=sys.stderr, flush=True)
    
    data = request.json
    print(f"Data: {data}", file=sys.stderr, flush=True)
    
    name = data.get('name', 'World')
    return jsonify({"message": f"Hello, {name}!"})

if __name__ == '__main__':
    print("Flask starting...", file=sys.stderr, flush=True)
    app.run(debug=True, use_reloader=False)
