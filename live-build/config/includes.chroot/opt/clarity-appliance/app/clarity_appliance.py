#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import re
import shutil
import signal
import struct
import subprocess
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, Y, Button, Frame, Label, Listbox, Scrollbar, Tk


CLARITY_ROOT = Path(os.environ.get("CLARITY_ROOT", "/opt/Clarity-OMR"))
CLARITY_PYTHON = Path(os.environ.get("CLARITY_PYTHON", "/opt/clarity-venv/bin/python"))
MOUNT_BASE = Path(os.environ.get("CLARITY_MOUNT_BASE", "/media/clarity-usb"))
PDF_DPI = int(os.environ.get("CLARITY_PDF_DPI", "200"))
THREADS = os.environ.get("CLARITY_THREADS", "2")
FAST_MODE = os.environ.get("CLARITY_FAST", "1").lower() not in {"0", "false", "no"}

LIVE_MOUNT_MARKERS = (
    "/run/live",
    "/lib/live/mount",
    "/usr/lib/live/mount",
)

SKIP_DIR_NAMES = {
    ".clarity-work",
    ".spotlight-v100",
    ".trashes",
    ".trash",
    "system volume information",
    "$recycle.bin",
}


@dataclass(frozen=True)
class PdfChoice:
    path: Path
    usb_root: Path


