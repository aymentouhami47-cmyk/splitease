"""SplitEase Flask application factory.

Run with:   python -m flask --app app run
"""
import os
import threading

from flask import Flask, g, jsonify, request

from . import db

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app(db_path=None):
    """db_path=":memory:" gives a throw-away database (used by the tests)."""
    app = Flask(
        __name__,
        static_folder=os.path.join(ROOT, "static"),
        static_url_path="",
    )
    path = db_path or os.environ.get("SPLITEASE_DB", os.path.join(ROOT, "splitease.db"))
    app.config["DB_PATH"] = path
    app.extensions["conn"] = db.connect(path)

    # One shared SQLite connection, so handle one request at a time.
    lock = threading.Lock()

    @app.before_request
    def _acquire_lock():
        lock.acquire()
        g.lock_held = True

    @app.teardown_request
    def _release_lock(_exc):
        if g.pop("lock_held", False):
            lock.release()

    from .routes import api

    app.register_blueprint(api)

    @app.route("/")
    def index():
        return app.send_static_file("index.html")

    @app.errorhandler(404)
    def _not_found(_error):
        if request.path.startswith("/api"):
            return jsonify({"error": "not found"}), 404
        return "Not found", 404

    @app.errorhandler(405)
    def _method_not_allowed(_error):
        if request.path.startswith("/api"):
            return jsonify({"error": "method not allowed"}), 405
        return "Method not allowed", 405

    return app
