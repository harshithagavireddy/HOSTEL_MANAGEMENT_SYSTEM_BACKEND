"""Student and admin dashboards with role-based access."""

from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models import Booking, Complaint, Enquiry, Room, User

dashboard_bp = Blueprint("dashboard", __name__)


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            flash("Admin access required.", "danger")
            return redirect(url_for("dashboard.student_dashboard"))
        return view(*args, **kwargs)

    return wrapped


def student_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.is_admin:
            return redirect(url_for("dashboard.admin_dashboard"))
        return view(*args, **kwargs)

    return wrapped


# ---------------------------------------------------------------------------
# Student dashboard
# ---------------------------------------------------------------------------


@dashboard_bp.route("/")
@login_required
def home():
    if current_user.is_admin:
        return redirect(url_for("dashboard.admin_dashboard"))
    return redirect(url_for("dashboard.student_dashboard"))


@dashboard_bp.route("/student")
@student_required
def student_dashboard():
    bookings = (
        Booking.query.filter_by(user_id=current_user.id)
        .order_by(Booking.created_at.desc())
        .all()
    )
    complaints = (
        Complaint.query.filter_by(user_id=current_user.id)
        .order_by(Complaint.created_at.desc())
        .all()
    )
    return render_template(
        "dashboard/student.html",
        bookings=bookings,
        complaints=complaints,
        user=current_user,
    )


@dashboard_bp.route("/student/profile", methods=["POST"])
@student_required
def update_profile():
    full_name = (request.form.get("full_name") or "").strip()
    phone = (request.form.get("phone") or "").strip()

    if not full_name:
        flash("Full name is required.", "danger")
        return redirect(url_for("dashboard.student_dashboard") + "#profile")

    current_user.full_name = full_name
    current_user.phone = phone or None
    db.session.commit()
    flash("Profile updated successfully.", "success")
    return redirect(url_for("dashboard.student_dashboard") + "#profile")


@dashboard_bp.route("/student/complaint", methods=["POST"])
@student_required
def submit_complaint():
    subject = (request.form.get("subject") or "").strip()
    message = (request.form.get("message") or "").strip()

    if not subject or not message:
        flash("Subject and message are required for a complaint.", "danger")
        return redirect(url_for("dashboard.student_dashboard") + "#complaints")

    complaint = Complaint(
        user_id=current_user.id,
        subject=subject,
        message=message,
        status="open",
    )
    db.session.add(complaint)
    db.session.commit()
    flash("Complaint submitted. We will review it shortly.", "success")
    return redirect(url_for("dashboard.student_dashboard") + "#complaints")


@dashboard_bp.route("/student/booking/<int:booking_id>/cancel", methods=["POST"])
@student_required
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        abort(403)

    if booking.status not in ("pending", "approved"):
        flash("This booking cannot be cancelled.", "warning")
        return redirect(url_for("dashboard.student_dashboard"))

    booking.status = "cancelled"
    # Free the room if it was approved
    if booking.room and not booking.room.is_available:
        # Only free if no other approved booking holds this room
        other = Booking.query.filter(
            Booking.room_id == booking.room_id,
            Booking.id != booking.id,
            Booking.status == "approved",
        ).first()
        if not other:
            booking.room.is_available = True

    db.session.commit()
    flash("Booking cancelled.", "info")
    return redirect(url_for("dashboard.student_dashboard"))


# ---------------------------------------------------------------------------
# Admin dashboard
# ---------------------------------------------------------------------------


@dashboard_bp.route("/admin")
@admin_required
def admin_dashboard():
    rooms = Room.query.order_by(Room.room_number).all()
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    enquiries = Enquiry.query.order_by(Enquiry.created_at.desc()).all()
    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    students = User.query.filter_by(role="student").order_by(User.created_at.desc()).all()

    stats = {
        "rooms": len(rooms),
        "available_rooms": sum(1 for r in rooms if r.is_available),
        "bookings": len(bookings),
        "pending_bookings": sum(1 for b in bookings if b.status == "pending"),
        "enquiries": len(enquiries),
        "unread_enquiries": sum(1 for e in enquiries if not e.is_read),
        "complaints": len(complaints),
        "open_complaints": sum(1 for c in complaints if c.status != "resolved"),
        "students": len(students),
    }

    return render_template(
        "dashboard/admin.html",
        rooms=rooms,
        bookings=bookings,
        enquiries=enquiries,
        complaints=complaints,
        students=students,
        stats=stats,
    )


