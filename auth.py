import hashlib
import os
import secrets
from functools import wraps
from flask import session, redirect, url_for, flash, request, jsonify
from database import get_db

def hash_password(password: str) -> str:
    """Hash a password using PBKDF2 with SHA-256 and random salt"""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return f"{salt}:{key.hex()}"

def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored salt:hash string"""
    try:
        salt, key_hex = stored_hash.split(':')
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return secrets.compare_digest(key.hex(), key_hex)
    except Exception:
        return False

def get_current_user():
    """Retrieve logged-in user details from session"""
    user_id = session.get('user_id')
    if not user_id:
        return None
    with get_db() as conn:
        user = conn.execute("SELECT id, name, email, phone, role, address, city, state, pincode FROM users WHERE id = ?", (user_id,)).fetchone()
        return user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            if request.is_json or request.path.startswith('/api/admin'):
                return jsonify({'success': False, 'message': 'Admin authentication required'}), 401
            flash('Please log in with admin privileges to access the Admin Panel.', 'warning')
            return redirect(url_for('admin_login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def customer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            if request.is_json:
                return jsonify({'success': False, 'message': 'Please log in to proceed'}), 401
            flash('Please log in to view your account and orders.', 'info')
            return redirect(url_for('customer_login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function
