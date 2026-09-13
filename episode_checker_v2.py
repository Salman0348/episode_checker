import os
import re
import requests
import tkinter as tk

from tkinter import filedialog, messagebox, ttk
from datetime import date
from threading import Thread


# ============================================================
# CONFIGURATION
# ============================================================

TVMAZE_BASE_URL = "https://api.tvmaze.com"

REQUEST_TIMEOUT = 8


# ============================================================
# LOCAL FILE SCANNING
# ============================================================

def extract_episode(filename):
    """
    Extract season and episode number from a filename.

    Supported formats:

        S01E04
        s01e04
        S1E4
        1x04
        01x04
        Season 1 Episode 4
        Season.1.Episode.4
        Season-1-Episode-4
    """

    patterns = [

        # S01E04
        r"[Ss](\d{1,2})[Ee](\d{1,3})",

        # 01x04
        r"(\d{1,2})[xX](\d{1,3})",

        # Season 1 Episode 4
        r"[Ss]eason[\s._-]*(\d{1,2})"
        r"[\s._-]*[Ee]pisode[\s._-]*(\d{1,3})",
    ]

    for pattern in patterns:

        match = re.search(pattern, filename)

        if match:

            season = int(match.group(1))
            episode = int(match.group(2))

            return season, episode

    return None


def scan_folder(folder):
    """
    Scan the selected folder and all subfolders.

    Returns:

        {
            season_number: {episode_numbers}
        }

    Example:

        {
            1: {1, 2, 3, 5},
            2: {1, 2, 3, 4}
        }
    """

    seasons = {}

    for root, _, files in os.walk(folder):

        for filename in files:

            result = extract_episode(filename)

            if result is None:
                continue

            season, episode = result

            if season not in seasons:
                seasons[season] = set()

            seasons[season].add(episode)

    return seasons


# ============================================================
# ORIGINAL OFFLINE CHECK
# ============================================================

def find_local_missing_episodes(seasons):
    """
    Original functionality.

    It assumes the highest episode found locally
    is the last expected episode.

    Example:

        Found:
        E01 E02 E03 E05 E06

        Missing:
        E04
    """

    results = {}

    for season in sorted(seasons):

        episodes = seasons[season]

        if not episodes:
            continue

        first_episode = min(episodes)
        last_episode = max(episodes)

        expected = set(
            range(
                first_episode,
                last_episode + 1
            )
        )

        missing = sorted(
            expected - episodes
        )

        results[season] = {
            "expected": expected,
            "found": episodes,
            "missing": missing,
            "online": False
        }

    return results


# ============================================================
# INTERNET / TVMAZE
# ============================================================

