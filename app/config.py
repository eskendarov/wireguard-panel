import os
import secrets
from dotenv import load_dotenv

load_dotenv()


class Config:
    WG_INTERFACE = os.getenv("WG_INTERFACE", "wg0")
    WG_CONFIG_PATH = os.getenv("WG_CONFIG_PATH", "/etc/wireguard/wg0.conf")
    SERVER_PUBLIC_KEY = os.getenv("SERVER_PUBLIC_KEY", "")
    SERVER_ENDPOINT = os.getenv("SERVER_ENDPOINT", "")
    VPN_SUBNET_V4 = os.getenv("VPN_SUBNET_V4", "10.8.0.0/24")
    VPN_SUBNET_V6 = os.getenv("VPN_SUBNET_V6", "fd42:42:42::/64")
    CLIENT_DNS = os.getenv("CLIENT_DNS", "1.1.1.1,8.8.8.8")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
    PEERS_STORE_PATH = os.getenv("PEERS_STORE_PATH", "config/peers.json")
