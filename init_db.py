# init_db.py - With debugging
import sqlite3
import hashlib
import os

def hash_password(password):
    """Simple password hashing"""
    hashed = hashlib.sha256(password.encode()).hexdigest()
    print(f"🔑 Password '{password}' hashed to: {hashed[:20]}...")
    return hashed

def init_db():
    # Delete existing database if it exists
    if os.path.exists('retail.db'):
        os.remove('retail.db')
        print("🗑️  Deleted old database")
    
    print("📦 Creating new database...")
    
    conn = sqlite3.connect('retail.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✅ Created users table")
    
    # Create datasets table
    cursor.execute('''
        CREATE TABLE datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT,
            original_filename TEXT,
            file_path TEXT,
            total_rows INTEGER,
            total_columns INTEGER,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    print("✅ Created datasets table")
    
    # Create reports table
    cursor.execute('''
        CREATE TABLE reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            dataset_id INTEGER,
            report_name TEXT,
            report_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (dataset_id) REFERENCES datasets (id)
        )
    ''')
    print("✅ Created reports table")
    
    # Insert admin user
    hashed = hash_password('admin123')
    
    cursor.execute('''
        INSERT INTO users (username, email, password, full_name)
        VALUES (?, ?, ?, ?)
    ''', ('admin', 'admin@example.com', hashed, 'Admin User'))
    
    conn.commit()
    print("✅ Admin user inserted")
    
    # Verify the user was created correctly
    cursor.execute("SELECT id, username, password FROM users WHERE username = 'admin'")
    user = cursor.fetchone()
    
    if user:
        print(f"👤 User ID: {user[0]}")
        print(f"👤 Username: {user[1]}")
        print(f"🔑 Password hash: {user[2][:30]}...")
        
        # Test the password
        test_hash = hash_password('admin123')
        if user[2] == test_hash:
            print("✅ Password verification: MATCHES!")
        else:
            print("❌ Password verification: MISMATCH!")
            print(f"   Stored: {user[2]}")
            print(f"   Test:   {test_hash}")
    else:
        print("❌ Failed to create admin user")
    
    conn.close()
    
    print("\n" + "="*50)
    print("✅ Database setup complete!")
    print("📝 Login with:")
    print("   Username: admin")
    print("   Password: admin123")
    print("="*50)

if __name__ == '__main__':
    init_db()