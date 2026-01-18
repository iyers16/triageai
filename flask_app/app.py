from flask import Flask, jsonify, request, render_template

app = Flask(__name__)

# Serve the homepage
@app.route('/')
def home():
    return render_template('index.html')

# Example API endpoint
@app.route('/api/data', methods=['POST'])
def get_data():
    data = request.json  # Get JSON sent from JS
    name = data.get('name', 'World')
    print("GOT IT!")
    # Respond with a message
    return jsonify({"message": f"Hello, {name}!"})

if __name__ == '__main__':
    app.run(debug=True)
