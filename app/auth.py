from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from .models import Usuario
from . import db, login_manager
from werkzeug.security import check_password_hash

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        senha = request.form.get('senha','').strip()
        if not username or not senha:
            flash('Preencha usuário e senha.', 'warning')
            return render_template('auth/login.html')
        user = Usuario.query.filter_by(username=username).first()
        if user and user.checar_senha(senha):
            login_user(user)
            user.last_login = __import__('datetime').datetime.utcnow()
            db.session.commit()
            flash('Bem-vindo ' + user.username, 'success')
            return redirect(url_for('index'))
        flash('Credenciais inválidas.', 'danger')
    return render_template('auth/login.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Desconectado.', 'info')
    return redirect(url_for('auth.login'))

@auth.route('/register', methods=['GET','POST'])
@login_required
def register():
    # only admin can create users
    if not current_user.is_authenticated or current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        senha = request.form.get('senha','').strip()
        role = request.form.get('role','comum')
        if not username or not senha:
            flash('Preencha usuário e senha.', 'warning')
            return render_template('auth/register.html')
        if Usuario.query.filter_by(username=username).first():
            flash('Usuário já existe.', 'danger')
            return render_template('auth/register.html')
        u = Usuario(username=username, role=role)
        u.set_senha(senha)
        db.session.add(u)
        db.session.commit()
        flash('Usuário criado!', 'success')
        return redirect(url_for('listar_usuarios'))
    return render_template('auth/register.html')