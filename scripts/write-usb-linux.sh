#!/bin/sh
set -e

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 /path/to/clarity-omr-appliance-amd64.iso /dev/sdX"
  echo "Example: $0 live-build/clarity-omr-appliance-amd64.iso /dev/sdb"
  exit 1
fi

ISO_PATH="$1"
DEVICE="$2"

if [ ! -f "${ISO_PATH}" ]; then
  echo "ISO not found: ${ISO_PATH}"
  exit 1
fi

case "${DEVICE}" in
  /dev/sd? | /dev/nvme?n? | /dev/mmcblk?)
    ;;
  *)
    echo "Use a whole disk device like /dev/sdb, not a partition like /dev/sdb1."
    exit 1
    ;;
esac

echo "This will erase ${DEVICE}."
echo "Press Ctrl-C now if this is the wrong disk."
sleep 8

sudo umount "${DEVICE}"* 2>/dev/null || true
sudo dd if="${ISO_PATH}" of="${DEVICE}" bs=4M status=progress conv=fsync
sync

echo "Done. The USB can now boot the Acer."

