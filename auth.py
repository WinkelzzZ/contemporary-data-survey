from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from bson import ObjectId
from db import get_db

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    confirm = request.form.get('confirm', '').strip()

    if not username or not password:
        flash('用户名和密码不能为空', 'error')
        return redirect(url_for('auth.register'))

    if len(username) < 3 or len(username) > 20:
        flash('用户名长度需在3-20个字符之间', 'error')
        return redirect(url_for('auth.register'))

    if len(password) < 6:
        flash('密码长度不能少于6个字符', 'error')
        return redirect(url_for('auth.register'))

    if password != confirm:
        flash('两次输入的密码不一致', 'error')
        return redirect(url_for('auth.register'))

    db = get_db()
    if db.users.find_one({'username': username}):
        flash('用户名已存在', 'error')
        return redirect(url_for('auth.register'))

    db.users.insert_one({
        'username': username,
        'password_hash': generate_password_hash(password),
        'created_at': datetime.now()
    })

    flash('注册成功，请登录', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    db = get_db()
    user = db.users.find_one({'username': username})

    if not user or not check_password_hash(user['password_hash'], password):
        flash('用户名或密码错误', 'error')
        return redirect(url_for('auth.login'))

    session['user_id'] = str(user['_id'])
    session['username'] = user['username']
    flash(f'欢迎回来，{username}！', 'success')
    next_url = session.pop('next_url', None)
    if next_url:
        return redirect(next_url)
    return redirect(url_for('survey.dashboard'))


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('已退出登录', 'success')
    return redirect(url_for('auth.login'))


def login_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'error')
            session['next_url'] = request.url
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated
