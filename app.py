from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
def index():
    """Display the Danube cruise navigation status page."""
    route = [
        {"name": "Budapest", "status": "unknown"},
        {"name": "Bratislava", "status": "unknown"},
        {"name": "Vienna", "status": "unknown"},
        {"name": "Wachau", "status": "unknown"},
        {"name": "Linz", "status": "unknown"},
        {"name": "Passau", "status": "unknown"},
        {"name": "Vilshofen", "status": "unknown"},
        {"name": "Regensburg", "status": "unknown"},
    ]
    return render_template("index.html", route=route)


if __name__ == "__main__":
    app.run(debug=True)
