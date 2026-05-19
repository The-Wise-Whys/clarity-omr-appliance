#!/bin/sh
set -e

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 /path/to/clarity-omr-appliance-amd64.iso diskN"
  echo "Example: $0 live-build/clarity-omr-appliance-amd64.iso disk4"
  exit 1
fi

ISO_PATH="$1"
DISK_NAME="$2"

case "${DISK_NAME}" in
  disk[0-9]*)
    ;;
  *)
    echo "Use a disk name like disk4, not ${DISK_NAME}."
    echo "Run diskutil list to find the USB disk."
    exit 1
    ;;
esac

if [ ! -f "${ISO_PATH}" ]; then
  echo "ISO not found: ${ISO_PATH}"
  exit 1
fi

echo "This will erase /dev/${DISK_NAME}."
echo "Press Ctrl-C now if this is the wrong disk."
sleep 8

diskutil unmountDisk "/dev/${DISK_NAME}"
sudo dd if="${ISO_PATH}" of="/dev/r${DISK_NAME}" bs=4m conv=sync
sync
diskutil eject "/dev/${DISK_NAME}"

echo "Done. The USB can now boot the Acer."

