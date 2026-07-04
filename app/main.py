import io
import functools

import qrcode
from flask import Flask, jsonify, request, session, send_file, render_template
from werkzeug.security import generate_password_hash, check_password_hash

from app.config import Config
from app import wg
from app import peers_store

app = Flask(__name__, template_folder="../static", static_folder="../static")
app.secret_key = Config.FLASK_SECRET_KEY

_admin_hash = generate_password_hash(Config.ADMIN_PASSWORD) if Config.ADMIN_PASSWORD else None


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("authed"):
            return jsonify({"error": "unauthorized"}), 401
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    password = data.get("password", "")
    if _admin_hash and check_password_hash(_admin_hash, password):
        session["authed"] = True
        return jsonify({"ok": True})
    return jsonify({"error": "invalid password"}), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/peers", methods=["GET"])
@login_required
def list_peers():
    peers = peers_store.load_peers()
    live = wg.live_dump()
    result = []
    for peer in peers:
        entry = dict(peer)
        entry.pop("private_key", None)  # never ship the private key over the wire
        stats = live.get(peer["public_key"], {})
        entry["online"] = bool(stats.get("latest_handshake")) and stats["latest_handshake"] > 0
        entry["endpoint"] = stats.get("endpoint")
        entry["latest_handshake"] = stats.get("latest_handshake")
        entry["transfer_rx"] = stats.get("transfer_rx", 0)
        entry["transfer_tx"] = stats.get("transfer_tx", 0)
        result.append(entry)
    return jsonify(result)


@app.route("/api/peers", methods=["POST"])
@login_required
def create_peer():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    existing = peers_store.load_peers()
    address_v4, address_v6 = wg.next_free_addresses(existing)

    private_key = wg.generate_private_key()
    public_key = wg.derive_public_key(private_key)
    preshared_key = wg.generate_preshared_key()

    peer = peers_store.add_peer(
        name=name,
        public_key=public_key,
        private_key=private_key,
        preshared_key=preshared_key,
        address_v4=address_v4,
        address_v6=address_v6,
    )

    wg.rewrite_conf(peers_store.load_peers())

    response = dict(peer)
    response.pop("private_key", None)
    return jsonify(response), 201


@app.route("/api/peers/<peer_id>", methods=["DELETE"])
@login_required
def remove_peer(peer_id):
    if not peers_store.get_peer(peer_id):
        return jsonify({"error": "not found"}), 404
    remaining = peers_store.delete_peer(peer_id)
    wg.rewrite_conf(remaining)
    return jsonify({"ok": True})


@app.route("/api/peers/<peer_id>/toggle", methods=["POST"])
@login_required
def toggle_peer(peer_id):
    peer = peers_store.get_peer(peer_id)
    if not peer:
        return jsonify({"error": "not found"}), 404
    peers = peers_store.set_enabled(peer_id, not peer["enabled"])
    wg.rewrite_conf(peers)
    return jsonify({"ok": True})


@app.route("/api/peers/<peer_id>/config", methods=["GET"])
@login_required
def download_config(peer_id):
    peer = peers_store.get_peer(peer_id)
    if not peer:
        return jsonify({"error": "not found"}), 404
    config_text = wg.build_client_config(peer)
    buffer = io.BytesIO(config_text.encode())
    return send_file(
        buffer,
        mimetype="text/plain",
        as_attachment=True,
        download_name=f"{peer['name']}.conf",
    )


@app.route("/api/peers/<peer_id>/qr", methods=["GET"])
@login_required
def peer_qr(peer_id):
    peer = peers_store.get_peer(peer_id)
    if not peer:
        return jsonify({"error": "not found"}), 404
    config_text = wg.build_client_config(peer)
    img = qrcode.make(config_text)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8787)
