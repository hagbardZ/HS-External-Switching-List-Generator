#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Generate a HomeServer .dat list from an AbfallPlus CSV or ICS export.

CSV files are expected to contain one column per waste type with dates in
DD.MM.YYYY format, separated by semicolons. ICS files are read from their
VEVENT entries. For every collection date one reminder entry and one
collection entry are written in the format

    YYYYMMDD_HHMM|location|text

A blank line is inserted between months.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

DEFAULT_INPUT = Path("allestrassenunterkirnach2026a.csv")
DEFAULT_OUTPUT = Path("muell2026.dat")

COLLECTION_TIME = time(8, 0)
DEFAULT_KNX_ADDRESS = "115/1/1"
DEFAULT_START_DAY_OFFSET = -1
DEFAULT_START_CLOCK = time(18, 0)
DEFAULT_END_DAY_OFFSET = 0
DEFAULT_END_CLOCK = COLLECTION_TIME

WEEKDAYS = (
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
)

# key: internal waste type, value: default search text in the source
DEFAULT_SEARCH_TERMS = {
    "gelbe tonne": "Gelbe Tonne",
    "altpapier": "Altpapier",
    "restmull": "Restmüll",
}

# key: internal waste type, value: default output text
DEFAULT_EVENT_NAMES = {
    "gelbe tonne": "Gelber Sack",
    "altpapier": "Altpapier",
    "restmull": "Restmuell",
}

REQUIRED_EVENT_KEYS = ("gelbe tonne", "altpapier", "restmull")
OPTIONAL_EVENT_KEYS = ("extra_1", "extra_2", "extra_3")
EVENT_KEYS = REQUIRED_EVENT_KEYS + OPTIONAL_EVENT_KEYS

WINDOW_ICON_PNG_BASE64 = """
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
"""


class ConversionError(Exception):
    """Raised when the input cannot be converted."""


@dataclass(frozen=True)
class Block:
    collection_date: date
    reminder: datetime
    end: datetime
    source_name: str
    waste_type: str
    lines: tuple[str, str]


def application_dir() -> Path:
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        return Path(appimage).resolve().parent
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def set_window_icon(root: object) -> None:
    import tkinter as tk

    try:
        icon = tk.PhotoImage(
            data="".join(WINDOW_ICON_PNG_BASE64.split())
        )
    except tk.TclError:
        return

    root.iconphoto(True, icon)  # type: ignore[attr-defined]
    root._window_icon = icon  # type: ignore[attr-defined]


def normalize(value: str) -> str:
    value = value.strip().lower()
    value = value.replace("ä", "a").replace("ö", "o").replace("ü", "u")
    value = value.replace("ß", "ss")
    return re.sub(r"\s+", " ", value)


def read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with path.open(newline="", encoding=encoding) as handle:
                rows = list(csv.reader(handle, delimiter=";"))
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ConversionError(f"Could not decode {path}")

    if not rows:
        raise ConversionError(f"{path} is empty")

    header = [name.strip() for name in rows[0]]
    return header, rows[1:]


def decode_ics(path: Path) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ConversionError(f"Could not decode {path}")


def unfold_ics_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        if raw_line.startswith((" ", "\t")) and lines:
            lines[-1] += raw_line[1:]
        else:
            lines.append(raw_line)
    return lines


