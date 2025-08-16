from flask import Flask, request, redirect, jsonify, render_template, url_for, flash
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import random, string
import psycopg2
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# In-memory database
url_map = {}

class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    link = db_setup()
    cursor = link.cursor()
    cursor.execute("SELECT id, username, password FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    link.close()
    if row:
        return User(*row)
    return None

def db_setup():
    try:
        link = psycopg2.connect(
            host="localhost",
            database="tinyurl",
            user="postgres",  
            password="Cosmic09",
            port=5432
        )
        print("Connected to PostgreSQL successfully!")
        return link

    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL: {e}")

def db_init():
    link = db_setup()
    cursor = link.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            long_url TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            clicks INTEGER DEFAULT 0
        )
    """)
    link.commit()
    link.close()
    cursor.close()

def save_url_to_db(code, long_url,user_id):
    link = db_setup()
    cursor = link.cursor()
    cursor.execute("INSERT INTO urls (code, long_url,user_id) VALUES (%s, %s,%s)", (code, long_url, user_id))
    link.commit()
    link.close()
    cursor.close()

def fetch_url_from_db(code):
    link = db_setup()
    cursor = link.cursor()
   
    cursor.execute("SELECT long_url FROM urls WHERE code = %s", (code,))
    row = cursor.fetchone()
    link.close()
    cursor.close()
    return row[0] if row else None

def fetch_all_urls():
    link = db_setup()
    cursor = link.cursor()
    cursor.execute("""
                    SELECT code, long_url, created_at, clicks
                    FROM urls WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 100
                """, (current_user.id,))
    return cursor.fetchall()

def delete_url(code):
    link = db_setup()
    cursor = link.cursor()
    cursor.execute("DELETE FROM urls WHERE code = %s", (code,))
    link.commit()
    link.close()
    cursor.close()

def generate_short_code():
    url_length = 6
    total_characters = string.ascii_letters + string.digits
    res = ""
    for _ in range(url_length):
        res = res + random.choice(total_characters)
    return res

def is_valid_url(u: str) -> bool:
    return u.startswith(("http://", "https://"))

def update_click_count(code):
    link = db_setup()   
    cursor = link.cursor()
    cursor.execute("UPDATE urls SET clicks = clicks + 1 WHERE code = %s", (code,))
    link.commit()
    link.close()
    cursor.close()
    ...

@app.route('/shorten', methods=['POST'])
@login_required
def shorten_url():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL format'}), 400
    code = generate_short_code()
    try:
        save_url_to_db(code,url,current_user.id)
        short_url = f"{request.host_url.rstrip('/')}/{code}"
        return jsonify({'shortened_url': short_url}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    ...

@app.route('/<code>')
@login_required
def redirect_to_url(code):
    url = fetch_url_from_db(code)
    if url:
        update_click_count(code)
        return redirect(url)
    return jsonify({'error': 'URL not found'}), 404
    ...

@app.route('/delete/<code>', methods=['DELETE'])
@login_required
def delete_short_url(code):
    try:
        delete_url(code)
        return jsonify({'message': 'URL deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# -----------------------
# Routes: Web UI
# -----------------------
@app.route("/", methods=["GET"])
@login_required
def landing():
    return render_template("index.html")

@app.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    return render_template("index.html")

@app.route("/shorten_form", methods=["POST"])
@login_required
def shorten_form():
    long_url = request.form.get("url", "").strip()
    if not long_url:
        flash("URL is required", "error")
        return redirect(url_for("home"))
    if not is_valid_url(long_url):
        flash("Invalid URL. Must start with http:// or https://", "error")
        return redirect(url_for("home"))

    code = generate_short_code()
    try:
        save_url_to_db(code, long_url,current_user.id)
    except Exception as e:
        flash(f"Failed to save URL: {e}", "error")
        return redirect(url_for("home"))

    short_url = f"{request.host_url.rstrip('/')}/{code}"
    flash(f"Shortened! {short_url}", "success")
    return redirect(url_for("home"))

@app.route("/list", methods=["GET"])
@login_required
def list_urls():
    rows = fetch_all_urls()
    # Precompute short links for the template
    base = request.host_url.rstrip("/")
    data = [
        {
            "code": r[0],
            "short_url": f"{base}/{r[0]}",
            "long_url": r[1],
            "created_at": r[2],
            "clicks": r[3],
        }
        for r in rows
    ]
    return render_template("list.html", urls=data)

# -----------------------
# Routes: SignUp and Login
# -----------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = bcrypt.generate_password_hash(request.form["password"]).decode("utf-8")

        conn = db_setup()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s) RETURNING id", (username, password))
            user_id = cur.fetchone()[0]
            conn.commit()
            user = User(user_id, username, password)
            login_user(user)
            flash("Signup successful!", "success")
            return redirect(url_for("dashboard"))
        except Exception as e:
            flash(f"Signup failed: {e}", "error")
        finally:
            cur.close()
            conn.close()

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = db_setup()
        cur = conn.cursor()
        cur.execute("SELECT id, username, password FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row and bcrypt.check_password_hash(row[2], password):
            user = User(*row)
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "error")

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out", "info")
    return redirect(url_for("login"))


if __name__ == "__main__":
    db_init()
    app.run(host="0.0.0.0", port=5000)
