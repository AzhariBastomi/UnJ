"""
tools/json_to_gherkin.py -- Generate file .feature (Gherkin) dari suite JSON
mana pun (TM81, BEXA, Flash, dst), supaya urutan step bisa dibaca/diedit
non-programmer tanpa sentuh JSON/Python.

Mendukung dua format suite (sama seperti JsonTestSource.entries() di
lib/loaders/base.py):
  - "steps" -- ringkas, merujuk step library "_steps.json" di folder yang
    sama dengan suite JSON-nya (dipakai TM81).
  - "tests"  -- entry lengkap langsung di file suite-nya sendiri, tanpa
    library terpisah (dipakai BEXA, Flash).

Pemakaian:
    python tools/json_to_gherkin.py commands/tm81/config/tm81_join.json
    python tools/json_to_gherkin.py commands/bexa/config/bexa_test.json
    python tools/json_to_gherkin.py commands/flash/config/tm81.json

Menghasilkan:
    <folder JSON>/<stem>.feature          -- daftar step dalam kalimat (field "label", fallback "description")
    (ditulis di folder yang SAMA dengan JSON sumbernya, bukan folder features/ terpusat.
    Kalimatnya dicocokkan LANGSUNG ke "name"/"label" entry oleh
    lib/loaders/gherkin_common.py -- tidak ada file map terpisah yang perlu digenerate)

PENTING: <stem> = nama file JSON tanpa ekstensi. Kalau dua suite JSON di
folder BERBEDA punya nama file SAMA, .feature-nya akan bentrok (saling timpa).
Semua suite yang ada di project ini saat ini punya nama file unik.
"""
import json
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_step_library(json_path):
    """Cari _steps.json di folder yang sama dengan suite JSON. {} kalau tidak ada."""
    lib_path = os.path.join(os.path.dirname(json_path), "_steps.json")
    if not os.path.isfile(lib_path):
        return {}
    data = _read(lib_path)
    steps = data.get("steps", data)
    return {k: v for k, v in steps.items() if not k.startswith("_")}


def _resolve(step, library):
    """Sama seperti JsonTestSource._resolve_step -- lihat lib/loaders/base.py."""
    if isinstance(step, str):
        name, override = step, {}
    elif isinstance(step, dict):
        name = step.get("use")
        if not name:
            return dict(step)
        override = {k: v for k, v in step.items() if k != "use"}
    else:
        return {"name": str(step), "description": str(step)}

    base = dict(library.get(name, {}))
    entry = dict(base)
    entry.update(override)
    entry["name"] = override.get("name") or name
    return {k: v for k, v in entry.items() if v is not None}


def _resolve_entries(cfg, json_path):
    if "steps" in cfg:
        library = _load_step_library(json_path)
        return [_resolve(s, library) for s in cfg.get("steps", [])]
    # Format "tests" -- entry sudah lengkap, tidak lewat library.
    return [dict(e) for e in cfg.get("tests", []) if e.get("name")]


def convert(json_path):
    json_path = os.path.abspath(json_path)
    cfg = _read(json_path)
    stem = os.path.splitext(os.path.basename(json_path))[0]
    entries = _resolve_entries(cfg, json_path)

    lines = []
    seen_desc = set()
    first = True
    for e in entries:
        if e.get("disabled"):
            continue
        name = e.get("name", "unknown")
        # Prioritaskan "label" (bukan "description") sebagai kalimat Gherkin --
        # supaya file .feature ini langsung dicocokkan LANGSUNG ke "name"/
        # "label" entry-nya sendiri oleh lib/loaders/gherkin_common.py &
        # lib/loaders/gherkin_lean.py, TANPA butuh file map terpisah.
        # description tetap dipakai sebagai fallback kalau tidak ada label.
        desc = (e.get("label") or e.get("description") or name).strip()
        if not desc:
            continue

        if desc in seen_desc:
            # Tabrakan label dgn entry lain -- pakai NAMA entry langsung
            # (selalu unik) sebagai kalimat, bukan akal-akalan suffix.
            desc = name
        seen_desc.add(desc)

        kw = "Given" if first else ("Then" if e.get("expect") else "And")
        first = False
        lines.append(f"    {kw} {desc}")

    if not lines:
        print(f"Tidak ada step ditemukan di {json_path} (format 'steps'/'tests' kosong) -- dilewati.")
        return

    label = cfg.get("label", stem.replace("_", " ").title())
    rel_json = os.path.relpath(json_path, _ROOT)

    # Kalau JSON-nya override "prefix" (beda dari nama file), simpan sebagai
    # comment "# prefix: ..." di .feature -- dipakai lib/loaders/gherkin_lean.py
    # supaya module name (mis. "tm81:xxx") tetap sama persis walau nanti
    # JSON-nya dihapus dan suite ini jalan murni dari .feature (mode ringkas).
    prefix_line = ""
    json_prefix = cfg.get("prefix")
    if json_prefix and json_prefix != stem:
        prefix_line = f"# prefix: {json_prefix}\n"

    feature_text = (
        f"# File ini digenerate otomatis dari {rel_json}\n"
        f"# Regenerasi setelah edit JSON: python tools/json_to_gherkin.py {rel_json}\n"
        f"# Untuk ubah alur test cukup edit file ini -- tidak perlu sentuh JSON/Python.\n"
        f"# Urutan baris = urutan eksekusi. Hapus baris = step dilewati.\n"
        + prefix_line
        + f"\n"
        f"Feature: {label}\n"
        f"\n"
        f"  Scenario: {label}\n"
        + "\n".join(lines) + "\n"
    )

    # Ditulis di folder YANG SAMA dengan JSON sumbernya (bukan features/
    # terpusat) -- supaya file .feature & _map_<stem>.json satu suite
    # ngumpul di folder config device-nya (commands/tm81/config/,
    # commands/bexa/config/, commands/flash/config/, dst).
    out_dir = os.path.dirname(json_path)

    feat_path = os.path.join(out_dir, f"{stem}.feature")
    with open(feat_path, "w", encoding="utf-8") as f:
        f.write(feature_text)

    print(f"Ditulis: {os.path.relpath(feat_path, _ROOT)}  ({len(lines)} step)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Pemakaian: python tools/json_to_gherkin.py <path ke suite json> [json lain...]")
        sys.exit(1)
    for p in sys.argv[1:]:
        convert(p)
