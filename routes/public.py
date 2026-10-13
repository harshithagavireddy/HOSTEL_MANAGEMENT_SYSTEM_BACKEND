"""Public-facing routes: homepage, contact/enquiry, room booking entry."""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models import Booking, Enquiry, Room

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    rooms = Room.query.filter_by(is_available=True).order_by(Room.price_monthly.desc()).all()
    return render_template("index.html", rooms=rooms)


@public_bp.route("/contact", methods=["POST"])
def contact():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    message = (request.form.get("message") or "").strip()

    if not name or not email or not message:
        flash("Please fill in all contact fields.", "danger")
        return redirect(url_for("public.index") + "#contact")

    enquiry = Enquiry(name=name, email=email, message=message)
    db.session.add(enquiry)
    db.session.commit()

    flash("Thank you! Your message was sent successfully. Our team will contact you shortly.", "success")
    return redirect(url_for("public.index") + "#contact")


@public_bp.route("/book/<int:room_id>", methods=["GET", "POST"])
@login_required
def book_room(room_id):
    room = Room.query.get_or_404(room_id)

    if not room.is_available:
        flash("Sorry, this room is no longer available.", "warning")
        return redirect(url_for("public.index") + "#rooms")

    if current_user.is_admin:
        flash("Admins cannot book rooms. Use the admin dashboard to manage bookings.", "info")
        return redirect(url_for("dashboard.admin_dashboard"))

    if request.method == "POST":
        check_in_raw = (request.form.get("check_in") or "").strip()
        notes = (request.form.get("notes") or "").strip()

        check_in = None
        if check_in_raw:
            try:
                check_in = datetime.strptime(check_in_raw, "%Y-%m-%d").date()
            except ValueError:
                flash("Invalid check-in date format.", "danger")
                return redirect(url_for("public.book_room", room_id=room.id))

        # Prevent duplicate pending/approved bookings for same room by same user
        existing = Booking.query.filter(
            Booking.user_id == current_user.id,
            Booking.room_id == room.id,
            Booking.status.in_(["pending", "approved"]),
        ).first()
        if existing:
            flash("You already have an active booking request for this room.", "warning")
            return redirect(url_for("dashboard.student_dashboard"))

        booking = Booking(
            user_id=current_user.id,
            room_id=room.id,
            status="pending",
            check_in=check_in,
            notes=notes or None,
        )
        db.session.add(booking)
        db.session.commit()

        flash("Booking request submitted! Status: Pending approval.", "success")
        return redirect(url_for("dashboard.student_dashboard"))

    return render_template("book.html", room=room)
