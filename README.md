📦 BingeBox - Premium Streaming Platform & DBMS Engine
BingeBox is a premium Netflix-inspired streaming service clone engineered as a hyper-compressed, high-performance DBMS MVP application. The entire platform consists of just 3 files (1 Python backend server, 1 Single-Page HTML/CSS/JS frontend, and 1 requirements list), removing Node.js and all node_modules folders entirely.

✨ Features
Floating Glassmorphic Interface: Fully responsive, animated dark UI with custom carousels and categories.
Strict 5-Table DBMS MVP Schema: Leverages SQLite3 to map standard streaming relational tables.
Live SQL console Playground: Execute read-only SELECT queries on the database directly from the browser, formatting results in interactive tables.
Real-Time Watchlist Sync: Managed dynamically inside LocalStorage for sub-millisecond addition/removal UI syncs.
Custom HTML5 Video Player: Seamless fullscreen player that automatically saves progress bookmarks to the database every 5 seconds.
Flexible Aesthetics: Supports 3 custom themes (Cinema Slate, Midnight Black, Light Cinema) and interactive simulators (simulated download tracking and live friends activity feed).
📂 Project Architecture

bingebox/
├── app.py              # Flask Server, SQLite migrations, JWT auth, and API routes
├── requirements.txt    # Python package dependencies
├── .gitignore          # Git exclusion rules
└── static/
    └── index.html      # Responsive Single-Page UI (Tailwind CSS & Vanilla JS)
🗄️ Relational Database Schema
The SQLite database (bingebox.db) consists of exactly 5 relational tables:


  Users (user_id, username, email, password)
    │
    ├── Subscription (subscription_id, user_id, plan_name, status)
    │
    ├── Watch_History (history_id, user_id, content_id, watch_date, progress_seconds)
    │
    └── Ratings (rating_id, user_id, content_id, rating)
         │
  Content (content_id, title, genre, content_type, parent_content_id, season_number, episode_number)
🚀 Setup & Installation (Windows)
Prerequisites
Download and install Python.
IMPORTANT: Check the box "Add python.exe to PATH" in the installer before proceeding.
Installation
Open your terminal inside the project directory and run:

bash

# Install Python dependencies
pip install -r requirements.txt
Running the App
Start the unified backend server and database engine:

bash

python app.py
Open your browser and navigate to: http://localhost:5000

Click the "Use Guest Account (Instant Access)" button to log in and start streaming!

🎬 Streaming Local Video Files
Create a folder named videos/ in the root of the project directory.
Drop your downloaded video file (e.g. mymovie.mp4) into the folder.
Open the BingeBox SQL Console in your browser and execute:
sql

UPDATE Content SET video_url = '/videos/mymovie.mp4' WHERE content_id = 1;
Clicking "Watch Now" on that movie card will stream your local file!
