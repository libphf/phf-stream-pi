# phf-stream-pi 🍓

Ultra-low latency, **100% bit-exact lossless** camera streaming server designed natively for the **Raspberry Pi**, powered by the **Pure High-Fidelity Format (PHF)**.

Streams live frames from **MIPI CSI ribbon-cable cameras** (such as the Raspberry Pi Camera Module v1 OV5647, v2 IMX219, HQ Camera IMX477, v3 IMX708) and **USB webcams** to any modern web browser decoding in real time with WebAssembly (`phf.wasm` SIMD128).

---

## Features

- **Native CSI Ribbon Cable Support**: Interfaces with the hardware ISP and Unicam driver via `Picamera2` (official libcamera stack).
- **USB Webcam Support**: Auto-detects and streams from connected USB UVC cameras alongside CSI modules.
- **Unified Camera Selector**: Web dashboard automatically discovers and labels all connected cameras (`[CSI Fita]` vs `[USB]`), allowing hot-switching without restarting the server.
- **Bit-Exact Lossless Video**: No JPEG artifacts, no chroma subsampling (full 4:4:4 RGB), no loss of detail.
- **Hardware-Accelerated Codec**: Uses `libphf` with ARM64 NEON SIMD optimization and OpenMP multi-threading.
- **Zero WebSocket Compression Overhead**: Uncompressed binary transport (`compression=None`) to eliminate event loop latency.
- **In-Browser WebAssembly Decoder**: Minimal client footprint decoding directly into HTML5 `<canvas>` via `phf.wasm`.

---

## Architecture

```
┌─────────────────────────────────┐
│     Raspberry Pi (Server)       │
│                                 │
│  [CSI Camera]      [USB Webcam] │
│        │                 │      │
│        ▼                 ▼      │
│     Picamera2 / libcamera       │
│        │                        │
│        ▼ (RGB in-memory array)  │
│   libphf.so (ARM64 NEON)        │
│        │ (Lossless .phf)        │
│        ▼                        │
│   WebSocket Server (:8765)      │
└────────────────┬────────────────┘
                 │ (LAN / Wi-Fi)
                 ▼
┌─────────────────────────────────┐
│     Web Client (Browser)        │
│                                 │
│      phf.wasm (SIMD128)         │
│               │                 │
│               ▼                 │
│      HTML5 <canvas>             │
└─────────────────────────────────┘
```

---

## Quick Start on Raspberry Pi

### 1. Requirements

Install standard system packages:
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-numpy python3-websockets python3-picamera2 cmake libomp-dev
```

### 2. Native Library Compilation (`libphf.so`)

Compile the ARM64 optimized `libphf.so` with NEON and OpenMP:
```bash
cd phf
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
cp build/libphf.so ../phf-stream-pi/bin/
```

### 3. Run the Server

```bash
cd phf-stream-pi
python3 run.py --host 0.0.0.0 --http-port 8000 --ws-port 8765
```

Open `http://<IP_DO_RASPBERRY_PI>:8000` on any device on your local network (computer, tablet, phone, Pixelbook).

---

## Technical Details

- **Binary Packet Protocol**:
  - `0x01` Video: 8-byte capture timestamp (f64 LE) + 4-byte encode duration (f32 LE) + raw PHF container bytes.
  - `0x02` Audio: 16-bit mono PCM @ 44.1 kHz (optional).
  - `0x03` JSON: Control events (device enumeration, resolution switching, FPS reports).
- **Default Resolution**: 640x480 (VGA) recommended for smooth 30 fps streaming on Raspberry Pi 4 Model B.

---

## License

MIT License. Authored and maintained by `libphf <libphf@gmail.com>`.
