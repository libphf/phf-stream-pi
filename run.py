#!/usr/bin/env python3
"""
PHF Stream Pi - Native Camera Streaming Server for Raspberry Pi.
Streams CSI ribbon cable cameras (Picamera2 / libcamera) and USB webcams
using lossless Pereira-Huffman Format (PHF) over WebSockets.
"""

import os
import sys
import argparse
import asyncio

# Ensure safe output on consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add server directory to module search path
server_dir = os.path.join(os.path.dirname(__file__), "server")
sys.path.insert(0, server_dir)

from stream_server import PiStreamServer

def main():
    parser = argparse.ArgumentParser(description="PHF Stream Pi (Raspberry Pi Camera Streaming Server)")
    parser.add_argument("--host", default="0.0.0.0",
                        help="Interface to listen on (default: 0.0.0.0 for LAN access)")
    parser.add_argument("--http-port", type=int, default=8000, help="HTTP dashboard port (default: 8000)")
    parser.add_argument("--ws-port", type=int, default=8765, help="WebSocket streaming port (default: 8765)")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    web_dir = os.path.join(base_dir, "web")

    server = PiStreamServer(
        web_dir=web_dir,
        host=args.host,
        http_port=args.http_port,
        ws_port=args.ws_port
    )

    print("=" * 65)
    print("  🍓 PHF Stream Pi - Raspberry Pi Camera Streaming Server")
    print("=" * 65)
    print(f"  👉 Web Dashboard:    http://{args.host}:{args.http_port}")
    print(f"  👉 WebSocket Stream:  ws://{args.host}:{args.ws_port}")
    print("  📷 Sources:           CSI Ribbon Cameras (Picamera2) & USB Webcams")
    print("=" * 65)
    print("Pressione Ctrl+C para encerrar o servidor.")

    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        print("\n[Server] Encerrando...")
    finally:
        server.stop()

if __name__ == "__main__":
    main()