def search_tvmaze_show(show_name):
    """
    Search TVmaze for a show.

    Returns a list of search results.
    """

    url = f"{TVMAZE_BASE_URL}/search/shows"

    params = {
        "q": show_name
    }

    response = requests.get(
        url,
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    return response.json()


def get_tvmaze_episodes(show_id):
    """
    Get all episodes for a TVmaze show.

    Specials are not included because we use
    the standard /episodes endpoint.
    """

    url = (
        f"{TVMAZE_BASE_URL}"
        f"/shows/{show_id}/episodes"
    )

    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    return response.json()


def organize_online_episodes(episodes):
    """
    Convert TVmaze's episode list into:

        {
            season: {episode numbers}
        }

    Only episodes that have already aired are included.
    """

    seasons = {}

    today = date.today()

    for episode in episodes:

        season = episode.get("season")
        number = episode.get("number")
        airdate = episode.get("airdate")

        # Ignore malformed API records
        if season is None or number is None:
            continue

        # Ignore episodes without an airdate
        if not airdate:
            continue

        try:
            episode_date = date.fromisoformat(
                airdate
            )

        except ValueError:
            continue

        # Don't count future episodes as missing
        if episode_date > today:
            continue

        if season not in seasons:
            seasons[season] = set()

        seasons[season].add(number)

    return seasons


# ============================================================
# ONLINE VS LOCAL COMPARISON
# ============================================================

def find_online_missing_episodes(
    local_seasons,
    online_seasons
):
    """
    Compare local episodes against the online
    episode list.

    Example:

        Online:
        {1, 2, 3, 4, 5, 6}

        Local:
        {1, 2, 3, 5, 6}

        Missing:
        {4}
    """

    results = {}

    # Include seasons that exist online
    for season in sorted(online_seasons):

        online_episodes = online_seasons[season]

        local_episodes = local_seasons.get(
            season,
            set()
        )

        missing = sorted(
            online_episodes - local_episodes
        )

        results[season] = {
            "expected": online_episodes,
            "found": local_episodes,
            "missing": missing,
            "online": True
        }

    # Also show local seasons that TVmaze doesn't know
    # about, just in case.
    for season in sorted(local_seasons):

        if season not in results:

            results[season] = {
                "expected": set(),
                "found": local_seasons[season],
                "missing": [],
                "online": True,
                "unknown_online_season": True
            }

    return results


# ============================================================
# FORMATTING
# ============================================================

def format_episodes(episodes):

    if not episodes:
        return "-"

    return ", ".join(
        f"E{episode:02d}"
        for episode in episodes
    )


# ============================================================
# GUI APPLICATION
# ============================================================

class EpisodeCheckerApp:

    def __init__(self, root):

        self.root = root

        self.root.title(
            "Series Episode Checker"
        )

        self.root.geometry(
            "1200x700"
        )

        self.root.minsize(
            950,
            600
        )

        # Current selected folder
        self.selected_folder = None

        # Currently selected TVmaze show
        self.selected_show = None

        # Build GUI
        self.create_gui()


    # ========================================================
    # GUI
    # ========================================================

    def create_gui(self):

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        title = tk.Label(
            self.root,
            text="Series Episode Checker",
            font=("Arial", 22, "bold")
        )

        title.pack(
            pady=(20, 15)
        )


        # ----------------------------------------------------
        # Main controls frame
        # ----------------------------------------------------

        controls = tk.Frame(
            self.root
        )

        controls.pack(
            fill="x",
            padx=25
        )


        # ----------------------------------------------------
        # Series name
        # ----------------------------------------------------

        series_label = tk.Label(
            controls,
            text="Series Name:",
            font=("Arial", 11)
        )

        series_label.grid(
            row=0,
            column=0,
            padx=(0, 8),
            pady=5,
            sticky="w"
        )


        self.series_entry = tk.Entry(
            controls,
            font=("Arial", 11),
            width=35
        )

        self.series_entry.grid(
            row=0,
            column=1,
            padx=5,
            pady=5,
            sticky="w"
        )


        # ----------------------------------------------------
        # Select folder button
        # ----------------------------------------------------

        select_button = tk.Button(
            controls,
            text="📁 Select Folder",
            font=("Arial", 11),
            padx=15,
            pady=5,
            command=self.select_folder
        )

        select_button.grid(
            row=0,
            column=2,
            padx=10,
            pady=5
        )


        # ----------------------------------------------------
        # Scan button
        # ----------------------------------------------------

        self.scan_button = tk.Button(
            controls,
            text="🔍 Scan",
            font=("Arial", 11, "bold"),
            padx=20,
            pady=5,
            command=self.start_scan
        )

        self.scan_button.grid(
            row=0,
            column=3,
            padx=5,
            pady=5
        )


        # ----------------------------------------------------
        # Folder label
        # ----------------------------------------------------

        self.folder_label = tk.Label(
            self.root,
            text="No folder selected",
            font=("Arial", 10),
            fg="gray",
            anchor="w"
        )

        self.folder_label.pack(
            fill="x",
            padx=25,
            pady=(5, 5)
        )


        # ----------------------------------------------------
        # Connection status
        # ----------------------------------------------------

        self.status_label = tk.Label(
            self.root,
            text="Ready",
            font=("Arial", 10),
            anchor="w"
        )

        self.status_label.pack(
            fill="x",
            padx=25,
            pady=(0, 10)
        )


        # ----------------------------------------------------
        # Results frame
        # ----------------------------------------------------

        results_frame = tk.Frame(
            self.root
        )

        results_frame.pack(
            fill="both",
            expand=True,
            padx=25,
            pady=5
        )


        # ----------------------------------------------------
        # Scrollbars
        # ----------------------------------------------------

        vertical_scrollbar = ttk.Scrollbar(
            results_frame,
            orient="vertical"
        )

        horizontal_scrollbar = ttk.Scrollbar(
            results_frame,
            orient="horizontal"
        )


        # ----------------------------------------------------
        # Results table
        # ----------------------------------------------------

        columns = (
            "Season",
            "Expected",
            "Found",
            "Missing",
            "Status"
        )

        self.tree = ttk.Treeview(
            results_frame,
            columns=columns,
            show="headings",
            yscrollcommand=vertical_scrollbar.set,
            xscrollcommand=horizontal_scrollbar.set
        )


        vertical_scrollbar.config(
            command=self.tree.yview
        )

        horizontal_scrollbar.config(
            command=self.tree.xview
        )


        # ----------------------------------------------------
        # Table headings
        # ----------------------------------------------------

        self.tree.heading(
            "Season",
            text="Season"
        )

        self.tree.heading(
            "Expected",
            text="Expected Episodes"
        )

        self.tree.heading(
            "Found",
            text="Episodes Found"
        )

        self.tree.heading(
            "Missing",
            text="Missing Episodes"
        )

        self.tree.heading(
            "Status",
            text="Status"
        )


        # ----------------------------------------------------
        # Table columns
        # ----------------------------------------------------

        self.tree.column(
            "Season",
            width=100,
            anchor="center"
        )

        self.tree.column(
            "Expected",
            width=150,
            anchor="center"
        )

        self.tree.column(
            "Found",
            width=150,
            anchor="center"
        )

        self.tree.column(
            "Missing",
            width=450
        )

        self.tree.column(
            "Status",
            width=130,
            anchor="center"
        )


        # ----------------------------------------------------
        # Pack table + scrollbars
        # ----------------------------------------------------

        self.tree.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        vertical_scrollbar.grid(
            row=0,
            column=1,
            sticky="ns"
        )

        horizontal_scrollbar.grid(
            row=1,
            column=0,
            sticky="ew"
        )


        results_frame.grid_rowconfigure(
            0,
            weight=1
        )

        results_frame.grid_columnconfigure(
            0,
            weight=1
        )


        # ----------------------------------------------------
        # Summary
        # ----------------------------------------------------

        summary_title = tk.Label(
            self.root,
            text="Summary",
            font=("Arial", 12, "bold"),
            anchor="w"
        )

        summary_title.pack(
            fill="x",
            padx=25,
            pady=(10, 2)
        )


        self.summary_text = tk.Text(
            self.root,
            height=5,
            font=("Arial", 10),
            state="disabled"
        )

        self.summary_text.pack(
            fill="x",
            padx=25,
            pady=(0, 20)
        )


    # ========================================================
    # SELECT FOLDER
    # ========================================================

    def select_folder(self):

        folder = filedialog.askdirectory(
            title="Select Series Folder"
        )

        if not folder:
            return

        self.selected_folder = folder

        self.folder_label.config(
            text=f"Folder: {folder}",
            fg="black"
        )

        # Automatically put the folder name into
        # the series name field if it is empty.
        if not self.series_entry.get().strip():

            folder_name = os.path.basename(
                os.path.normpath(folder)
            )

            self.series_entry.insert(
                0,
                folder_name
            )


    # ========================================================
    # START SCAN
    # ========================================================

    def start_scan(self):

        if not self.selected_folder:

            messagebox.showwarning(
                "Folder Required",
                "Please select the series folder first."
            )

            return

        self.scan_button.config(
            state="disabled"
        )

        self.status_label.config(
            text="Scanning folder..."
        )

        # Clear previous results
        self.clear_results()

        # Run scan in background so GUI doesn't freeze
        thread = Thread(
            target=self.perform_scan,
            daemon=True
        )

        thread.start()


    # ========================================================
    # PERFORM SCAN
    # ========================================================

    def perform_scan(self):

        try:

            # ------------------------------------------------
            # Step 1: Scan local files
            # ------------------------------------------------

            local_seasons = scan_folder(
                self.selected_folder
            )

            if not local_seasons:

                self.root.after(
                    0,
                    self.show_no_files
                )

                return


            # ------------------------------------------------
            # Step 2: Try online search
            # ------------------------------------------------

            show_name = (
                self.series_entry
                .get()
                .strip()
            )

            if not show_name:

                show_name = os.path.basename(
                    os.path.normpath(
                        self.selected_folder
                    )
                )


            self.root.after(
                0,
                lambda: self.status_label.config(
                    text="Checking internet connection..."
                )
            )


            try:

                search_results = search_tvmaze_show(
                    show_name
                )

                # Internet worked, but no show was found
                if not search_results:

                    self.root.after(
                        0,
                        lambda: self.use_offline_mode(
                            local_seasons,
                            "Series not found online."
                        )
                    )

                    return


                # ------------------------------------------------
                # Ask user to choose show
                # ------------------------------------------------

                self.root.after(
                    0,
                    lambda: self.choose_show(
                        search_results,
                        local_seasons
                    )
                )


            except (
                requests.RequestException,
                requests.ConnectionError,
                requests.Timeout
            ):

                # ------------------------------------------------
                # No internet
                # ------------------------------------------------

                self.root.after(
                    0,
                    lambda: self.use_offline_mode(
                        local_seasons,
                        "No internet connection. "
                        "Using offline mode."
                    )
                )


        except Exception as error:

            self.root.after(
                0,
                lambda: self.show_error(
                    str(error)
                )
            )


    # ========================================================
    # SHOW SEARCH RESULTS
    # ========================================================

    def choose_show(
        self,
        search_results,
        local_seasons
    ):

        # Create selection window

        window = tk.Toplevel(
            self.root
        )

        window.title(
            "Select Series"
        )

        window.geometry(
            "650x450"
        )

        window.transient(
            self.root
        )

        window.grab_set()


        label = tk.Label(
            window,
            text="Select the correct series:",
            font=("Arial", 13, "bold")
        )

        label.pack(
            pady=(20, 10)
        )


        # ----------------------------------------------------
        # Results list
        # ----------------------------------------------------

        listbox = tk.Listbox(
            window,
            font=("Arial", 11),
            height=12
        )

        listbox.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=10
        )


        # ----------------------------------------------------
        # Store actual show objects
        # ----------------------------------------------------

        shows = []

        for result in search_results:

            show = result.get(
                "show",
                {}
            )

            name = show.get(
                "name",
                "Unknown"
            )

            premiered = show.get(
                "premiered",
                "Unknown"
            )

            status = show.get(
                "status",
                "Unknown"
            )

            show_type = show.get(
                "type",
                "Unknown"
            )

            display = (
                f"{name} | "
                f"{premiered} | "
                f"{status} | "
                f"{show_type}"
            )

            listbox.insert(
                tk.END,
                display
            )

            shows.append(show)


        if shows:

            listbox.selection_set(0)


        # ----------------------------------------------------
        # Select button
        # ----------------------------------------------------

        def select_show():

            selection = listbox.curselection()

            if not selection:

                messagebox.showwarning(
                    "Select Series",
                    "Please select a series."
                )

                return

            index = selection[0]

            selected_show = shows[index]

            window.destroy()

            self.selected_show = selected_show

            self.load_online_episodes(
                selected_show,
                local_seasons
            )


        button = tk.Button(
            window,
            text="Use Selected Series",
            font=("Arial", 11, "bold"),
            padx=20,
            pady=7,
            command=select_show
        )

        button.pack(
            pady=(5, 20)
        )


        # Double click also selects
        listbox.bind(
            "<Double-Button-1>",
            lambda event: select_show()
        )


    # ========================================================
    # LOAD ONLINE EPISODES
    # ========================================================

    def load_online_episodes(
        self,
        show,
        local_seasons
    ):

        show_name = show.get(
            "name",
            "Unknown"
        )

        show_id = show.get(
            "id"
        )

        self.status_label.config(
            text=(
                f"Online mode: "
                f"Loading episodes for {show_name}..."
            )
        )


        # --------------------------------------------
        # Download episodes in background
        # --------------------------------------------

        thread = Thread(
            target=self.download_online_data,
            args=(
                show_id,
                show_name,
                local_seasons
            ),
            daemon=True
        )

        thread.start()


    # ========================================================
    # DOWNLOAD ONLINE DATA
    # ========================================================

    def download_online_data(
        self,
        show_id,
        show_name,
        local_seasons
    ):

        try:

            episodes = get_tvmaze_episodes(
                show_id
            )

            online_seasons = (
                organize_online_episodes(
                    episodes
                )
            )

            results = find_online_missing_episodes(
                local_seasons,
                online_seasons
            )


            self.root.after(
                0,
                lambda: self.display_results(
                    results,
                    online=True,
                    show_name=show_name
                )
            )


        except (
            requests.RequestException,
            requests.ConnectionError,
            requests.Timeout
        ):

            # If the online request fails,
            # fall back to the old method.

            self.root.after(
                0,
                lambda: self.use_offline_mode(
                    local_seasons,
                    "Online lookup failed. "
                    "Using offline mode."
                )
            )


        except Exception as error:

            self.root.after(
                0,
                lambda: self.show_error(
                    str(error)
                )
            )


    # ========================================================
    # OFFLINE MODE
    # ========================================================

    def use_offline_mode(
        self,
        local_seasons,
        reason
    ):

        results = find_local_missing_episodes(
            local_seasons
        )

        self.display_results(
            results,
            online=False,
            show_name=None,
            offline_reason=reason
        )


    # ========================================================
    # DISPLAY RESULTS
    # ========================================================

    def display_results(
        self,
        results,
        online,
        show_name=None,
        offline_reason=None
    ):

        # Clear table
        self.clear_results()


        # ----------------------------------------------------
        # Determine mode
        # ----------------------------------------------------

        if online:

            self.status_label.config(
                text=(
                    f"Online mode — "
                    f"{show_name}"
                ),
                fg="green"
            )

        else:

            self.status_label.config(
                text=(
                    f"Offline mode — "
                    f"{offline_reason or ''}"
                ),
                fg="orange"
            )


        # ----------------------------------------------------
        # Insert rows
        # ----------------------------------------------------

        total_found = 0
        total_expected = 0
        total_missing = 0

        for season in sorted(results):

            data = results[season]

            expected = data.get(
                "expected",
                set()
            )

            found = data.get(
                "found",
                set()
            )

            missing = data.get(
                "missing",
                []
            )

            total_found += len(found)

            total_expected += len(expected)

            total_missing += len(missing)


            # ------------------------------------------------
            # Status
            # ------------------------------------------------

            if online and data.get(
                "unknown_online_season",
                False
            ):

                status = "Not Online"

            elif missing:

                status = "Missing"

            else:

                status = "Complete"


            # ------------------------------------------------
            # Expected value
            # ------------------------------------------------

            if expected:

                expected_text = str(
                    len(expected)
                )

            else:

                expected_text = "Unknown"


            # ------------------------------------------------
            # Insert table row
            # ------------------------------------------------

            self.tree.insert(
                "",
                tk.END,
                values=(
                    f"Season {season}",
                    expected_text,
                    len(found),
                    format_episodes(missing),
                    status
                )
            )


        # ----------------------------------------------------
        # Summary
        # ----------------------------------------------------

        self.set_summary(
            online=online,
            show_name=show_name,
            seasons=len(results),
            expected=total_expected,
            found=total_found,
            missing=total_missing
        )


        # Enable scan again
        self.scan_button.config(
            state="normal"
        )


    # ========================================================
    # SUMMARY
    # ========================================================

    def set_summary(
        self,
        online,
        show_name,
        seasons,
        expected,
        found,
        missing
    ):

        if online:

            mode_text = (
                f"Online mode\n"
                f"Series: {show_name}"
            )

        else:

            mode_text = (
                "Offline mode\n"
                "Expected episode count is "
                "based on the highest episode found locally."
            )


        if missing == 0:

            result_text = (
                "\n\n"
                "✅ No missing episodes found."
            )

        else:

            result_text = (
                f"\n\n"
                f"❌ Missing episodes: {missing}"
            )


        text = (
            f"{mode_text}\n"
            f"Seasons found: {seasons}\n"
            f"Episodes found locally: {found}\n"
        )

        if online:

            text += (
                f"Expected aired episodes: "
                f"{expected}"
            )

        text += result_text


        self.summary_text.config(
            state="normal"
        )

        self.summary_text.delete(
            "1.0",
            tk.END
        )

        self.summary_text.insert(
            tk.END,
            text
        )

        self.summary_text.config(
            state="disabled"
        )


    # ========================================================
    # CLEAR RESULTS
    # ========================================================

    def clear_results(self):

        for item in self.tree.get_children():

            self.tree.delete(
                item
            )

        self.summary_text.config(
            state="normal"
        )

        self.summary_text.delete(
            "1.0",
            tk.END
        )

        self.summary_text.config(
            state="disabled"
        )


    # ========================================================
    # NO FILES
    # ========================================================

    def show_no_files(self):

        self.scan_button.config(
            state="normal"
        )

        self.status_label.config(
            text="No episode files found.",
            fg="red"
        )

        messagebox.showinfo(
            "No Episodes Found",
            "No recognizable episode files were found "
            "in the selected folder."
        )


    # ========================================================
    # ERROR
    # ========================================================

    def show_error(self, error):

        self.scan_button.config(
            state="normal"
        )

        self.status_label.config(
            text="Error occurred.",
            fg="red"
        )

        messagebox.showerror(
            "Error",
            f"Something went wrong:\n\n{error}"
        )


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    root = tk.Tk()

    app = EpisodeCheckerApp(
        root
    )

    root.mainloop()