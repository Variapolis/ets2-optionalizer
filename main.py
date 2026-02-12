import os
import re
import curses
from pathlib import Path

STEAM_APP_ID = "227300"


# ----------------------------
# Folder Selection
# ----------------------------
def select_ets2_folder():
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        folder = filedialog.askdirectory(
            title="Select Euro Truck Simulator 2 Folder"
        )

        if folder:
            return Path(folder).resolve()

        print("No folder selected.")
        exit()

    except Exception:
        print("GUI not available. Please paste ETS2 path manually.")
        folder = input("Path: ").strip()
        if not folder:
            print("No path provided.")
            exit()
        return Path(folder).resolve()


# ----------------------------
# Path Handling
# ----------------------------
def find_workshop_path(ets2_path: Path) -> Path:
    steamapps = ets2_path.parent.parent
    return steamapps / "workshop" / "content" / STEAM_APP_ID


# ----------------------------
# Manifest Helpers
# ----------------------------
def read_manifest_from_text(text):
    return "mp_mod_optional: true" in text


def extract_display_name(text):
    match = re.search(r'display_name:\s*"([^"]+)"', text)
    if match:
        return match.group(1)
    return None


def toggle_manifest_text(text, enable=True):
    lines = text.splitlines()
    result = []
    in_block = False
    brace_level = 0
    modified = False
    value = 'true' if enable else 'false'

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("mod_package") and ":" in stripped:
            in_block = True
            brace_level = line.count("{")

        if in_block:
            brace_level += line.count("{")
            brace_level -= line.count("}")

            if "mp_mod_optional:" in stripped:
                indent = line[:-len(line.lstrip())]
                result.append(f"{indent}mp_mod_optional: {value}")
                modified = True
                continue

            # Insert just before closing brace
            if brace_level == 0 and stripped == "}":
                if not modified:
                    indent = line[:-len(line.lstrip())]
                    result.append(f"{indent}    mp_mod_optional: {value}")
                result.append(line)
                in_block = False
                continue

        result.append(line)

    return "\n".join(result)


# ----------------------------
# Folder Mods
# ----------------------------
def process_folder_mod(manifest_path, enable=None):
    version_folder = manifest_path.parent.name
    workshop_id_folder = manifest_path.parent.parent.name

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_content = f.read()

    current = read_manifest_from_text(manifest_content)
    display_name = extract_display_name(manifest_content)

    if not display_name:
        display_name = workshop_id_folder

    display_name = f"{display_name} [{version_folder}]"

    if enable is not None:
        new_content = toggle_manifest_text(manifest_content, enable)
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        current = enable

    return current, display_name


# ----------------------------
# Collect Mods
# ----------------------------
def collect_mods(workshop_path):
    mods = []
    for root, dirs, files in os.walk(workshop_path):
        for file in files:
            if file == "manifest.sii":
                mods.append(Path(root) / file)
    return mods


# ----------------------------
# Arrow-Key Interactive Menu
# ----------------------------
def arrow_menu(mod_states):
    def draw_menu(stdscr, selected_idx):
        stdscr.clear()
        stdscr.addstr(0, 0, "Use Up/Down arrows to navigate, Space to toggle, A=All On, D=All Off, Q=Quit\n\n")
        for i, (_, state, name) in enumerate(mod_states):
            mark = "[x]" if state else "[ ]"
            if i == selected_idx:
                stdscr.addstr(i + 2, 0, f"> {mark} {name}", curses.A_REVERSE)
            else:
                stdscr.addstr(i + 2, 0, f"  {mark} {name}")
        stdscr.refresh()

    def main_loop(stdscr):
        curses.curs_set(0)
        selected_idx = 0
        while True:
            draw_menu(stdscr, selected_idx)
            key = stdscr.getch()

            if key in [curses.KEY_UP, ord('k')]:
                selected_idx = max(0, selected_idx - 1)
            elif key in [curses.KEY_DOWN, ord('j')]:
                selected_idx = min(len(mod_states) - 1, selected_idx + 1)
            elif key == ord(' '):
                # toggle selected mod
                manifest_path, state, name = mod_states[selected_idx]
                # Pass the new state to process_folder_mod to save it
                new_state, _ = process_folder_mod(manifest_path, not state)
                # Update in-memory state
                mod_states[selected_idx] = (manifest_path, new_state, name)
            elif key in [ord('a'), ord('A')]:
                # enable all
                for i, (manifest_path, _, name) in enumerate(mod_states):
                    _, _ = process_folder_mod(manifest_path, True)
                    mod_states[i] = (manifest_path, True, name)
            elif key in [ord('d'), ord('D')]:
                # disable all
                for i, (manifest_path, _, name) in enumerate(mod_states):
                    _, _ = process_folder_mod(manifest_path, False)
                    mod_states[i] = (manifest_path, False, name)
            elif key in [ord('q'), ord('Q')]:
                break

    curses.wrapper(main_loop)


# ----------------------------
# Main
# ----------------------------
def main():
    ets2_path = select_ets2_folder()
    workshop_path = find_workshop_path(ets2_path)

    if not workshop_path.exists():
        print("Workshop path not found.")
        return

    manifests = collect_mods(workshop_path)
    if not manifests:
        print("No mods with manifest.sii found.")
        return

    mod_states = []
    for manifest_path in manifests:
        try:
            state, name = process_folder_mod(manifest_path)
            mod_states.append((manifest_path, state, name))
        except Exception as e:
            print(f"Error reading {manifest_path}: {e}")

    arrow_menu(mod_states)


if __name__ == "__main__":
    main()
