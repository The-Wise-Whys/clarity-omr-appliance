#!/bin/sh
set -e

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BUILD_DIR="${ROOT_DIR}/live-build"

if ! command -v lb >/dev/null 2>&1; then
  echo "The live-build tool is missing."
  echo "Install it with: sudo apt install live-build xorriso squashfs-tools debootstrap syslinux-common isolinux grub-pc-bin grub-efi-amd64-bin mtools dosfstools"
  exit 1
fi

cd "${BUILD_DIR}"

sudo lb clean --purge || true
sudo lb config
sudo lb build

if [ -f "${BUILD_DIR}/clarity-omr-appliance-amd64.hybrid.iso" ]; then
  mv "${BUILD_DIR}/clarity-omr-appliance-amd64.hybrid.iso" "${BUILD_DIR}/clarity-omr-appliance-amd64.iso"
elif [ -f "${BUILD_DIR}/live-image-amd64.hybrid.iso" ]; then
  mv "${BUILD_DIR}/live-image-amd64.hybrid.iso" "${BUILD_DIR}/clarity-omr-appliance-amd64.iso"
fi

if [ ! -f "${BUILD_DIR}/clarity-omr-appliance-amd64.iso" ]; then
  echo "Build ended, but the ISO was not found."
  exit 1
fi

sha256sum "${BUILD_DIR}/clarity-omr-appliance-amd64.iso" > "${BUILD_DIR}/clarity-omr-appliance-amd64.iso.sha256"
echo "Built: ${BUILD_DIR}/clarity-omr-appliance-amd64.iso"
echo "Checksum: ${BUILD_DIR}/clarity-omr-appliance-amd64.iso.sha256"
