from flask import Flask, render_template, request, redirect, url_for, session
from functools import wraps

PORT = 5000

app = Flask(__name__)
app.secret_key = "your-secret-key"  # In production, use a secure secret key

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "admin" and password == "admin":
            session["logged_in"] = True
            return redirect(url_for("protected"))
        return "Invalid credentials", 401
    return render_template("login.html")

@app.route("/")
@login_required
def protected():
    return render_template("protected.html")

if __name__ == "__main__":
    app.run(debug=True, port=PORT) 