@dashboard_bp.route("/admin/rooms/add", methods=["POST"])
@admin_required
def add_room():
    room_number = (request.form.get("room_number") or "").strip()
    room_type = (request.form.get("room_type") or "").strip()
    price_raw = (request.form.get("price_monthly") or "").strip()
    capacity_raw = (request.form.get("capacity") or "1").strip()
    description = (request.form.get("description") or "").strip()
    image_url = (request.form.get("image_url") or "bed.jpg").strip()

    if not room_number or not room_type or not price_raw:
        flash("Room number, type, and price are required.", "danger")
        return redirect(url_for("dashboard.admin_dashboard") + "#rooms")

    if Room.query.filter_by(room_number=room_number).first():
        flash("A room with that number already exists.", "danger")
        return redirect(url_for("dashboard.admin_dashboard") + "#rooms")

    try:
        price = float(price_raw)
        capacity = int(capacity_raw)
    except ValueError:
        flash("Invalid price or capacity.", "danger")
        return redirect(url_for("dashboard.admin_dashboard") + "#rooms")

    room = Room(
        room_number=room_number,
        room_type=room_type,
        price_monthly=price,
        capacity=capacity,
        description=description or None,
        image_url=image_url or "bed.jpg",
        is_available=True,
    )
    db.session.add(room)
    db.session.commit()
    flash(f"Room {room_number} added.", "success")
    return redirect(url_for("dashboard.admin_dashboard") + "#rooms")


@dashboard_bp.route("/admin/rooms/<int:room_id>/toggle", methods=["POST"])
@admin_required
def toggle_room(room_id):
    room = Room.query.get_or_404(room_id)
    room.is_available = not room.is_available
    db.session.commit()
    state = "available" if room.is_available else "unavailable"
    flash(f"Room {room.room_number} marked as {state}.", "info")
    return redirect(url_for("dashboard.admin_dashboard") + "#rooms")


@dashboard_bp.route("/admin/rooms/<int:room_id>/delete", methods=["POST"])
@admin_required
def delete_room(room_id):
    room = Room.query.get_or_404(room_id)
    active = Booking.query.filter(
        Booking.room_id == room.id,
        Booking.status.in_(["pending", "approved"]),
    ).first()
    if active:
        flash("Cannot delete a room with active bookings. Cancel/reject them first.", "danger")
        return redirect(url_for("dashboard.admin_dashboard") + "#rooms")

    db.session.delete(room)
    db.session.commit()
    flash("Room deleted.", "info")
    return redirect(url_for("dashboard.admin_dashboard") + "#rooms")


@dashboard_bp.route("/admin/bookings/<int:booking_id>/status", methods=["POST"])
@admin_required
def update_booking_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    new_status = (request.form.get("status") or "").strip().lower()

    if new_status not in ("pending", "approved", "rejected", "cancelled"):
        flash("Invalid booking status.", "danger")
        return redirect(url_for("dashboard.admin_dashboard") + "#bookings")

    booking.status = new_status

    if new_status == "approved" and booking.room:
        booking.room.is_available = False
    elif new_status in ("rejected", "cancelled") and booking.room:
        other = Booking.query.filter(
            Booking.room_id == booking.room_id,
            Booking.id != booking.id,
            Booking.status == "approved",
        ).first()
        if not other:
            booking.room.is_available = True

    db.session.commit()
    flash(f"Booking #{booking.id} marked as {new_status}.", "success")
    return redirect(url_for("dashboard.admin_dashboard") + "#bookings")


@dashboard_bp.route("/admin/enquiries/<int:enquiry_id>/read", methods=["POST"])
@admin_required
def mark_enquiry_read(enquiry_id):
    enquiry = Enquiry.query.get_or_404(enquiry_id)
    enquiry.is_read = True
    db.session.commit()
    flash("Enquiry marked as read.", "info")
    return redirect(url_for("dashboard.admin_dashboard") + "#enquiries")


@dashboard_bp.route("/admin/enquiries/<int:enquiry_id>/delete", methods=["POST"])
@admin_required
def delete_enquiry(enquiry_id):
    enquiry = Enquiry.query.get_or_404(enquiry_id)
    db.session.delete(enquiry)
    db.session.commit()
    flash("Enquiry deleted.", "info")
    return redirect(url_for("dashboard.admin_dashboard") + "#enquiries")


@dashboard_bp.route("/admin/complaints/<int:complaint_id>/status", methods=["POST"])
@admin_required
def update_complaint_status(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    new_status = (request.form.get("status") or "").strip().lower()
    admin_response = (request.form.get("admin_response") or "").strip()

    if new_status not in ("open", "in_progress", "resolved"):
        flash("Invalid complaint status.", "danger")
        return redirect(url_for("dashboard.admin_dashboard") + "#complaints")

    complaint.status = new_status
    if admin_response:
        complaint.admin_response = admin_response
    db.session.commit()
    flash(f"Complaint #{complaint.id} updated.", "success")
    return redirect(url_for("dashboard.admin_dashboard") + "#complaints")
