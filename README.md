# Clarity OMR USB Appliance

This project builds a bootable USB appliance for an old Acer Aspire 5560 class laptop.

The goal is simple:

1. Boot the Acer from the appliance USB.
2. The computer starts the OMR screen by itself. There is no desktop, no login, and no password prompt.
3. Insert a second USB drive that contains violin sheet-music PDFs.
4. Select one PDF.
5. Press `Start`.
6. The status button is green while ready and red while processing.
7. The result is saved beside the PDF as the same filename with `.musicxml`.
8. The laptop beeps when processing finishes.

## Important Hardware Truth

The Acer Aspire 5560 uses an old AMD A8 generation CPU. That CPU is 64-bit, but it appears to lack AVX instructions. Modern AI software often depends on PyTorch, and modern PyTorch CPU builds often expect AVX-capable hardware.

That means the ISO can boot correctly but Clarity-OMR may still fail on that exact laptop with an `Illegal instruction` type error. That is not a Linux boot problem. It is the AI library trying to use CPU instructions the old processor does not have.

This build still installs Clarity-OMR because that is what was requested, but I do not want to pretend the old A8 CPU is a normal target for current PyTorch-based OMR.

## Accuracy Truth

Clarity-OMR converts PDF sheet music to MusicXML. It may detect notes and some notation details, but no OMR program can honestly guarantee perfect violin bowing, articulations, dynamics, and fingerings from every PDF. If the marks are printed clearly, the result may include more of them. If the marks are tiny, handwritten, faded, or ambiguous, they may be missed and need correction in MuseScore, Dorico, Sibelius, or another notation editor.

## What This Builds

This builds a Debian Live amd64 ISO. Debian Live is used because it can create a bootable ISO/USB image and lets us add packages, files, startup services, and build hooks.

The live system includes:

- Minimal Linux, not a full desktop.
- Xorg only to show the simple graphical screen.
- Python/Tkinter for the appliance UI.
- Clarity-OMR installed under `/opt/Clarity-OMR`.
- A Python virtual environment under `/opt/clarity-venv`.
- Clarity model files downloaded into the ISO during the build.
- USB filesystem support for FAT, exFAT, NTFS, and Linux filesystems.
- AMD graphics firmware and AMD microcode for old AMD laptop hardware.

## USB Drives

You need two USB drives.

- USB 1: the bootable appliance USB. This is made from the ISO.
- USB 2: the music USB. Put your PDFs on this drive. The MusicXML output is saved back to this same drive.

Do not put your only copy of important PDFs on a USB drive you are about to erase.

## Fastest Way To Get An ISO

This Mac is ARM-based and does not have the Linux live-build tools installed, so I cannot truthfully hand you a locally built, boot-tested amd64 ISO from this machine.

The project includes a GitHub Actions workflow that can build the ISO on an x86_64 Linux runner:

1. Push this folder to a GitHub repository.
2. Open the repository on GitHub.
3. Go to `Actions`.
4. Run `Build Clarity OMR Appliance ISO`.
5. Download the artifact named `clarity-omr-appliance-iso`.
6. Inside it you will find `clarity-omr-appliance-amd64.iso` and a SHA256 checksum.

The build can take a long time because it downloads Debian packages, PyTorch, Clarity-OMR dependencies, and the model files.

## Build Locally On Linux

Use a Debian or Ubuntu x86_64 computer or virtual machine. Do not use the old Acer for building. The build is too heavy for that.

Install the build tools:

```bash
sudo apt update
sudo apt install -y live-build xorriso squashfs-tools debootstrap syslinux-common syslinux-utils isolinux grub-pc-bin grub-efi-amd64-bin mtools dosfstools
```

Build the ISO:

```bash
./scripts/build-iso-linux.sh
```

When it finishes, the ISO should be here:

```text
live-build/clarity-omr-appliance-amd64.iso
```

## Write The ISO To A USB On macOS

First plug in the USB drive that will become the bootable appliance drive. This will erase that USB drive.

Find the disk name:

```bash
diskutil list
```

If the USB is `disk4`, write the ISO like this:

```bash
./scripts/write-usb-macos.sh live-build/clarity-omr-appliance-amd64.iso disk4
```

Replace `disk4` with the real disk number for your USB drive.

## Boot The Acer

1. Plug the appliance USB into the Acer.
2. Turn the Acer on.
3. Press `F2` to enter BIOS if needed.
4. Enable the `F12 Boot Menu` if it is disabled.
5. Save and restart.
6. Press `F12`.
7. Pick the USB drive.
8. Wait for the appliance screen.
9. Insert the second USB drive with your PDFs.
10. Select a PDF and press `Start`.

## If It Fails

If the UI says PyTorch crashed or Clarity failed, check the log file on the music USB. For a PDF named `piece.pdf`, the log is:

```text
piece.clarity.log
```

If the log mentions `Illegal instruction`, the old AMD CPU is the problem. The practical options are:

- Build a no-AVX PyTorch from source, which is difficult and slow.
- Use a newer laptop or desktop for Clarity-OMR.
- Use a Java-based OMR tool such as Audiveris on the old Acer instead of Clarity-OMR.

## Project Layout

```text
live-build/
  auto/
    config
    build
    clean
  config/
    hooks/live/
      010-install-clarity.hook.chroot
      020-configure-system.hook.chroot
    includes.chroot/
      opt/clarity-appliance/app/clarity_appliance.py
      usr/local/bin/clarity-appliance-session
      etc/systemd/system/clarity-appliance.service
    package-lists/
      clarity-appliance.list.chroot
scripts/
  build-iso-linux.sh
  write-usb-macos.sh
  write-usb-linux.sh
.github/workflows/
  build-iso.yml
```
