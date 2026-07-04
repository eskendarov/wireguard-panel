"""
Thin wrapper around the `wg` / `wg-quick` command line tools.

Design choice: the live kernel WireGuard state and /etc/wireguard/wg0.conf are
always kept in sync via `wg syncconf`, which applies a config file to the
running interface *without* dropping existing peer sessions that are
unaffected by the change (unlike `wg-quick down && up`).

Peer metadata that plain WireGuard has no concept of — human-readable names,
whether a peer is "enabled", and each peer's own private key so we can
regenerate its QR code later — lives in peers.json (see peers_store.py).
peers.json is the source of truth; wg0.conf is regenerated from it on every
change.
"""

import ipaddress
import subprocess

from app.config import Config


def _run(args):
    result = subprocess.run(args, capture_output=True, text=True, check=True)
    return result.stdout


def get_server_public_key():
    if Config.SERVER_PUBLIC_KEY:
        return Config.SERVER_PUBLIC_KEY
    return _run(["wg", "show", Config.WG_INTERFACE, "public-key"]).strip()


def generate_private_key():
    return _run(["wg", "genkey"]).strip()


def derive_public_key(private_key):
    result = subprocess.run(
        ["wg", "pubkey"], input=private_key, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def generate_preshared_key():
    return _run(["wg", "genpsk"]).strip()


def live_dump():
    """
    Parses `wg show <iface> dump` into a dict keyed by public_key with
    live stats: endpoint, latest_handshake, rx/tx bytes.
    """
    try:
        raw = _run(["wg", "show", Config.WG_INTERFACE, "dump"])
    except subprocess.CalledProcessError:
        return {}

    lines = raw.strip().split("\n")
    stats = {}
    # First line is the interface itself — skip it.
    for line in lines[1:]:
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 8:
            continue
        public_key, _psk, endpoint, _allowed_ips, handshake, rx, tx, keepalive = parts
        stats[public_key] = {
            "endpoint": endpoint if endpoint != "(none)" else None,
            "latest_handshake": int(handshake),
            "transfer_rx": int(rx),
            "transfer_tx": int(tx),
            "persistent_keepalive": None if keepalive == "off" else int(keepalive),
        }
    return stats


def next_free_addresses(existing_peers):
    """
    Finds the next unused host address in both the v4 and v6 VPN subnets.
    existing_peers: list of peer dicts already containing address_v4/address_v6.
    """
    net4 = ipaddress.ip_network(Config.VPN_SUBNET_V4, strict=False)
    net6 = ipaddress.ip_network(Config.VPN_SUBNET_V6, strict=False)

    used4 = {p["address_v4"] for p in existing_peers}
    used6 = {p["address_v6"] for p in existing_peers}

    # .1 is reserved for the server itself.
    addr4 = None
    for host in net4.hosts():
        if str(host) == str(net4.network_address + 1):
            continue
        if str(host) not in used4:
            addr4 = str(host)
            break

    addr6 = None
    count = 2  # server = ::1
    for host in net6.hosts():
        if count == 0:
            break
        count -= 1
    for i in range(2, 2 ** 16):
        candidate = str(net6.network_address + i)
        if candidate not in used6:
            addr6 = candidate
            break

    if addr4 is None or addr6 is None:
        raise RuntimeError("No free addresses left in the VPN subnet")

    return addr4, addr6


def _read_interface_block(conf_path):
    """
    Extracts the [Interface] section verbatim from the on-disk conf file,
    so PostUp/PostDown/ListenPort/PrivateKey are preserved untouched.
    """
    with open(conf_path) as f:
        content = f.read()

    lines = content.split("\n")
    interface_lines = []
    in_interface = False
    for line in lines:
        stripped = line.strip()
        if stripped == "[Interface]":
            in_interface = True
            interface_lines.append(line)
            continue
        if stripped.startswith("[Peer]"):
            break
        if in_interface:
            interface_lines.append(line)

    return "\n".join(interface_lines).rstrip() + "\n"


def rewrite_conf(peers):
    """
    Regenerates /etc/wireguard/wg0.conf from peers.json (only enabled peers
    get a [Peer] block) and then live-syncs the running interface to match,
    without dropping unrelated active sessions.
    """
    interface_block = _read_interface_block(Config.WG_CONFIG_PATH)

    blocks = [interface_block]
    for peer in peers:
        if not peer.get("enabled", True):
            continue
        allowed_ips = f"{peer['address_v4']}/32, {peer['address_v6']}/128"
        block = (
            f"\n### Client {peer['name']}\n"
            f"[Peer]\n"
            f"PublicKey = {peer['public_key']}\n"
            f"PresharedKey = {peer['preshared_key']}\n"
            f"AllowedIPs = {allowed_ips}\n"
        )
        blocks.append(block)

    new_content = "".join(blocks)

    with open(Config.WG_CONFIG_PATH, "w") as f:
        f.write(new_content)

    # Apply live without dropping unrelated peers' sessions.
    strip_result = subprocess.run(
        ["wg-quick", "strip", Config.WG_CONFIG_PATH],
        capture_output=True, text=True, check=True,
    )
    subprocess.run(
        ["wg", "syncconf", Config.WG_INTERFACE, "/dev/stdin"],
        input=strip_result.stdout, text=True, check=True,
    )


def build_client_config(peer):
    dns_line = f"DNS = {Config.CLIENT_DNS}\n" if Config.CLIENT_DNS else ""
    return (
        f"[Interface]\n"
        f"PrivateKey = {peer['private_key']}\n"
        f"Address = {peer['address_v4']}/32, {peer['address_v6']}/128\n"
        f"{dns_line}"
        f"\n"
        f"[Peer]\n"
        f"PublicKey = {get_server_public_key()}\n"
        f"PresharedKey = {peer['preshared_key']}\n"
        f"Endpoint = {Config.SERVER_ENDPOINT}\n"
        f"AllowedIPs = 0.0.0.0/0, ::/0\n"
        f"PersistentKeepalive = 25\n"
    )
