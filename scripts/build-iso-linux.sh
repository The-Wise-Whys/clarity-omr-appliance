#!/bin/sh
set -e

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BUILD_DIR="${ROOT_DIR}/live-build"

if ! command -v lb >/dev/null 2>&1; then
  echo "The live-build tool is missing."
  echo "Install it with: sudo apt install live-build xorriso squashfs-tools debootstrap syslinux-common syslinux-utils syslinux isolinux grub-pc-bin grub-efi-amd64-bin mtools dosfstools"
  exit 1
fi

cd "${BUILD_DIR}"

sudo lb clean noauto --purge || true
sudo sed -i 's|/Contents-|/main/Contents-|g' /usr/lib/live/build/lb_chroot_linux-image
sudo grep -R "/root/isolinux" -n /usr/lib/live/build /usr/share/live/build 2>/dev/null || true
sudo find /usr/lib/live/build /usr/share/live/build -type f -exec sed -i \
  -e 's|/root/isolinux/isolinux.bin|/usr/lib/ISOLINUX/isolinux.bin|g' \
  -e 's|/root/isolinux/vesamenu.c32|/usr/lib/syslinux/modules/bios/vesamenu.c32|g' \
  -e 's|/root/isolinux/menu.c32|/usr/lib/syslinux/modules/bios/menu.c32|g' \
  -e 's|/root/isolinux/ldlinux.c32|/usr/lib/syslinux/modules/bios/ldlinux.c32|g' \
  -e 's|/root/isolinux/libcom32.c32|/usr/lib/syslinux/modules/bios/libcom32.c32|g' \
  -e 's|/root/isolinux/libutil.c32|/usr/lib/syslinux/modules/bios/libutil.c32|g' \
  {} +
sudo grep -R "/root/isolinux" -n /usr/lib/live/build /usr/share/live/build 2>/dev/null || true
sudo lb config noauto
sudo mkdir -p /root/isolinux
sudo cp -L /usr/lib/ISOLINUX/isolinux.bin /root/isolinux/isolinux.bin
sudo cp -L /usr/lib/syslinux/modules/bios/vesamenu.c32 /root/isolinux/vesamenu.c32
sudo cp -L /usr/lib/syslinux/modules/bios/ldlinux.c32 /root/isolinux/ldlinux.c32
sudo cp -L /usr/lib/syslinux/modules/bios/libcom32.c32 /root/isolinux/libcom32.c32
sudo cp -L /usr/lib/syslinux/modules/bios/libutil.c32 /root/isolinux/libutil.c32
sudo cp -L /usr/lib/syslinux/modules/bios/menu.c32 /root/isolinux/menu.c32
sudo lb build noauto

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
