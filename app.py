from flask import Flask, request, render_template, redirect, url_for, session, jsonify
from config import Config
from werkzeug.security import generate_password_hash, check_password_hash
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import sqlite3

app = Flask(__name__)
#app.secret_key =   # Replace with a strong secret key
app.config.from_object(Config)

# Database setup (For simplicity, using SQLite)
def init_db():
    conn = sqlite3.connect('businesses.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_type TEXT,
                  name TEXT,
                  business_name TEXT,
                  email TEXT UNIQUE,
                  phone TEXT UNIQUE,
                  password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS businesses
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  zip_code TEXT,
                  latitude REAL,
                  longitude REAL,
                  address TEXT,
                  city TEXT,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    conn.commit()
    conn.close()

# Function to geocode a zip code to latitude and longitude
def geocode_zip(zip_code):
    geolocator = Nominatim(user_agent="business_finder")
    location = geolocator.geocode({"postalcode": zip_code, "country": "United States"})
    if location:
        return (location.latitude, location.longitude)
    return None

# # Home page with login/signup options
# @app.route('/')
# def index():
#     return render_template('welcome.html')

# Home page with login/signup options
@app.route('/welcome')
def welcome():
    return render_template('welcome.html')

# Sign-up route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user_type = request.form['user_type']
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        hashed_password = generate_password_hash(password)

        if password != confirm_password:
            return "Passwords do not match!"

        business_name = None
        zip_code = None
        lat_lng = None
        if user_type == 'business':
            business_name = request.form['business_name']
            zip_code = request.form['zip_code']
            lat_lng = geocode_zip(zip_code)
            if lat_lng is None:
                return "Invalid ZIP code!"

        conn = sqlite3.connect('businesses.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (user_type, name, business_name, email, phone, password) VALUES (?, ?, ?, ?, ?, ?)",
                      (user_type, name, business_name, email, phone, hashed_password))
            user_id = c.lastrowid
            if user_type == 'business':
                c.execute("INSERT INTO businesses (user_id, zip_code, latitude, longitude) VALUES (?, ?, ?, ?)",
                          (user_id, zip_code, lat_lng[0], lat_lng[1]))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Email or phone number already exists!"

        conn.close()
        return redirect(url_for('login'))

    return render_template('signup.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['identifier']
        password = request.form['password']

        conn = sqlite3.connect('businesses.db')
        c = conn.cursor()
        c.execute("SELECT id, password FROM users WHERE email = ? OR phone = ?", (identifier, identifier))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            return redirect(url_for('index'))
        else:
            return "Invalid email/phone or password!"

    return render_template('login.html')

# Logout route
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

# Route to add a new business (requires login)
@app.route('/add', methods=['GET', 'POST'])
def add_business():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        address = request.form['address']
        city = request.form['city']
        zip_code = request.form['zip_code']

        lat_lng = geocode_zip(zip_code)
        if lat_lng is None:
            return "Invalid ZIP code!"

        conn = sqlite3.connect('businesses.db')
        c = conn.cursor()
        c.execute("INSERT INTO businesses (user_id, address, city, zip_code, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)",
                  (session['user_id'], address, city, zip_code, lat_lng[0], lat_lng[1]))
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "Business added successfully!"})

    return render_template('add_business.html')

# Route to search businesses by city or zip code within a 15-mile radius
@app.route('/search', methods=['GET'])
def search_businesses():
    zip_code = request.args.get('zip_code')

    if not zip_code:
        return "Please enter a ZIP code!"

    user_location = geocode_zip(zip_code)
    if user_location is None:
        return "Invalid ZIP code!"

    conn = sqlite3.connect('businesses.db')
    c = conn.cursor()
    c.execute("SELECT u.name, b.address, b.city, b.zip_code, b.latitude, b.longitude FROM businesses b JOIN users u ON b.user_id = u.id")
    businesses = c.fetchall()
    conn.close()

    results = []
    for business in businesses:
        business_location = (business[4], business[5])  # Latitude, Longitude
        distance = geodesic(user_location, business_location).miles
        if distance <= 15:
            results.append({
                "name": business[0],
                "address": business[1],
                "city": business[2],
                "zip_code": business[3],
                "distance": round(distance, 2)
            })

    if not results:
        return render_template('search_results.html', results=None)

    return render_template('search_results.html', results=results)

@app.route('/business-finder', methods=['GET', 'POST'])
def business_finder():
    if request.method == 'POST':
        zip_code = request.form['zip_code']
        return redirect(url_for('search'))
    return render_template('business_finder.html')


if __name__ == '__main__':
    init_db()  # Initialize the database
    app.run(debug=False) #set True when debugging
