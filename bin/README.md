# Native Binaries for phf-stream-pi

This directory holds the pre-compiled `libphf.so` for Linux ARM64 (aarch64) Raspberry Pi devices.

## Building `libphf.so` on Raspberry Pi 4 / 5

From the sibling `phf` repository:

```bash
cd ../phf
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
cp build/libphf.so ../phf-stream-pi/bin/
```

Or directly via GCC:

```bash
gcc -O3 -march=armv8-a -fopenmp -fPIC -shared \
    -o bin/libphf.so \
    ../phf/libphf/src/phf.c ../phf/libphf/src/huff.c \
    -I ../phf/libphf/include
```
