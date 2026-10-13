"""
UrbanStay Hostel Management System — Flask application entry point.
"""

import os

from flask import Flask

from extensions import db, login_manager
from models import User, Room  # noqa: F401 — register models with SQLAlchemy


def create_app() -> Flask:
    base_dir = os.path.abspath(os.path.dirname(__file__))
    instance_path = os.path.join(base_dir, "instance")
    os.makedirs(instance_path, exist_ok=True)

    app = Flask(
        __name__,
        instance_path=instance_path,
        template_folder="templates",
        static_folder="static",
    )

    db_path = os.path.join(instance_path, "hostel.db").replace("\\", "/")
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "urbanstay-dev-secret-change-in-production"),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", f"sqlite:///{db_path}"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # Secret code required when registering as admin
        ADMIN_SECRET_CODE=os.environ.get("ADMIN_SECRET_CODE", "URBANSTAY-ADMIN-2026"),
    )

    db.init_app(app)
    login_manager.init_app(app)

    from routes.public import public_bp
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")

    with app.app_context():
        db.create_all()
        _seed_rooms()
        _seed_default_admin()

    return app


def _seed_rooms() -> None:
    """Seed sample rooms matching the original frontend cards (once)."""
    if Room.query.count() > 0:
        return

    samples = [
        Room(
            room_number="A101",
            room_type="Premium Single Suite",
            price_monthly=10000,
            capacity=1,
            description="Perfect for ultimate privacy and focused study sessions.",
            image_url="bed.jpg",
            is_available=True,
        ),
        Room(
            room_number="B201",
            room_type="Deluxe Twin Sharing",
            price_monthly=8500,
            capacity=2,
            description="Share with a friend without compromising your personal space.",
            image_url="bed1.jpg",
            is_available=True,
        ),
        Room(
            room_number="C301",
            room_type="Classic Quad Shared",
            price_monthly=7500,
            capacity=4,
            description="Affordable, economic choice packed with community vibes.",
            image_url="bed2.jpg",
            is_available=True,
        ),
        Room(
            room_number="A102",
            room_type="Premium Single Suite",
            price_monthly=10000,
            capacity=1,
            description="Quiet single room with study desk and wardrobe.",
            image_url="bed.jpg",
            is_available=True,
        ),
        Room(
            room_number="B202",
            room_type="Deluxe Twin Sharing",
            price_monthly=8500,
            capacity=2,
            description="Twin sharing with attached balcony.",
            image_url="bed1.jpg",
            is_available=True,
        ),
    ]
    db.session.add_all(samples)
    db.session.commit()


def _seed_default_admin() -> None:
    """Create a default admin if none exists."""
    if User.query.filter_by(role="admin").first():
        return

    admin = User(
        full_name="System Admin",
        email="admin@urbanstay.com",
        phone="9999955555",
        role="admin",
    )
    admin.set_password("admin123")
    db.session.add(admin)
    db.session.commit()


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