def unescape_ics_text(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return {"n": "\n", "N": "\n"}.get(match.group(1), match.group(1))

    return re.sub(r"\\([\\,;nN])", replace, value)


def parse_ics_date(value: str) -> date | None:
    value = value.strip()
    if not value:
        return None

    date_part = value.split("T", 1)[0]
    try:
        return datetime.strptime(date_part, "%Y%m%d").date()
    except ValueError:
        return None


def read_ics_events(path: Path) -> list[tuple[date, str]]:
    events: list[tuple[date, str]] = []
    current: dict[str, str] = {}
    in_event = False

    for line in unfold_ics_lines(decode_ics(path)):
        property_name, separator, property_value = line.partition(":")
        name = property_name.split(";", 1)[0].strip().upper()

        if name == "BEGIN" and property_value.strip().upper() == "VEVENT":
            current = {}
            in_event = True
            continue
        if name == "END" and property_value.strip().upper() == "VEVENT":
            if in_event:
                summary = unescape_ics_text(
                    current.get("SUMMARY", "")
                ).strip()
                collection = parse_ics_date(current.get("DTSTART", ""))
                if summary and collection is not None:
                    events.append((collection, summary))
            current = {}
            in_event = False
            continue
        if in_event and separator:
            current.setdefault(name, property_value)

    return events


def read_events(path: Path) -> list[tuple[date, str]]:
    if path.suffix.lower() == ".ics":
        events = read_ics_events(path)
        if not events:
            raise ConversionError(f"{path}: no events found")
        return events

    header, rows = read_csv(path)
    events = []
    for line_number, row in enumerate(rows, start=2):
        for index, source_name in enumerate(header):
            if index >= len(row) or not row[index].strip():
                continue
            events.append(
                (parse_date(row[index], path, line_number), source_name)
            )
    return events


def parse_date(value: str, source: Path, line: int) -> date:
    value = value.strip()
    try:
        return datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError:
        raise ConversionError(
            f"{source}:{line}: invalid date {value!r}, expected DD.MM.YYYY"
        ) from None


def parse_cli_clock(value: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid time {value!r}, expected HH:MM"
        ) from None


def make_blocks(
    input_path: Path,
    knx_address: str = DEFAULT_KNX_ADDRESS,
    start_day_offset: int = DEFAULT_START_DAY_OFFSET,
    start_clock: time = DEFAULT_START_CLOCK,
    end_day_offset: int = DEFAULT_END_DAY_OFFSET,
    end_clock: time = DEFAULT_END_CLOCK,
    event_names: dict[str, str] | None = None,
    search_terms: dict[str, str] | None = None,
) -> list[Block]:
    knx_address = knx_address.strip()
    if not knx_address:
        raise ConversionError("KNX group address must not be empty")

    names = {key: DEFAULT_EVENT_NAMES.get(key, "") for key in EVENT_KEYS}
    for key, value in (event_names or {}).items():
        if key in names:
            names[key] = value.strip()

    searches = {
        key: DEFAULT_SEARCH_TERMS.get(key, "") for key in EVENT_KEYS
    }
    for key, value in (search_terms or {}).items():
        if key in searches:
            searches[key] = value.strip()

    for key in EVENT_KEYS:
        if bool(names[key]) != bool(searches[key]):
            raise ConversionError(
                "Search text and DAT name must both be set for "
                f"{key!r}"
            )

    normalized_searches = {
        key: normalize(value) for key, value in searches.items()
    }

    events = read_events(input_path)

    blocks: list[Block] = []
    for collection, source_name in events:
        normalized_source = normalize(source_name)
        waste_key = next(
            (
                key
                for key, search in normalized_searches.items()
                if search and search in normalized_source
            ),
            None,
        )
        if waste_key is None:
            continue

        text = names[waste_key]
        start = datetime.combine(
            collection + timedelta(days=start_day_offset), start_clock
        )
        end = datetime.combine(
            collection + timedelta(days=end_day_offset), end_clock
        )

        blocks.append(
            Block(
                collection,
                start,
                end,
                source_name,
                text,
                (
                    f"{start:%Y%m%d_%H%M}|{knx_address}|{text}",
                    f"{end:%Y%m%d_%H%M}|{knx_address}|-",
                ),
            )
        )

    if not blocks:
        raise ConversionError(
            f"{input_path}: no matching waste-type events found"
        )

    blocks.sort(
        key=lambda block: (
            block.collection_date,
            block.source_name,
            block.waste_type,
        )
    )
    return blocks


def render(blocks: list[Block]) -> str:
    out: list[str] = []
    previous_month: tuple[int, int] | None = None

    for block in blocks:
        month = (block.collection_date.year, block.collection_date.month)
        if previous_month is not None and month != previous_month:
            out.append("")
        out.extend(block.lines)
        previous_month = month

    return "\n".join(out) + ("\n" if out else "")


def convert(
    input_path: Path,
    output_path: Path,
    knx_address: str = DEFAULT_KNX_ADDRESS,
    start_day_offset: int = DEFAULT_START_DAY_OFFSET,
    start_clock: time = DEFAULT_START_CLOCK,
    end_day_offset: int = DEFAULT_END_DAY_OFFSET,
    end_clock: time = DEFAULT_END_CLOCK,
    event_names: dict[str, str] | None = None,
    search_terms: dict[str, str] | None = None,
) -> int:
    blocks = make_blocks(
        input_path,
        knx_address,
        start_day_offset,
        start_clock,
        end_day_offset,
        end_clock,
        event_names,
        search_terms,
    )
    content = render(blocks)
    output_path.write_text(content, encoding="utf-8", newline="\n")
    return len(blocks)


def run_gui() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    script_dir = application_dir()
    root = tk.Tk()
    root.title("HS_ExternalSwitchingList_Generator")
    root.minsize(880, 680)
    set_window_icon(root)

    frame = ttk.Frame(root, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(6, weight=1)

    input_var = tk.StringVar(value=str(script_dir / DEFAULT_INPUT))
    output_var = tk.StringVar(value=str(script_dir / DEFAULT_OUTPUT))
    knx_var = tk.StringVar(value=DEFAULT_KNX_ADDRESS)
    start_day_var = tk.StringVar(value=str(DEFAULT_START_DAY_OFFSET))
    start_time_var = tk.StringVar(
        value=DEFAULT_START_CLOCK.strftime("%H:%M")
    )
    end_day_var = tk.StringVar(value=str(DEFAULT_END_DAY_OFFSET))
    end_time_var = tk.StringVar(value=DEFAULT_END_CLOCK.strftime("%H:%M"))
    gelbe_search_var = tk.StringVar(
        value=DEFAULT_SEARCH_TERMS["gelbe tonne"]
    )
    altpapier_search_var = tk.StringVar(
        value=DEFAULT_SEARCH_TERMS["altpapier"]
    )
    restmuell_search_var = tk.StringVar(
        value=DEFAULT_SEARCH_TERMS["restmull"]
    )
    gelbe_name_var = tk.StringVar(
        value=DEFAULT_EVENT_NAMES["gelbe tonne"]
    )
    altpapier_name_var = tk.StringVar(
        value=DEFAULT_EVENT_NAMES["altpapier"]
    )
    restmuell_name_var = tk.StringVar(
        value=DEFAULT_EVENT_NAMES["restmull"]
    )
    extra_search_vars = [
        tk.StringVar(value="") for _ in OPTIONAL_EVENT_KEYS
    ]
    extra_name_vars = [
        tk.StringVar(value="") for _ in OPTIONAL_EVENT_KEYS
    ]
    status_var = tk.StringVar(value="Bereit.")
    preview_status_var = tk.StringVar(value="Noch keine Vorschau geladen.")

    def browse_input() -> None:
        selected = filedialog.askopenfilename(
            parent=root,
            title="Eingabedatei auswählen",
            initialdir=str(Path(input_var.get()).parent),
            filetypes=[
                ("CSV/ICS-Dateien", "*.csv *.ics"),
                ("CSV-Dateien", "*.csv"),
                ("ICS-Dateien", "*.ics"),
                ("Alle Dateien", "*.*"),
            ],
        )
        if selected:
            input_var.set(selected)
            refresh_preview()

    def browse_output() -> None:
        current = Path(output_var.get())
        selected = filedialog.asksaveasfilename(
            parent=root,
            title="Ausgabedatei auswählen",
            initialdir=str(current.parent),
            initialfile=current.name,
            defaultextension=".dat",
            filetypes=[("DAT-Dateien", "*.dat"), ("Alle Dateien", "*.*")],
        )
        if selected:
            output_var.set(selected)

    def parse_offsets() -> tuple[int, time, int, time]:
        try:
            start_days = int(start_day_var.get().strip())
            end_days = int(end_day_var.get().strip())
        except ValueError:
            raise ConversionError(
                "Der Tagesversatz muss eine ganze Zahl sein."
            ) from None

        try:
            start_clock = datetime.strptime(
                start_time_var.get().strip(), "%H:%M"
            ).time()
            end_clock = datetime.strptime(
                end_time_var.get().strip(), "%H:%M"
            ).time()
        except ValueError:
            raise ConversionError(
                "Ungültige Uhrzeit. Erwartet: HH:MM."
            ) from None

        return start_days, start_clock, end_days, end_clock

    def get_mappings() -> tuple[dict[str, str], dict[str, str]]:
        names = {
            "gelbe tonne": gelbe_name_var.get().strip(),
            "altpapier": altpapier_name_var.get().strip(),
            "restmull": restmuell_name_var.get().strip(),
        }
        searches = {
            "gelbe tonne": gelbe_search_var.get().strip(),
            "altpapier": altpapier_search_var.get().strip(),
            "restmull": restmuell_search_var.get().strip(),
        }
        for key, search_var, name_var in zip(
            OPTIONAL_EVENT_KEYS, extra_search_vars, extra_name_vars
        ):
            searches[key] = search_var.get().strip()
            names[key] = name_var.get().strip()

        if not all(names[key] for key in REQUIRED_EVENT_KEYS):
            raise ConversionError(
                "Bitte die ersten drei Bezeichnungen ausfüllen."
            )
        if not all(searches[key] for key in REQUIRED_EVENT_KEYS):
            raise ConversionError(
                "Bitte die ersten drei Suchwerte ausfüllen."
            )
        for key in OPTIONAL_EVENT_KEYS:
            if bool(names[key]) != bool(searches[key]):
                raise ConversionError(
                    "Bitte bei zusätzlichen Zeilen Quelle und Name "
                    "gemeinsam ausfüllen."
                )
        return names, searches

    ttk.Label(frame, text="Eingabedatei:").grid(
        row=0, column=0, sticky="w", pady=(0, 8)
    )
    input_entry = ttk.Entry(frame, textvariable=input_var)
    input_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=(0, 8))
    ttk.Button(frame, text="Durchsuchen…", command=browse_input).grid(
        row=0, column=2, pady=(0, 8)
    )

    ttk.Label(frame, text="Ausgabe-DAT:").grid(
        row=1, column=0, sticky="w", pady=(0, 12)
    )
    ttk.Entry(frame, textvariable=output_var).grid(
        row=1, column=1, sticky="ew", padx=8, pady=(0, 12)
    )
    ttk.Button(frame, text="Durchsuchen…", command=browse_output).grid(
        row=1, column=2, pady=(0, 12)
    )

    ttk.Label(frame, text="KNX-Gruppenadresse:").grid(
        row=2, column=0, sticky="w", pady=(0, 12)
    )
    ttk.Entry(frame, textvariable=knx_var, width=24).grid(
        row=2, column=1, sticky="w", padx=8, pady=(0, 12)
    )

    range_frame = ttk.LabelFrame(
        frame, text="Start/Ende der Erinnerung", padding=8
    )
    range_frame.grid(
        row=3, column=0, columnspan=3, sticky="ew", pady=(0, 12)
    )

    ttk.Label(range_frame, text="Start, Tage relativ:").grid(
        row=0, column=0, sticky="w"
    )
    start_day_entry = ttk.Entry(
        range_frame, textvariable=start_day_var, width=6
    )
    start_day_entry.grid(row=0, column=1, sticky="w", padx=(8, 16))
    ttk.Label(range_frame, text="Uhrzeit:").grid(
        row=0, column=2, sticky="w"
    )
    start_time_entry = ttk.Entry(
        range_frame, textvariable=start_time_var, width=8
    )
    start_time_entry.grid(row=0, column=3, sticky="w", padx=(8, 0))

    ttk.Label(range_frame, text="Ende, Tage relativ:").grid(
        row=1, column=0, sticky="w", pady=(6, 0)
    )
    end_day_entry = ttk.Entry(
        range_frame, textvariable=end_day_var, width=6
    )
    end_day_entry.grid(
        row=1, column=1, sticky="w", padx=(8, 16), pady=(6, 0)
    )
    ttk.Label(range_frame, text="Uhrzeit:").grid(
        row=1, column=2, sticky="w", pady=(6, 0)
    )
    end_time_entry = ttk.Entry(
        range_frame, textvariable=end_time_var, width=8
    )
    end_time_entry.grid(
        row=1, column=3, sticky="w", padx=(8, 0), pady=(6, 0)
    )
    ttk.Label(
        range_frame,
        text="Nur der Tag ist relativ, die Uhrzeit ist fest (z. B. +1 / 08:00)",
        foreground="gray",
    ).grid(row=0, column=4, rowspan=2, sticky="w", padx=(24, 0))

    names_frame = ttk.LabelFrame(
        frame, text="Suche und Bezeichnungen im DAT", padding=8
    )
    names_frame.grid(
        row=4, column=0, columnspan=3, sticky="ew", pady=(0, 12)
    )

    ttk.Label(names_frame, text="Suche in der Quelle").grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(names_frame, text="Name im DAT").grid(
        row=0, column=1, sticky="w", padx=(20, 0)
    )

    gelbe_search_entry = ttk.Entry(
        names_frame, textvariable=gelbe_search_var, width=22
    )
    gelbe_search_entry.grid(
        row=1, column=0, sticky="w", pady=(6, 0)
    )
    gelbe_name_entry = ttk.Entry(
        names_frame, textvariable=gelbe_name_var, width=20
    )
    gelbe_name_entry.grid(
        row=1, column=1, sticky="w", padx=(20, 0), pady=(6, 0)
    )

    altpapier_search_entry = ttk.Entry(
        names_frame, textvariable=altpapier_search_var, width=22
    )
    altpapier_search_entry.grid(
        row=2, column=0, sticky="w", pady=(6, 0)
    )
    altpapier_name_entry = ttk.Entry(
        names_frame, textvariable=altpapier_name_var, width=20
    )
    altpapier_name_entry.grid(
        row=2, column=1, sticky="w", padx=(20, 0), pady=(6, 0)
    )

    restmuell_search_entry = ttk.Entry(
        names_frame, textvariable=restmuell_search_var, width=22
    )
    restmuell_search_entry.grid(
        row=3, column=0, sticky="w", pady=(6, 0)
    )
    restmuell_name_entry = ttk.Entry(
        names_frame, textvariable=restmuell_name_var, width=20
    )
    restmuell_name_entry.grid(
        row=3, column=1, sticky="w", padx=(20, 0), pady=(6, 0)
    )

    extra_entries: list[ttk.Entry] = []
    for row, (search_var, name_var) in enumerate(
        zip(extra_search_vars, extra_name_vars), start=4
    ):
        search_entry = ttk.Entry(
            names_frame, textvariable=search_var, width=22
        )
        search_entry.grid(
            row=row, column=0, sticky="w", pady=(6, 0)
        )
        name_entry = ttk.Entry(
            names_frame, textvariable=name_var, width=20
        )
        name_entry.grid(
            row=row, column=1, sticky="w", padx=(20, 0), pady=(6, 0)
        )
        extra_entries.extend([search_entry, name_entry])

    ttk.Label(frame, text="Vorschau der Termine:").grid(
        row=5, column=0, sticky="w", pady=(0, 4)
    )
    ttk.Label(frame, textvariable=preview_status_var).grid(
        row=5, column=1, columnspan=2, sticky="e", pady=(0, 4)
    )

    preview_frame = ttk.Frame(frame)
    preview_frame.grid(row=6, column=0, columnspan=3, sticky="nsew")
    preview_frame.columnconfigure(0, weight=1)
    preview_frame.rowconfigure(0, weight=1)

    preview = ttk.Treeview(
        preview_frame,
        columns=("date", "weekday", "source", "waste", "start", "end"),
        show="headings",
        height=12,
    )
    preview.heading("date", text="Abholdatum")
    preview.heading("weekday", text="Wochentag")
    preview.heading("source", text="Abfallart (Quelle)")
    preview.heading("waste", text="Bezeichnung (DAT)")
    preview.heading("start", text="Start")
    preview.heading("end", text="Ende")
    preview.column("date", width=90, anchor="center", stretch=False)
    preview.column("weekday", width=90, anchor="center", stretch=False)
    preview.column("source", width=170, anchor="w", stretch=True)
    preview.column("waste", width=160, anchor="w", stretch=True)
    preview.column("start", width=135, anchor="center", stretch=False)
    preview.column("end", width=135, anchor="center", stretch=False)
    preview.grid(row=0, column=0, sticky="nsew")

    scrollbar = ttk.Scrollbar(
        preview_frame, orient="vertical", command=preview.yview
    )
    scrollbar.grid(row=0, column=1, sticky="ns")
    preview.configure(yscrollcommand=scrollbar.set)

    def refresh_preview(*_event: object) -> None:
        existing = preview.get_children()
        if existing:
            preview.delete(*existing)

        raw_path = input_var.get().strip()
        if not raw_path:
            preview_status_var.set("Keine Eingabedatei ausgewählt.")
            return

        input_path = Path(raw_path)
        if not input_path.exists():
            preview_status_var.set(f"Datei nicht gefunden: {input_path}")
            return

        try:
            start_days, start_clock, end_days, end_clock = parse_offsets()
            event_names, search_terms = get_mappings()
            blocks = make_blocks(
                input_path,
                DEFAULT_KNX_ADDRESS,
                start_days,
                start_clock,
                end_days,
                end_clock,
                event_names,
                search_terms,
            )
        except (ConversionError, OSError) as exc:
            preview_status_var.set(f"Vorschau nicht möglich: {exc}")
            return

        for block in blocks:
            preview.insert(
                "",
                "end",
                values=(
                    block.collection_date.strftime("%d.%m.%Y"),
                    WEEKDAYS[block.collection_date.weekday()],
                    block.source_name,
                    block.waste_type,
                    block.reminder.strftime("%d.%m.%Y %H:%M"),
                    block.end.strftime("%d.%m.%Y %H:%M"),
                ),
            )

        preview_status_var.set(
            f"{len(blocks)} Abfuhrtermine in der Datei gefunden."
        )

    input_entry.bind("<Return>", refresh_preview)
    input_entry.bind("<FocusOut>", refresh_preview)
    for entry in (
        start_day_entry,
        start_time_entry,
        end_day_entry,
        end_time_entry,
        gelbe_search_entry,
        altpapier_search_entry,
        restmuell_search_entry,
        gelbe_name_entry,
        altpapier_name_entry,
        restmuell_name_entry,
        *extra_entries,
    ):
        entry.bind("<Return>", refresh_preview)
        entry.bind("<FocusOut>", refresh_preview)

    def generate() -> None:
        input_path = Path(input_var.get().strip())
        output_path = Path(output_var.get().strip())
        knx_address = knx_var.get().strip()

        if not input_var.get().strip():
            messagebox.showerror("Fehler", "Bitte eine Eingabedatei auswählen.")
            return
        if not output_var.get().strip():
            messagebox.showerror("Fehler", "Bitte eine Ausgabedatei auswählen.")
            return
        if not knx_address:
            messagebox.showerror(
                "Fehler", "Bitte eine KNX-Gruppenadresse eingeben."
            )
            return
        try:
            start_days, start_clock, end_days, end_clock = parse_offsets()
            event_names, search_terms = get_mappings()
        except ConversionError as exc:
            messagebox.showerror("Fehler", str(exc), parent=root)
            return
        if output_path.exists() and not messagebox.askyesno(
            "Überschreiben?",
            f"{output_path}\n\nDie Datei existiert bereits. Überschreiben?",
            parent=root,
        ):
            return

        try:
            count = convert(
                input_path,
                output_path,
                knx_address,
                start_days,
                start_clock,
                end_days,
                end_clock,
                event_names,
                search_terms,
            )
        except (ConversionError, OSError) as exc:
            status_var.set("Fehler beim Erzeugen.")
            messagebox.showerror("Fehler", str(exc), parent=root)
            return

        status_var.set(f"{count} Termine geschrieben: {output_path}")
        messagebox.showinfo(
            "Fertig",
            f"{count} Termine wurden geschrieben nach:\n{output_path}",
            parent=root,
        )

    ttk.Button(frame, text="Generieren", command=generate).grid(
        row=2, column=2, sticky="e", pady=(0, 12)
    )
    ttk.Label(frame, textvariable=status_var).grid(
        row=8, column=0, columnspan=3, sticky="w", pady=(12, 0)
    )

    root.after(0, refresh_preview)
    root.mainloop()


def main() -> None:
    if len(sys.argv) == 1:
        run_gui()
        return

    parser = argparse.ArgumentParser(
        description="Generate a HomeServer .dat list from an AbfallPlus CSV or ICS file."
    )
    parser.add_argument(
        "csv",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT,
        metavar="INPUT",
        help="input CSV or ICS file (default: %(default)s)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="output .dat file (default: %(default)s)",
    )
    parser.add_argument(
        "-k",
        "--knx-address",
        default=DEFAULT_KNX_ADDRESS,
        help="KNX group address (default: %(default)s)",
    )
    parser.add_argument(
        "-s",
        "--start-days",
        type=int,
        default=DEFAULT_START_DAY_OFFSET,
        help="start day offset relative to collection date (default: %(default)s)",
    )
    parser.add_argument(
        "--start-time",
        type=parse_cli_clock,
        default=DEFAULT_START_CLOCK,
        metavar="HH:MM",
        help="start time of day (default: 18:00)",
    )
    parser.add_argument(
        "-e",
        "--end-days",
        type=int,
        default=DEFAULT_END_DAY_OFFSET,
        help="end day offset relative to collection date (default: %(default)s)",
    )
    parser.add_argument(
        "--end-time",
        type=parse_cli_clock,
        default=DEFAULT_END_CLOCK,
        metavar="HH:MM",
        help="end time of day (default: 08:00)",
    )
    parser.add_argument(
        "--gelber-search",
        default=DEFAULT_SEARCH_TERMS["gelbe tonne"],
        help="source search text for Gelbe Tonne (default: %(default)s)",
    )
    parser.add_argument(
        "--altpapier-search",
        default=DEFAULT_SEARCH_TERMS["altpapier"],
        help="source search text for Altpapier (default: %(default)s)",
    )
    parser.add_argument(
        "--restmuell-search",
        default=DEFAULT_SEARCH_TERMS["restmull"],
        help="source search text for Restmüll (default: %(default)s)",
    )
    parser.add_argument(
        "--gelber-name",
        default=DEFAULT_EVENT_NAMES["gelbe tonne"],
        help="event name for Gelbe Tonne (default: %(default)s)",
    )
    parser.add_argument(
        "--altpapier-name",
        default=DEFAULT_EVENT_NAMES["altpapier"],
        help="event name for Altpapier (default: %(default)s)",
    )
    parser.add_argument(
        "--restmuell-name",
        default=DEFAULT_EVENT_NAMES["restmull"],
        help="event name for Restmüll (default: %(default)s)",
    )
    for number in range(1, len(OPTIONAL_EVENT_KEYS) + 1):
        parser.add_argument(
            f"--extra{number}-search",
            default="",
            help=f"additional source search text {number}",
        )
        parser.add_argument(
            f"--extra{number}-name",
            default="",
            help=f"additional event name {number}",
        )
    args = parser.parse_args()

    event_names = {
        "gelbe tonne": args.gelber_name,
        "altpapier": args.altpapier_name,
        "restmull": args.restmuell_name,
    }
    search_terms = {
        "gelbe tonne": args.gelber_search,
        "altpapier": args.altpapier_search,
        "restmull": args.restmuell_search,
    }
    for number, key in enumerate(OPTIONAL_EVENT_KEYS, start=1):
        search_terms[key] = getattr(args, f"extra{number}_search")
        event_names[key] = getattr(args, f"extra{number}_name")

    try:
        count = convert(
            args.csv,
            args.output,
            args.knx_address,
            args.start_days,
            args.start_time,
            args.end_days,
            args.end_time,
            event_names,
            search_terms,
        )
    except (ConversionError, OSError) as exc:
        raise SystemExit(f"Error: {exc}") from None

    print(f"Wrote {args.output} ({count} appointments)")


if __name__ == "__main__":
    main()