def run_command(command: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._") or "usb"


def read_cpu_flags() -> set[str]:
    try:
        text = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return set()
    flags: set[str] = set()
    for line in text.splitlines():
        if line.lower().startswith("flags"):
            _, _, raw_flags = line.partition(":")
            flags.update(raw_flags.strip().split())
    return flags


def mountpoints_from_node(node: dict) -> list[str]:
    raw = node.get("mountpoints")
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    if isinstance(raw, str) and raw:
        return [raw]
    raw = node.get("mountpoint")
    if isinstance(raw, str) and raw:
        return [raw]
    return []


def flatten_lsblk(node: dict, parent_tran: str | None = None, parent_rm: bool = False) -> list[dict]:
    current = dict(node)
    current["_effective_tran"] = node.get("tran") or parent_tran
    current["_effective_rm"] = bool(node.get("rm")) or parent_rm

    rows = [current]
    for child in node.get("children") or []:
        rows.extend(flatten_lsblk(child, current["_effective_tran"], current["_effective_rm"]))
    return rows


def list_block_devices() -> list[dict]:
    command = [
        "lsblk",
        "-J",
        "-p",
        "-o",
        "NAME,PATH,TYPE,TRAN,RM,MOUNTPOINTS,FSTYPE,LABEL,SIZE,MODEL",
    ]
    result = run_command(command)
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    rows: list[dict] = []
    for node in data.get("blockdevices", []):
        rows.extend(flatten_lsblk(node))
    return rows


def is_live_medium(node: dict) -> bool:
    fstype = str(node.get("fstype") or "").lower()
    if fstype in {"iso9660", "squashfs"}:
        return True
    for mountpoint in mountpoints_from_node(node):
        if any(mountpoint.startswith(marker) for marker in LIVE_MOUNT_MARKERS):
            return True
    return False


def is_usb_storage(node: dict) -> bool:
    if str(node.get("type") or "") not in {"part", "disk"}:
        return False
    if not node.get("fstype"):
        return False
    if is_live_medium(node):
        return False
    return str(node.get("_effective_tran") or "") == "usb" or bool(node.get("_effective_rm"))


def mounted_root_for(node: dict) -> Path | None:
    for mountpoint in mountpoints_from_node(node):
        path = Path(mountpoint)
        if path.exists() and not any(str(path).startswith(marker) for marker in LIVE_MOUNT_MARKERS):
            return path
    return None


def mount_usb_node(node: dict) -> tuple[Path | None, str | None]:
    existing = mounted_root_for(node)
    if existing is not None:
        return existing, None

    device = str(node.get("path") or node.get("name") or "")
    if not device:
        return None, "USB device path was empty."

    label = str(node.get("label") or Path(device).name)
    target = MOUNT_BASE / safe_name(label)
    target.mkdir(parents=True, exist_ok=True)

    result = run_command(["mount", "-o", "rw", device, str(target)], timeout=20)
    if result.returncode == 0:
        return target, None

    message = (result.stderr or result.stdout or "mount failed").strip()
    return None, message


def discover_usb_roots() -> tuple[list[Path], list[str]]:
    roots: list[Path] = []
    errors: list[str] = []
    seen: set[Path] = set()

    for node in list_block_devices():
        if not is_usb_storage(node):
            continue
        root, error = mount_usb_node(node)
        if error:
            name = node.get("label") or node.get("path") or node.get("name") or "USB"
            errors.append(f"{name}: {error}")
        if root and root not in seen:
            roots.append(root)
            seen.add(root)
    return roots, errors


def find_pdfs() -> tuple[list[PdfChoice], list[str]]:
    roots, errors = discover_usb_roots()
    choices: list[PdfChoice] = []

    for root in roots:
        for current, dirs, files in os.walk(root):
            dirs[:] = [
                name for name in dirs
                if name.lower() not in SKIP_DIR_NAMES and not name.startswith(".")
            ]
            for filename in files:
                if filename.lower().endswith(".pdf"):
                    choices.append(PdfChoice(path=Path(current) / filename, usb_root=root))

    choices.sort(key=lambda item: str(item.path).lower())
    return choices, errors


def make_beep_wav(path: Path, frequency: int = 880, seconds: float = 0.35) -> None:
    sample_rate = 44100
    amplitude = 22000
    frames = int(sample_rate * seconds)

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for index in range(frames):
            value = int(amplitude * math.sin(2 * math.pi * frequency * index / sample_rate))
            wav_file.writeframes(struct.pack("<h", value))


def play_done_beep(root: Tk) -> None:
    try:
        root.bell()
    except Exception:
        pass

    wav_path = Path("/tmp/clarity-done.wav")
    try:
        if not wav_path.exists():
            make_beep_wav(wav_path)
        subprocess.Popen(["aplay", "-q", str(wav_path)])
    except Exception:
        pass


class ApplianceApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Clarity OMR Appliance")
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg="#101418")

        self.choices: list[PdfChoice] = []
        self.processing = False

        self.title_label = Label(
            root,
            text="Clarity OMR",
            bg="#101418",
            fg="#f5f7fa",
            font=("DejaVu Sans", 34, "bold"),
        )
        self.title_label.pack(pady=(26, 8))

        self.message_label = Label(
            root,
            text="Insert the second USB drive.",
            bg="#101418",
            fg="#d7dee8",
            font=("DejaVu Sans", 18),
            wraplength=1000,
        )
        self.message_label.pack(pady=(0, 18))

        list_frame = Frame(root, bg="#101418")
        list_frame.pack(fill=BOTH, expand=True, padx=38, pady=10)

        self.listbox = Listbox(
            list_frame,
            bg="#f5f7fa",
            fg="#101418",
            selectbackground="#2b6cb0",
            selectforeground="#ffffff",
            font=("DejaVu Sans", 18),
            activestyle="none",
            relief="flat",
            height=10,
        )
        scrollbar = Scrollbar(list_frame)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.listbox.yview)
        self.listbox.pack(side=LEFT, fill=BOTH, expand=True)

        button_frame = Frame(root, bg="#101418")
        button_frame.pack(fill=BOTH, padx=38, pady=(14, 30))

        self.status_button = Button(
            button_frame,
            text="READY",
            bg="#128a38",
            fg="#ffffff",
            activebackground="#128a38",
            activeforeground="#ffffff",
            disabledforeground="#ffffff",
            font=("DejaVu Sans", 24, "bold"),
            relief="flat",
            width=12,
            state="disabled",
        )
        self.status_button.pack(side=LEFT, padx=(0, 18), ipady=12)

        self.start_button = Button(
            button_frame,
            text="Start",
            command=self.start_processing,
            bg="#ffffff",
            fg="#101418",
            activebackground="#d7dee8",
            font=("DejaVu Sans", 24, "bold"),
            relief="flat",
            width=10,
        )
        self.start_button.pack(side=LEFT, padx=(0, 18), ipady=12)

        self.refresh_button = Button(
            button_frame,
            text="Rescan USB",
            command=self.refresh_pdfs,
            bg="#ffffff",
            fg="#101418",
            activebackground="#d7dee8",
            font=("DejaVu Sans", 18, "bold"),
            relief="flat",
            width=12,
        )
        self.refresh_button.pack(side=LEFT, padx=(0, 18), ipady=15)

        self.power_button = Button(
            button_frame,
            text="Power Off",
            command=self.power_off,
            bg="#2d3748",
            fg="#ffffff",
            activebackground="#4a5568",
            activeforeground="#ffffff",
            font=("DejaVu Sans", 18, "bold"),
            relief="flat",
            width=12,
        )
        self.power_button.pack(side=RIGHT, ipady=15)

        self.set_ready()
        self.refresh_pdfs()
        self.root.after(1000, self.check_clarity_health)
        self.root.after(5000, self.periodic_refresh)

    def set_status_button(self, text: str, color: str) -> None:
        self.status_button.configure(
            text=text,
            bg=color,
            activebackground=color,
        )

    def set_ready(self) -> None:
        self.processing = False
        self.set_status_button("READY", "#128a38")
        self.start_button.configure(state="normal")
        self.refresh_button.configure(state="normal")

    def set_processing(self) -> None:
        self.processing = True
        self.set_status_button("PROCESSING", "#b91c1c")
        self.start_button.configure(state="disabled")
        self.refresh_button.configure(state="disabled")

    def set_message(self, message: str) -> None:
        self.message_label.configure(text=message)

    def periodic_refresh(self) -> None:
        if not self.processing:
            self.refresh_pdfs()
        self.root.after(5000, self.periodic_refresh)

    def refresh_pdfs(self) -> None:
        selected_path = self.selected_pdf_path()
        choices, errors = find_pdfs()
        self.choices = choices

        self.listbox.delete(0, END)
        selected_index = 0
        for index, choice in enumerate(self.choices):
            try:
                display = str(choice.path.relative_to(choice.usb_root))
            except ValueError:
                display = choice.path.name
            self.listbox.insert(END, display)
            if selected_path and choice.path == selected_path:
                selected_index = index

        if self.choices:
            self.listbox.selection_clear(0, END)
            self.listbox.selection_set(selected_index)
            self.listbox.see(selected_index)
            self.set_message(f"{len(self.choices)} PDF file(s) found.")
        else:
            self.set_message("No PDF files found. Insert the second USB drive.")

        if errors and not self.choices:
            self.set_message("USB found, but it could not be mounted. Try a FAT32 or exFAT USB drive.")

    def selected_pdf_path(self) -> Path | None:
        selected = self.listbox.curselection()
        if not selected:
            return None
        index = int(selected[0])
        if index >= len(self.choices):
            return None
        return self.choices[index].path

    def start_processing(self) -> None:
        pdf_path = self.selected_pdf_path()
        if pdf_path is None:
            self.set_message("Select a PDF first.")
            return

        self.set_processing()
        self.set_message(f"Processing {pdf_path.name}")
        thread = threading.Thread(target=self.process_pdf, args=(pdf_path,), daemon=True)
        thread.start()

    def process_pdf(self, pdf_path: Path) -> None:
        output_path = pdf_path.with_suffix(".musicxml")
        log_path = pdf_path.with_suffix(".clarity.log")
        work_dir = pdf_path.parent / ".clarity-work" / safe_name(pdf_path.stem)

        if not CLARITY_PYTHON.exists() or not (CLARITY_ROOT / "omr.py").exists():
            self.finish_with_error("Clarity-OMR is not installed in this ISO.", log_path)
            return

        try:
            work_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.rmtree(work_dir, ignore_errors=True)
            work_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.finish_with_error(f"Could not create work folder: {exc}", log_path)
            return

        command = [
            str(CLARITY_PYTHON),
            str(CLARITY_ROOT / "omr.py"),
            str(pdf_path),
            "-o",
            str(output_path),
            "--device",
            "cpu",
            "--pdf-dpi",
            str(PDF_DPI),
            "--work-dir",
            str(work_dir),
        ]
        if FAST_MODE:
            command.append("--fast")

        env = os.environ.copy()
        env.update(
            {
                "OMP_NUM_THREADS": THREADS,
                "OPENBLAS_NUM_THREADS": THREADS,
                "MKL_NUM_THREADS": THREADS,
                "NUMEXPR_NUM_THREADS": THREADS,
                "TOKENIZERS_PARALLELISM": "false",
                "PYTHONUNBUFFERED": "1",
            }
        )

        try:
            with log_path.open("w", encoding="utf-8", errors="replace") as log:
                log.write("Command:\n")
                log.write(" ".join(command))
                log.write("\n\n")
                log.write(f"Started: {time.ctime()}\n\n")
                log.flush()

                process = subprocess.Popen(
                    command,
                    cwd=str(CLARITY_ROOT),
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    start_new_session=True,
                )
                return_code = process.wait()
                log.write(f"\nFinished: {time.ctime()}\n")
                log.write(f"Exit code: {return_code}\n")
        except OSError as exc:
            self.finish_with_error(f"Could not run Clarity: {exc}", log_path)
            return

        if return_code == 0 and output_path.exists():
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except OSError:
                pass
            self.root.after(0, lambda: self.finish_success(output_path))
            return

        if return_code < 0 and abs(return_code) == signal.SIGILL:
            message = "PyTorch crashed because this CPU likely lacks AVX instructions."
        else:
            message = f"Clarity failed. Log saved as {log_path.name}"
        self.finish_with_error(message, log_path)

    def finish_success(self, output_path: Path) -> None:
        self.set_ready()
        self.set_message(f"Saved {output_path.name}")
        play_done_beep(self.root)
        self.refresh_pdfs()

    def finish_with_error(self, message: str, log_path: Path) -> None:
        def update() -> None:
            self.set_ready()
            self.set_message(message)
            try:
                if not log_path.exists():
                    log_path.write_text(message + "\n", encoding="utf-8")
            except OSError:
                pass
            play_done_beep(self.root)

        self.root.after(0, update)

    def check_clarity_health(self) -> None:
        def worker() -> None:
            flags = read_cpu_flags()
            no_avx = flags and "avx" not in flags

            if not CLARITY_PYTHON.exists():
                message = "Clarity Python environment is missing."
                self.root.after(0, lambda: self.set_message(message))
                return

            result = run_command(
                [str(CLARITY_PYTHON), "-c", "import torch; print(torch.__version__)"],
                timeout=45,
            )
            if result.returncode != 0:
                message = "PyTorch did not start. Clarity may not run on this laptop."
                self.root.after(0, lambda: self.set_message(message))
                return

            if no_avx:
                message = "Old CPU detected. If Clarity fails, the likely cause is missing AVX support."
                self.root.after(0, lambda: self.set_message(message))

        threading.Thread(target=worker, daemon=True).start()

    def power_off(self) -> None:
        subprocess.Popen(["systemctl", "poweroff"])


def main() -> None:
    root = Tk()
    app = ApplianceApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

