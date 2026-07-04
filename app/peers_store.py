import json
import os
import uuid
from datetime import datetime, timezone
from threading import Lock

from app.config import Config

_lock = Lock()


def _ensure_store():
    os.makedirs(os.path.dirname(Config.PEERS_STORE_PATH) or ".", exist_ok=True)
    if not os.path.exists(Config.PEERS_STORE_PATH):
        with open(Config.PEERS_STORE_PATH, "w") as f:
            json.dump({"peers": []}, f, indent=2)


def load_peers():
    _ensure_store()
    with open(Config.PEERS_STORE_PATH) as f:
        return json.load(f)["peers"]


def save_peers(peers):
    with open(Config.PEERS_STORE_PATH, "w") as f:
        json.dump({"peers": peers}, f, indent=2)


def add_peer(name, public_key, private_key, preshared_key, address_v4, address_v6):
    with _lock:
        peers = load_peers()
        peer = {
            "id": str(uuid.uuid4()),
            "name": name,
            "public_key": public_key,
            "private_key": private_key,
            "preshared_key": preshared_key,
            "address_v4": address_v4,
            "address_v6": address_v6,
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        peers.append(peer)
        save_peers(peers)
        return peer


def get_peer(peer_id):
    for peer in load_peers():
        if peer["id"] == peer_id:
            return peer
    return None


def delete_peer(peer_id):
    with _lock:
        peers = load_peers()
        peers = [p for p in peers if p["id"] != peer_id]
        save_peers(peers)
        return peers


def set_enabled(peer_id, enabled):
    with _lock:
        peers = load_peers()
        for peer in peers:
            if peer["id"] == peer_id:
                peer["enabled"] = enabled
        save_peers(peers)
        return peers
