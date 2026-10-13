"""Authentication routes: register, login, logout."""

from functools import wraps

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from extensions import db
from models import User

auth_bp = Blueprint("auth", __name__)


def guest_required(view):
    """Redirect authenticated users away from login/register."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user.is_authenticated:
            if current_user.is_admin:
                return redirect(url_for("dashboard.admin_dashboard"))
            return redirect(url_for("dashboard.student_dashboard"))
        return view(*args, **kwargs)

    return wrapped


@auth_bp.route("/register", methods=["GET", "POST"])
@guest_required
def register():
    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        role = (request.form.get("role") or "student").strip().lower()
        admin_code = (request.form.get("admin_code") or "").strip()

        if not full_name or not email or not password:
            flash("Name, email, and password are required.", "danger")
            return render_template("auth/register.html")

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("auth/register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template("auth/register.html")

        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "danger")
            return render_template("auth/register.html")

        if role not in ("student", "admin"):
            role = "student"

        if role == "admin":
            expected = current_app.config.get("ADMIN_SECRET_CODE", "")
            if not admin_code or admin_code != expected:
                flash("Invalid admin secret code. Register as student or contact support.", "danger")
                return render_template("auth/register.html")

        user = User(
            full_name=full_name,
            email=email,
            phone=phone or None,
            role=role,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
@guest_required
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html")

        login_user(user, remember=remember)
        flash(f"Welcome back, {user.full_name}!", "success")

        next_page = request.args.get("next")
        if next_page:
            return redirect(next_page)

        if user.is_admin:
            return redirect(url_for("dashboard.admin_dashboard"))
        return redirect(url_for("dashboard.student_dashboard"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
        flash("You have been logged out.", "info")
    return redirect(url_for("public.index"))
