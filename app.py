import os
import re
import datetime
import sqlite3
import jwt
import bcrypt
from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS
from functools import wraps

app = Flask(__name__)
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), 'bingebox.db')
JWT_SECRET = os.environ.get('JWT_SECRET', 'bingebox-super-secret-key-12345')

# =====================================================================
# DATABASE HELPER METHODS
# =====================================================================

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn

def db_run(sql, params=()):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id

def db_get(sql, params=()):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def db_all(sql, params=()):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# =====================================================================
# JWT AUTHENTICATION MIDDLEWARE
# =====================================================================

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'No authorization header found'}), 401
            
        try:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]
            else:
                return jsonify({'error': 'Token missing or invalid header format'}), 401
                
            decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            g.user = decoded
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid or expired token'}), 403
        except Exception as e:
            return jsonify({'error': 'Token validation failed'}), 403
            
        return f(*args, **kwargs)
    return decorated

# =====================================================================
# DATABASE CREATION & SEEDING
# =====================================================================

def init_db():
    print("Initializing SQLite Database (5-table relational schema)...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Drop existing tables
    tables = ['Ratings', 'Watch_History', 'Subscription', 'Content', 'Users']
    for t in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {t}")
        
    # 1. Users Table
    cursor.execute("""
        CREATE TABLE Users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    
    # 2. Content Table
    cursor.execute("""
        CREATE TABLE Content (
            content_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            genre TEXT NOT NULL,
            content_type TEXT NOT NULL,
            description TEXT,
            thumbnail_url TEXT,
            banner_url TEXT,
            video_url TEXT,
            rating REAL DEFAULT 0.0,
            parent_content_id INTEGER,
            season_number INTEGER,
            episode_number INTEGER,
            FOREIGN KEY (parent_content_id) REFERENCES Content (content_id) ON DELETE CASCADE
        )
    """)
    
    # 3. Subscription Table
    cursor.execute("""
        CREATE TABLE Subscription (
            subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_name TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES Users (user_id) ON DELETE CASCADE
        )
    """)
    
    # 4. Watch_History Table
    cursor.execute("""
        CREATE TABLE Watch_History (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content_id INTEGER NOT NULL,
            watch_date TEXT NOT NULL,
            progress_seconds INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES Users (user_id) ON DELETE CASCADE,
            FOREIGN KEY (content_id) REFERENCES Content (content_id) ON DELETE CASCADE
        )
    """)
    
    # 5. Ratings Table
    cursor.execute("""
        CREATE TABLE Ratings (
            rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES Users (user_id) ON DELETE CASCADE,
            FOREIGN KEY (content_id) REFERENCES Content (content_id) ON DELETE CASCADE,
            UNIQUE(user_id, content_id)
        )
    """)
    
    conn.commit()
    conn.close()
    
    # Seed mock data
    seed_db()

def seed_db():
    print("Seeding BingeBox database records...")
    password_hash = bcrypt.hashpw("password123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Users
    guest_id = db_run("INSERT INTO Users (username, email, password) VALUES (?, ?, ?)", ("GuestUser", "guest@bingebox.com", password_hash))
    sarah_id = db_run("INSERT INTO Users (username, email, password) VALUES (?, ?, ?)", ("SarahConnor", "sarah@bingebox.com", password_hash))
    neo_id = db_run("INSERT INTO Users (username, email, password) VALUES (?, ?, ?)", ("NeoTheOne", "neo@bingebox.com", password_hash))
    
    # Subscriptions
    db_run("INSERT INTO Subscription (user_id, plan_name, status) VALUES (?, ?, ?)", (guest_id, "Premium Ultra 4K", "Active"))
    db_run("INSERT INTO Subscription (user_id, plan_name, status) VALUES (?, ?, ?)", (sarah_id, "Standard HD", "Active"))
    db_run("INSERT INTO Subscription (user_id, plan_name, status) VALUES (?, ?, ?)", (neo_id, "Premium Ultra 4K", "Active"))
    
    # Content Catalog
    catalog = [
        # Sci-Fi
        {
            "title": "Cosmic Odyssey", "genre": "Sci-Fi", "content_type": "Movie",
            "description": "In the near future, an intrepid group of explorers embarks on a desperate interstellar mission to find a habitable planet for humanity. Guided by a strange signal from deep space, they traverse wormholes and survive temporal loops.",
            "thumbnail_url": "https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
        },
        {
            "title": "Dreamscape Inception", "genre": "Sci-Fi", "content_type": "Movie",
            "description": "A technology that allows scientists to enter and modify human dreams falls into dangerous hands. A seasoned dream thief is hired for one final job: planting a life-altering idea inside a sleeping billionaire's mind.",
            "thumbnail_url": "https://images.unsplash.com/photo-1478760329108-5c3ed9d495a0?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4"
        },
        {
            "title": "Cyber City 2099", "genre": "Sci-Fi", "content_type": "TV Show",
            "description": "In a neon-drenched metropolis controlled by cybernetic syndicates, a rogue detective searches for a missing AI that holds the key to humanity's liberation.",
            "thumbnail_url": "https://images.unsplash.com/photo-1515621061946-eff1c2a352bd?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1508739773434-c26b3d09e071?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4"
        },
        {
            "title": "The Martian Frontier", "genre": "Sci-Fi", "content_type": "TV Show",
            "description": "A documentary-style drama exploring the trials, political intrigues, and dangerous landscapes faced by the first human colony on Mars.",
            "thumbnail_url": "https://images.unsplash.com/photo-1614728894747-a83421e2b9c9?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1614314107204-b816223b320d?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4"
        },
        # Action
        {
            "title": "Shadow Knight", "genre": "Action", "content_type": "Movie",
            "description": "A vigilante rises from the criminal underbelly of a decaying metropolis. Fighting corruption and high-tech corporate espionage, he must confront his own tragic past to save the city from complete anarchy.",
            "thumbnail_url": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4"
        },
        {
            "title": "Gladiator of Rome", "genre": "Action", "content_type": "Movie",
            "description": "Set in ancient Rome, a disgraced general is betrayed and forced into slavery. Reborn as a lethal gladiator in the Colosseum, he fights his way up to seek vengeance against the corrupt Emperor who slaughtered his family.",
            "thumbnail_url": "https://images.unsplash.com/photo-1558591710-4b4a1ae0f04d?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1533105079780-92b9be482077?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4"
        },
        {
            "title": "Apex Predators", "genre": "Action", "content_type": "Movie",
            "description": "When an elite black-ops team is stranded in a dense jungle containing biological mutations, they must use primitive instincts to survive the night.",
            "thumbnail_url": "https://images.unsplash.com/photo-1535498730771-e735b998cd64?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1519074069444-1ba4e6664104?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerMeltdowns.mp4"
        },
        # Drama
        {
            "title": "The Jester's Smile", "genre": "Drama", "content_type": "Movie",
            "description": "A struggling street performer is pushed to the edge by economic hardship and social isolation. Finding solace in a dark, theatrical alter ego, he accidentally sparks a massive popular movement.",
            "thumbnail_url": "https://images.unsplash.com/photo-1514306191717-452ec28c7814?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1485846234645-a62644f84728?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"
        },
        {
            "title": "Echoes of Silence", "genre": "Drama", "content_type": "Movie",
            "description": "A deaf-mute sculptor in a remote coastal village discovers a washed-up container carrying a mysterious child. Through quiet interactions, they heal each other's hidden grief.",
            "thumbnail_url": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutbackOnStreetAndDirt.mp4"
        },
        {
            "title": "Legacy & Lies", "genre": "Drama", "content_type": "TV Show",
            "description": "A powerful media conglomerate is thrown into chaos when its aging patriarch suffers a stroke, launching his four manipulative children into a toxic civil war for control.",
            "thumbnail_url": "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1450133064473-71024230f91b?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4"
        },
        # Comedy
        {
            "title": "Lost in Tokyo", "genre": "Comedy", "content_type": "Movie",
            "description": "Three best friends embark on a wild bachelor weekend in Tokyo, only to wake up with no memory of the previous night, a missing groom, and a baby panda in their hotel room.",
            "thumbnail_url": "https://images.unsplash.com/photo-1540959733332-eab4deceeaf7?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1503899036084-c55cdd92da26?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4"
        },
        {
            "title": "Office Politics", "genre": "Comedy", "content_type": "TV Show",
            "description": "A mockumentary surrounding the mundane, hilarious, and bizarre daily lives of office workers in a mid-sized paper distribution branch in Pennsylvania.",
            "thumbnail_url": "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1497366216548-37526070297c?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
        },
        {
            "title": "Suburban Chaos", "genre": "Comedy", "content_type": "Movie",
            "description": "When two nerdy high school seniors decide to throw a legendary house party to get noticed, they accidentally set off a series of explosions, car chases, and neighborhood brawls.",
            "thumbnail_url": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4"
        },
        # Romance
        {
            "title": "Chords of Love", "genre": "Romance", "content_type": "Movie",
            "description": "In the heart of romantic Paris, an aspiring jazz pianist and a passionate street artist cross paths. Through shared melodies and vibrant canvases, they discover a connection that challenges their creative ambitions.",
            "thumbnail_url": "https://images.unsplash.com/photo-1518199266791-5375a83190b7?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1494905998402-395d579af36f?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4"
        },
        {
            "title": "A Midnight Stroll", "genre": "Romance", "content_type": "Movie",
            "description": "Two strangers meet on a train from Vienna and decide to spend a single night wandering the streets together, talking about life, love, and destiny before parting at sunrise.",
            "thumbnail_url": "https://images.unsplash.com/photo-1517457373958-b7bdd4587205?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutbackOnStreetAndDirt.mp4"
        },
        {
            "title": "Heartstrings", "genre": "Romance", "content_type": "TV Show",
            "description": "A popular romantic drama series tracking the complicated, overlapping relationship histories of six young residents living in a cozy apartment block in Seattle.",
            "thumbnail_url": "https://images.unsplash.com/photo-1464746133101-a2c3f88e0dd9?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1516062423079-7ca13cdc7f5a?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4"
        },
        # Thriller
        {
            "title": "Intruders", "genre": "Thriller", "content_type": "Movie",
            "description": "An unemployed family of four slowly infiltrates the household of a wealthy estate owner. What starts as a series of clever cons quickly spirals into a dark, shocking battle for survival.",
            "thumbnail_url": "https://images.unsplash.com/photo-1505635338219-0a113f6ec6a6?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4"
        },
        {
            "title": "The Cipher Code", "genre": "Thriller", "content_type": "Movie",
            "description": "A brilliant cryptographer is recruited by a shadow government agency to crack a complex distress code sent from a deep-sea research lab, only to realize he is deciphering his own future.",
            "thumbnail_url": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1504639725590-34d0984388bd?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4"
        },
        # Documentary
        {
            "title": "Culinary Masters", "genre": "Documentary", "content_type": "TV Show",
            "description": "An intimate look into the lives, philosophies, and exquisite kitchens of three world-renowned chefs. Explore how they blend traditional techniques with cutting-edge gastronomy.",
            "thumbnail_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutbackOnStreetAndDirt.mp4"
        },
        {
            "title": "Planet Earth Rising", "genre": "Documentary", "content_type": "TV Show",
            "description": "An immersive journey across the world's most remote ecosystems, capturing the beauty, struggle, and survival stories of rare wildlife species using ultra-high-definition cameras.",
            "thumbnail_url": "https://images.unsplash.com/photo-1473448912268-2022ce9509d8?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
        },
        # Anime
        {
            "title": "Forest Spirits", "genre": "Anime", "content_type": "Movie",
            "description": "When a young girl wanders into a hidden forest sanctuary, she discovers an enchanted realm populated by ancient spirits and mythical creatures. She must help them save their home.",
            "thumbnail_url": "https://images.unsplash.com/photo-1502082553048-f009c37129b9?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1448375240586-882707db888b?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerMeltdowns.mp4"
        },
        {
            "title": "Neon Genesis Mech", "genre": "Anime", "content_type": "TV Show",
            "description": "Teenage pilots are recruited to navigate massive biomechanical mechs to defend a post-apocalyptic Tokyo from mysterious extra-dimensional entities.",
            "thumbnail_url": "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1563089145-599997674d42?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4"
        },
        # Horror
        {
            "title": "The Haunting of Hillside", "genre": "Horror", "content_type": "TV Show",
            "description": "A fractured family confronts haunting memories of their old home and the terrifying events that drove them from it.",
            "thumbnail_url": "https://images.unsplash.com/photo-1505635338219-0a113f6ec6a6?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1509248961158-e54f6934749c?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
        },
        {
            "title": "Cabin in the Woods", "genre": "Horror", "content_type": "Movie",
            "description": "Five teenagers head to a remote cabin in the woods, where they get far more than they bargained for as they uncover a shocking industrial experiment.",
            "thumbnail_url": "https://images.unsplash.com/photo-1524850301259-772984de37ed?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1518818419601-72c8673f5852?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4"
        },
        # Fantasy
        {
            "title": "Kingdom of Runes", "genre": "Fantasy", "content_type": "Movie",
            "description": "An ancient prophecy sends a young blacksmith on a quest to restore the forgotten magic of the Runes and unite the warring kingdoms.",
            "thumbnail_url": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1448375240586-882707db888b?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4"
        },
        {
            "title": "The Last Druid", "genre": "Fantasy", "content_type": "Movie",
            "description": "As the age of nature declines, the last surviving druid protector must shield a magical seedling from the high-tech empire of glass and steel.",
            "thumbnail_url": "https://images.unsplash.com/photo-1502082553048-f009c37129b9?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1473448912268-2022ce9509d8?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4"
        },
        # Mystery
        {
            "title": "Murder at Midnight", "genre": "Mystery", "content_type": "Movie",
            "description": "A retired inspector is trapped in a luxury estate with nine suspects after the host is found dead. Every clock in the house has stopped at exactly midnight.",
            "thumbnail_url": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4"
        },
        {
            "title": "Vanishing Point", "genre": "Mystery", "content_type": "TV Show",
            "description": "When a commuter train vanishes inside a tunnel without triggering any alarms or sensor trips, an investigator must follow a trail of impossible anomalies.",
            "thumbnail_url": "https://images.unsplash.com/photo-1532012197267-da84d127e765?w=600&auto=format&fit=crop&q=80",
            "banner_url": "https://images.unsplash.com/photo-1478760329108-5c3ed9d495a0?w=1600&auto=format&fit=crop&q=80",
            "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutbackOnStreetAndDirt.mp4"
        }
    ]
    
    for item in catalog:
        import random
        rating = round(4.0 + random.random() * 1.0, 1)
        db_run(
            """INSERT INTO Content 
               (title, genre, content_type, description, thumbnail_url, banner_url, video_url, rating) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (item["title"], item["genre"], item["content_type"], item["description"], 
             item["thumbnail_url"], item["banner_url"], item["video_url"], rating)
        )
        
    # Episodes for "Cyber City 2099"
    cyber_city = db_get("SELECT content_id FROM Content WHERE title = 'Cyber City 2099'")
    if cyber_city:
        p_id = cyber_city["content_id"]
        cyber_episodes = [
            {
                "title": "Genesis of Neon", "season": 1, "episode": 1,
                "desc": "A rogue detective recovers a piece of memory from a junked synthetic unit, launching him into the cyber underworld.",
                "vid": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4",
                "thumb": "https://images.unsplash.com/photo-1515621061946-eff1c2a352bd?w=600&auto=format&fit=crop&q=80"
            },
            {
                "title": "The Digital Ghost", "season": 1, "episode": 2,
                "desc": "Chasing a shadow network entity, the detective is cornered by military androids and rescued by an AI cultist.",
                "vid": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4",
                "thumb": "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=600&auto=format&fit=crop&q=80"
            },
            {
                "title": "Synthetic Dreams", "season": 1, "episode": 3,
                "desc": "A search inside the memory cores of a corporate executive reveals a shocking experiment about human consciousness mapping.",
                "vid": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
                "thumb": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=600&auto=format&fit=crop&q=80"
            }
        ]
        for ep in cyber_episodes:
            db_run(
                """INSERT INTO Content 
                   (title, genre, content_type, description, thumbnail_url, banner_url, video_url, rating, parent_content_id, season_number, episode_number)
                   VALUES (?, ?, 'Episode', ?, ?, ?, ?, 4.5, ?, ?, ?)""",
                (ep["title"], "Sci-Fi", ep["desc"], ep["thumb"], ep["thumb"], ep["vid"], p_id, ep["season"], ep["episode"])
            )
            
    # Episodes for "Office Politics"
    office = db_get("SELECT content_id FROM Content WHERE title = 'Office Politics'")
    if office:
        p_id = office["content_id"]
        office_episodes = [
            {
                "title": "The Local Merger", "season": 1, "episode": 1,
                "desc": "Rumors of downsizing circulate while the regional manager tries to paint a bright picture of branch sales statistics.",
                "vid": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
                "thumb": "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=600&auto=format&fit=crop&q=80"
            },
            {
                "title": "The Fire Drill Incident", "season": 1, "episode": 2,
                "desc": "An overzealous safety inspector locks the doors and simulates a fire, triggering panic, chaos, and cat-throwing in the office.",
                "vid": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4",
                "thumb": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=600&auto=format&fit=crop&q=80"
            }
        ]
        for ep in office_episodes:
            db_run(
                """INSERT INTO Content 
                   (title, genre, content_type, description, thumbnail_url, banner_url, video_url, rating, parent_content_id, season_number, episode_number)
                   VALUES (?, ?, 'Episode', ?, ?, ?, ?, 4.2, ?, ?, ?)""",
                (ep["title"], "Comedy", ep["desc"], ep["thumb"], ep["thumb"], ep["vid"], p_id, ep["season"], ep["episode"])
            )

    # Seed some mock ratings/history for guest
    scifi = db_all("SELECT content_id FROM Content WHERE genre = 'Sci-Fi'")
    if len(scifi) >= 2:
        db_run("INSERT INTO Watch_History (user_id, content_id, watch_date, progress_seconds) VALUES (?, ?, '2026-07-08', 350)", (guest_id, scifi[0]["content_id"]))
        db_run("INSERT INTO Ratings (user_id, content_id, rating) VALUES (?, ?, 5)", (guest_id, scifi[0]["content_id"]))
        db_run("INSERT INTO Watch_History (user_id, content_id, watch_date, progress_seconds) VALUES (?, ?, '2026-07-08', 120)", (guest_id, scifi[1]["content_id"]))
        db_run("INSERT INTO Ratings (user_id, content_id, rating) VALUES (?, ?, 4)", (guest_id, scifi[1]["content_id"]))

    print("BingeBox seeding complete.")

# =====================================================================
# API ENDPOINTS
# =====================================================================

# Authentication Blueprints
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    plan_name = data.get('plan_name', 'Standard HD')
    
    if not username or not email or not password:
        return jsonify({'error': 'Please provide username, email, and password'}), 400
        
    try:
        existing = db_get('SELECT * FROM Users WHERE email = ?', (email,))
        if existing:
            return jsonify({'error': 'Email already registered'}), 400
            
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user_id = db_run('INSERT INTO Users (username, email, password) VALUES (?, ?, ?)', (username, email, password_hash))
        db_run('INSERT INTO Subscription (user_id, plan_name, status) VALUES (?, ?, ?)', (user_id, plan_name, 'Active'))
        
        payload = {
            'user_id': user_id, 'email': email, 'username': username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
        return jsonify({
            'token': token,
            'user': {'user_id': user_id, 'username': username, 'email': email, 'plan_name': plan_name, 'status': 'Active'}
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Please provide email and password'}), 400
        
    try:
        user = db_get('SELECT * FROM Users WHERE email = ?', (email,))
        if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            return jsonify({'error': 'Invalid email or password'}), 400
            
        sub = db_get('SELECT plan_name, status FROM Subscription WHERE user_id = ?', (user['user_id'],))
        
        payload = {
            'user_id': user['user_id'], 'email': user['email'], 'username': user['username'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
        return jsonify({
            'token': token,
            'user': {
                'user_id': user['user_id'], 'username': user['username'], 'email': user['email'],
                'plan_name': sub['plan_name'] if sub else 'No Subscription', 'status': sub['status'] if sub else 'Inactive'
            }
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/me', methods=['GET'])
@token_required
def me():
    try:
        user = db_get('SELECT user_id, username, email FROM Users WHERE user_id = ?', (g.user['user_id'],))
        if not user:
            return jsonify({'error': 'User not found'}), 404
        sub = db_get('SELECT plan_name, status FROM Subscription WHERE user_id = ?', (user['user_id'],))
        return jsonify({
            'user_id': user['user_id'], 'username': user['username'], 'email': user['email'],
            'plan_name': sub['plan_name'] if sub else 'No Subscription', 'status': sub['status'] if sub else 'Inactive'
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Content Catalog Endpoints
@app.route('/api/content', methods=['GET'])
@token_required
def get_content():
    genre = request.args.get('genre')
    content_type = request.args.get('content_type')
    q = request.args.get('q')
    
    sql = "SELECT * FROM Content WHERE parent_content_id IS NULL"
    params = []
    if genre:
        sql += " AND genre = ?"
        params.append(genre)
    if content_type:
        sql += " AND content_type = ?"
        params.append(content_type)
    if q:
        sql += " AND (title LIKE ? OR description LIKE ?)"
        params.append(f"%{q}%")
        params.append(f"%{q}%")
        
    try:
        items = db_all(sql, params)
        return jsonify(items), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/content/featured', methods=['GET'])
@token_required
def get_featured():
    try:
        featured = db_get('SELECT * FROM Content WHERE parent_content_id IS NULL ORDER BY rating DESC LIMIT 1')
        return jsonify(featured), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/content/<int:content_id>/episodes', methods=['GET'])
@token_required
def get_episodes(content_id):
    try:
        episodes = db_all('SELECT * FROM Content WHERE parent_content_id = ? ORDER BY season_number, episode_number', (content_id,))
        return jsonify(episodes), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/content/<int:content_id>', methods=['GET'])
@token_required
def get_details(content_id):
    try:
        item = db_get('SELECT * FROM Content WHERE content_id = ?', (content_id,))
        if not item:
            return jsonify({'error': 'Not found'}), 404
        return jsonify(item), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/content/recommendations', methods=['GET'])
@token_required
def get_recommendations():
    user_id = g.user['user_id']
    try:
        # Preferred genre query
        pref_query = """
            SELECT c.genre, COUNT(*) as cnt
            FROM Watch_History h
            JOIN Content c ON h.content_id = c.content_id
            WHERE h.user_id = ?
            GROUP BY c.genre
            ORDER BY cnt DESC
            LIMIT 1
        """
        pref = db_get(pref_query, (user_id,))
        recommendations = []
        if pref:
            # Unwatched items in preferred genre
            rec_query = """
                SELECT * FROM Content
                WHERE genre = ? AND parent_content_id IS NULL
                  AND content_id NOT IN (SELECT content_id FROM Watch_History WHERE user_id = ?)
                ORDER BY rating DESC LIMIT 10
            """
            recommendations = db_all(rec_query, (pref['genre'], user_id))
            
        if not recommendations:
            # Fallback: top rated unwatched items
            fallback_query = """
                SELECT * FROM Content
                WHERE parent_content_id IS NULL
                  AND content_id NOT IN (SELECT content_id FROM Watch_History WHERE user_id = ?)
                ORDER BY rating DESC LIMIT 10
            """
            recommendations = db_all(fallback_query, (user_id,))
            
        return jsonify(recommendations), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/content/sql-query', methods=['POST'])
@token_required
def run_sql():
    data = request.get_json() or {}
    sql = data.get('sql')
    if not sql:
        return jsonify({'error': 'SQL query text is required'}), 400
        
    query_clean = sql.strip().upper()
    if not query_clean.startswith('SELECT'):
        return jsonify({'error': 'SQL Execution Denied: For security reasons, the SQL Playground only runs read-only SELECT statements.'}), 403
        
    forbidden = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE', 'REPLACE']
    for kw in forbidden:
        if re.search(r'\b' + re.escape(kw) + r'\b', sql, re.IGNORECASE):
            return jsonify({'error': f"SQL Execution Denied: Forbidden modification keyword '{kw}' detected."}), 403
            
    try:
        res = db_all(sql)
        return jsonify({'success': True, 'data': res}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# Interactions Endpoints
@app.route('/api/interactions/history', methods=['GET', 'POST'])
@token_required
def handle_history():
    user_id = g.user['user_id']
    if request.method == 'GET':
        try:
            sql = """
                SELECT h.*, c.title, c.description, c.thumbnail_url, c.banner_url, c.video_url, c.genre, c.content_type
                FROM Watch_History h
                JOIN Content c ON h.content_id = c.content_id
                WHERE h.user_id = ?
                ORDER BY h.history_id DESC
            """
            history = db_all(sql, (user_id,))
            return jsonify(history), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        # POST: Save progress
        data = request.get_json() or {}
        content_id = data.get('content_id')
        progress_seconds = data.get('progress_seconds', 0)
        if not content_id:
            return jsonify({'error': 'content_id required'}), 400
            
        watch_date = datetime.date.today().isoformat()
        try:
            existing = db_get('SELECT * FROM Watch_History WHERE user_id = ? AND content_id = ?', (user_id, content_id))
            if existing:
                db_run('UPDATE Watch_History SET watch_date = ?, progress_seconds = ? WHERE history_id = ?',
                       (watch_date, progress_seconds, existing['history_id']))
            else:
                db_run('INSERT INTO Watch_History (user_id, content_id, watch_date, progress_seconds) VALUES (?, ?, ?, ?)',
                       (user_id, content_id, watch_date, progress_seconds))
            return jsonify({'message': 'Watch history updated'}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/interactions/ratings/<int:content_id>', methods=['GET'])
@token_required
def get_rating(content_id):
    user_id = g.user['user_id']
    try:
        row = db_get('SELECT rating FROM Ratings WHERE user_id = ? AND content_id = ?', (user_id, content_id))
        return jsonify({'rating': row['rating'] if row else 0}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/interactions/ratings', methods=['POST'])
@token_required
def submit_rating():
    user_id = g.user['user_id']
    data = request.get_json() or {}
    content_id = data.get('content_id')
    rating_val = data.get('rating')
    
    if not content_id or rating_val is None:
        return jsonify({'error': 'Please provide content_id and rating'}), 400
        
    try:
        rating_int = int(rating_val)
        if rating_int < 1 or rating_int > 5:
            raise ValueError()
    except ValueError:
        return jsonify({'error': 'Rating must be an integer between 1 and 5'}), 400
        
    try:
        db_run("""
            INSERT INTO Ratings (user_id, content_id, rating) VALUES (?, ?, ?)
            ON CONFLICT(user_id, content_id) DO UPDATE SET rating = excluded.rating
        """, (user_id, content_id, rating_int))
        
        avg_row = db_get('SELECT AVG(rating) as avg_r FROM Ratings WHERE content_id = ?', (content_id,))
        avg_rating = round(float(avg_row['avg_r']), 1) if avg_row and avg_row['avg_r'] is not None else float(rating_int)
        db_run('UPDATE Content SET rating = ? WHERE content_id = ?', (avg_rating, content_id))
        
        return jsonify({'message': 'Rating saved', 'averageRating': avg_rating}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =====================================================================
# STATIC INTERFACE & LOCAL STREAMING ROUTES
# =====================================================================

# Route to serve local downloaded files
@app.route('/videos/<path:filename>')
def serve_videos(filename):
    video_dir = os.path.join(os.path.dirname(__file__), 'videos')
    return send_from_directory(video_dir, filename)

# Root route serving single-page HTML client
@app.route('/')
def serve_index():
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    return send_from_directory(static_dir, 'index.html')

# Serve other static assets if placed in static folder
@app.route('/<path:filename>')
def serve_static(filename):
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    return send_from_directory(static_dir, filename)

# Health endpoint
@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'service': 'BingeBox Single-File Python API',
        'timestamp': datetime.datetime.now().isoformat()
    }), 200

if __name__ == '__main__':
    # Build database schema if not exists
    if not os.path.exists(DB_PATH):
        init_db()
    else:
        # Quick validation/repair if empty
        test = db_get("SELECT COUNT(*) as c FROM Content")
        if not test or test['c'] == 0:
            init_db()
            
    # Setup videos placeholder folder
    v_dir = os.path.join(os.path.dirname(__file__), 'videos')
    os.makedirs(v_dir, exist_ok=True)
    with open(os.path.join(v_dir, 'PLACE_MOVIES_HERE.txt'), 'w') as f:
        f.write("BingeBox Local Streaming Folder\nDrop local downloaded video files (.mp4 etc.) in this folder, then update your database video_url field to /videos/yourfile.mp4 to stream them directly on the site.\n")
        
    print("=======================================================================")
    print(" BingeBox unified Flask + Database engine is online!                    ")
    print(" Listening on: http://localhost:5000                                   ")
    print("=======================================================================")
    app.run(host='0.0.0.0', port=5000, debug=True)
