"""
DepotDownloader GUI  —  customtkinter edition
pip install customtkinter Pillow

DLL expected at:  ./libs/DepotDownloaderMod.dll
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import subprocess, threading, shutil, re, os, json, tempfile, zipfile, io
import urllib.request, urllib.parse, urllib.error

try:
    from PIL import Image, ImageTk
    _PIL = True
except ImportError:
    _PIL = False

_img_cache: dict = {}   # url -> PhotoImage or CTkImage

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

DLL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "libs", "DepotDownloaderMod.dll")
# always save config to Downloads folder
CONFIG_PATH = os.path.join(os.path.expanduser("~"), "Downloads", "ddgui_config.json")
BASE = "https://manifest.morrenus.xyz/api/v1"

#  config
def load_config():
    try:
        with open(CONFIG_PATH) as f: return json.load(f)
    except Exception: return {}

def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w") as f: json.dump(cfg, f, indent=2)
    except Exception: pass

#  lua / manifest helpers 
def parse_lua(path):
    depots = {}
    with open(path, encoding="utf-8") as f:
        text = f.read()
    for m in re.finditer(r'addappid\(\s*(\d+)\s*,\s*\d+\s*,\s*"([0-9a-fA-F]+)"\s*\)', text):
        d, k = m.group(1), m.group(2)
        depots.setdefault(d, {"key": None, "manifest": None})["key"] = k
    for m in re.finditer(r'addappid\(\s*(\d+)\s*\)', text):
        depots.setdefault(m.group(1), {"key": None, "manifest": None})
    for m in re.finditer(r'setManifestid\(\s*(\d+)\s*,\s*"(\d+)"\s*\)', text):
        d, v = m.group(1), m.group(2)
        depots.setdefault(d, {"key": None, "manifest": None})["manifest"] = v
    return depots

def write_temp_keyfile(lua_depots):
    lines = [f"{d};{i['key']}" for d, i in sorted(lua_depots.items(), key=lambda x: int(x[0])) if i["key"]]
    if not lines: return None
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".key", delete=False, prefix="ddgui_")
    tmp.write("\n".join(lines)); tmp.close()
    return tmp.name

def parse_manifest_filename(fn):
    m = re.match(r'^(\d+)_(\d+)\.manifest$', os.path.basename(fn))
    return (m.group(1), m.group(2)) if m else (None, None)

#  api
def api_search(key, q):
    # use Steam API for images, manifest API for other data
    steam_url = f"https://store.steampowered.com/api/storesearch/?term={urllib.parse.quote(q)}&cc=US&l=english"
    manifest_url = f"{BASE}/search?api_key={urllib.parse.quote(key)}&q={urllib.parse.quote(q)}"
    
    # fetch from Steam API for images
    steam_data = {}
    try:
        print(f"[DEBUG] Fetching from Steam API: {steam_url}")
        with urllib.request.urlopen(urllib.request.Request(steam_url, headers={"User-Agent": "DDGui/4"}), timeout=15) as r:
            steam_response = json.loads(r.read())
            # Create a dict mapping app_id to tiny_image for quick lookup
            items = steam_response.get("items", [])
            print(f"[DEBUG] Steam API returned {len(items)} items")
            for item in items:
                app_id = str(item.get("id", ""))
                tiny_img = item.get("tiny_image", "")
                if app_id and tiny_img:
                    steam_data[app_id] = tiny_img
                    print(f"[DEBUG] Stored image for app {app_id}: {tiny_img[:60]}...")
    except Exception as e:
        print(f"[DEBUG] Steam API failed: {e}")
    
    # Fetch from manifest API
    print(f"[DEBUG] Fetching from Manifest API: {manifest_url}")
    with urllib.request.urlopen(urllib.request.Request(manifest_url, headers={"User-Agent": "DDGui/4"}), timeout=15) as r:
        data = json.loads(r.read())
    
    results = data.get("results", data if isinstance(data, list) else [])
    print(f"[DEBUG] Manifest API returned {len(results)} results")
    
    # Add tiny_image to each result if available
    for result in results:
        game_id = str(result.get("game_id", ""))
        game_name = result.get("game_name", "Unknown")
        
        if game_id in steam_data:
            result["tiny_image"] = steam_data[game_id]
            print(f"[DEBUG] ✓ Matched image for '{game_name}' (ID: {game_id})")
        else:
            result["tiny_image"] = ""
            print(f"[DEBUG] ✗ No image found for '{game_name}' (ID: {game_id})")
    
    return results

def api_user_stats(key):
    url = f"{BASE}/user/stats?api_key={urllib.parse.quote(key)}"
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "DDGui/4"}), timeout=10
    ) as r:
        return json.loads(r.read())

def fetch_image_ctk(url, width=192, height=90):
    """Download a Steam header image and return a PhotoImage that fills the exact dimensions."""
    if not _PIL:
        print("[DEBUG] PIL not available")
        return None
    if not url:
        print("[DEBUG] No URL provided")
        return None
    
    # Create cache key with dimensions
    cache_key = f"{url}_{width}x{height}"
    if cache_key in _img_cache:
        print(f"[DEBUG] Image in cache: {url[:50]}")
        return _img_cache[cache_key]
    
    try:
        print(f"[DEBUG] Fetching image from: {url[:80]}")
        req = urllib.request.Request(url, headers={"User-Agent": "DDGui/4"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
        print(f"[DEBUG] Downloaded {len(data)} bytes")
        
        # Load and resize image to EXACT dimensions (will stretch to fit)
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img = img.resize((width, height), Image.LANCZOS)
        
        # Create PhotoImage which will display at exact size
        photo_img = ImageTk.PhotoImage(img)
        _img_cache[cache_key] = photo_img
        print(f"[DEBUG] Image created and cached at {width}x{height}")
        return photo_img
    except Exception as e:
        print(f"[DEBUG] Image fetch error: {e}")
        return None

def api_fetch_zip(key, app_id, dest):
    url = f"{BASE}/manifest/{app_id}?api_key={urllib.parse.quote(key)}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "DDGui/4"}), timeout=30) as r:
        raw = r.read()
    folder = os.path.join(dest, f"app_{app_id}")
    os.makedirs(folder, exist_ok=True)
    zp = os.path.join(folder, "dl.zip")
    with open(zp, "wb") as f: f.write(raw)
    with zipfile.ZipFile(zp) as z: z.extractall(folder)
    os.remove(zp)
    luas, manifests = [], []
    for rd, _, files in os.walk(folder):
        for fn in files:
            full = os.path.join(rd, fn)
            if fn.endswith(".lua"): luas.append(full)
            elif fn.endswith(".manifest"): manifests.append(full)
    return folder, luas, manifests


# app
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SOCRATES-DL -- WSG -- V1")
        self.geometry("1000x560")
        self.minsize(860, 700)
        self.configure(fg_color="#0d0d14")

        # Load icon from URL and set window icon
        self._app_icon = None
        self._sidebar_icon = None
        threading.Thread(target=self._load_app_icon, daemon=True).start()

        self.cfg            = load_config()
        self.process        = None
        self._tmpkey        = None
        self.lua_depots     = {}
        self.manifest_files = []
        self.search_res     = []

        # hidden state — no UI for these
        self._lua_path        = ""
        self._fetched_app_id  = ""   # the app_id used when fetching the zip
        self._fetched_game_name = ""  # game name from the search result
        self._fetched_game_image = "" # tiny_image URL from the search result
        self._app_id          = ""
        self._depot_id        = ""
        self._manifest_id     = ""
        self._manifest_path   = ""
        self._output_dir      = ""

        self._build()

    def _load_app_icon(self):
        """Download the .ico from catbox and set both the window icon and sidebar label icon."""
        ICON_URL = "https://files.catbox.moe/nfppzl.ico"
        try:
            req = urllib.request.Request(ICON_URL, headers={"User-Agent": "DDGui/4"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read()
            if _PIL:
                img = Image.open(io.BytesIO(data))

                # Window icon (taskbar + title bar) — use a 32x32 variant
                ico_img = img.copy()
                ico_img = ico_img.resize((32, 32), Image.LANCZOS).convert("RGBA")
                self._app_icon = ImageTk.PhotoImage(ico_img)
                self.after(0, lambda: self.iconphoto(True, self._app_icon))

                # Sidebar label icon — 20x20
                small = img.copy().resize((20, 20), Image.LANCZOS).convert("RGBA")
                self._sidebar_icon = ctk.CTkImage(light_image=small, dark_image=small, size=(20, 20))
                self.after(0, self._apply_sidebar_icon)
        except Exception as e:
            print(f"[DEBUG] Icon load failed: {e}")

    def _apply_sidebar_icon(self):
        """Update the sidebar logo label to show the icon next to the text."""
        if self._sidebar_icon and hasattr(self, "_logo_label"):
            self._logo_label.configure(image=self._sidebar_icon, compound="left")

    # chrome 
    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()

        content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        self._frames = {}
        for name, builder in [
            ("search",     self._build_search),
            ("downloader", self._build_downloader),
            ("quota",      self._build_quota),
            ("settings",   self._build_settings),
        ]:
            f = ctk.CTkFrame(content, corner_radius=0, fg_color="transparent")
            f.grid(row=0, column=0, sticky="nsew")
            f.grid_columnconfigure(0, weight=1)
            f.grid_rowconfigure(0, weight=1)
            builder(f)
            self._frames[name] = f

        self._show("search")

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#0a0a10")
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_rowconfigure(6, weight=1)
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)
        
        # Configure row 6 to expand for image
        sb.grid_rowconfigure(6, weight=1)

        # ── logo area ──
        logo_frame = ctk.CTkFrame(sb, fg_color="#12121e", corner_radius=0)
        logo_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        logo_frame.grid_columnconfigure(0, weight=1)

        self._logo_label = ctk.CTkLabel(logo_frame, text=" SOCRATES-DL-V1",
                     font=ctk.CTkFont(family="Courier", size=20, weight="bold"),
                     text_color="#4fc3f7")
        self._logo_label.grid(row=0, column=0, pady=(22, 0))
        ctk.CTkLabel(logo_frame, text="SOCRATES-DL --WSG-- V1",
                     font=ctk.CTkFont(family="Courier", size=9),
                     text_color="#2a4a5a").grid(row=1, column=0, pady=(0, 18))

        #  divider
        ctk.CTkFrame(sb, height=1, fg_color="#1a1a28", corner_radius=0).grid(
            row=1, column=0, sticky="ew")

        #  nav items 
        self._nav_btns = {}
        nav_items = [
            ("search",     "Search",        ""),
            ("downloader", "Downloader",    ""),
            ("quota",      "Daily Limit",   ""),
            ("settings",   "Settings",      ""),
        ]
        for i, (key, label, icon) in enumerate(nav_items, start=2):
            btn_frame = ctk.CTkFrame(sb, fg_color="transparent", corner_radius=0)
            btn_frame.grid(row=i, column=0, sticky="ew", padx=12, pady=3)
            btn_frame.grid_columnconfigure(1, weight=1)

            # indicator bar on the left
            ind = ctk.CTkFrame(btn_frame, width=3, height=36, corner_radius=2,
                                fg_color="transparent")
            ind.grid(row=0, column=0, padx=(0, 10))

            b = ctk.CTkButton(
                btn_frame, text=f"  {icon}   {label}",
                anchor="w", height=40, corner_radius=8,
                fg_color="transparent",
                hover_color="#151528",
                font=ctk.CTkFont(size=13),
                text_color="#8888aa",
                command=lambda n=key: self._show(n))
            b.grid(row=0, column=1, sticky="ew")

            self._nav_btns[key] = (b, ind)

        # image area 
        self.sidebar_image_label = ctk.CTkLabel(sb, text="Loading image...",
                                                 text_color="#666677",
                                                 font=ctk.CTkFont(size=10))
        self.sidebar_image_label.grid(row=6, column=0, sticky="nsew", padx=10, pady=10)
        
        # Load image in background
        threading.Thread(target=self._load_sidebar_image, daemon=True).start()

        #  bottom tag 
        ctk.CTkLabel(sb, text="manifest.morrenus.xyz",
                     font=ctk.CTkFont(size=10), text_color="#222233").grid(
            row=7, column=0, pady=(0, 14))

    def _load_sidebar_image(self):
        """Load image from URL for sidebar"""
        try:
            if not _PIL: return
            image_url = "https://files.catbox.moe/v6oorg.jfif"
            req = urllib.request.Request(image_url, headers={"User-Agent": "DDGui/4"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read()
            img = Image.open(io.BytesIO(data)).convert("RGB")
            # Resize to fit sidebar width (200px)
            img.thumbnail((200, 300), Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
            self.sidebar_image_label.configure(image=ctk_img, text="")
            self.sidebar_image_label.image = ctk_img
        except Exception as e:
            self.sidebar_image_label.configure(text="Image load failed")

    def _show(self, name):
        for f in self._frames.values(): f.grid_remove()
        self._frames[name].grid()
        for n, (b, ind) in self._nav_btns.items():
            if n == name:
                b.configure(fg_color="#151530", text_color="#ffffff")
                ind.configure(fg_color="#4fc3f7")
            else:
                b.configure(fg_color="transparent", text_color="#8888aa")
                ind.configure(fg_color="transparent")
        if name == "quota":
            self._refresh_quota()

    # 1
    # SEARCH
    # 2
    def _build_search(self, parent):
        parent.grid_rowconfigure(2, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # header
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=32, pady=(28, 0))
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text="Search Games",
                     font=ctk.CTkFont(size=26, weight="bold"),
                     text_color="#ffffff").grid(row=0, column=0, sticky="w", pady=(0, 4))
        ctk.CTkLabel(hdr, text="Find a game and fetch its manifest files",
                     font=ctk.CTkFont(size=13), text_color="#555566").grid(
            row=1, column=0, sticky="w", pady=(0, 18))

        # search bar
        bar = ctk.CTkFrame(hdr, fg_color="#12121e", corner_radius=12,
                            border_width=1, border_color="#1e1e32")
        bar.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        bar.grid_columnconfigure(0, weight=1)

        self.search_var = ctk.StringVar()
        se = ctk.CTkEntry(bar, textvariable=self.search_var,
                           placeholder_text="Search for a game…",
                           height=46, font=ctk.CTkFont(size=14),
                           fg_color="transparent", border_width=0)
        se.grid(row=0, column=0, sticky="ew", padx=(16, 0))
        se.bind("<Return>", lambda _: self._do_search())

        self.search_btn = ctk.CTkButton(bar, text="Search", width=110, height=38,
                                         corner_radius=8,
                                         font=ctk.CTkFont(size=13, weight="bold"),
                                         command=self._do_search)
        self.search_btn.grid(row=0, column=1, padx=6, pady=4)

        # status
        self.search_status = ctk.StringVar(value="")
        ctk.CTkLabel(parent, textvariable=self.search_status,
                     text_color="#444455", font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, sticky="w", padx=34, pady=(0, 4))

        # results
        self.results_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                                      scrollbar_fg_color="#0a0a10")
        self.results_scroll.grid(row=2, column=0, sticky="nsew", padx=28, pady=(0, 8))
        self.results_scroll.grid_columnconfigure(0, weight=1)
        self._result_widgets = []

        # bottom
        bot = ctk.CTkFrame(parent, fg_color="transparent")
        bot.grid(row=3, column=0, sticky="ew", padx=32, pady=(0, 16))
        self.fetch_status = ctk.StringVar(value="")
        ctk.CTkLabel(bot, textvariable=self.fetch_status,
                     text_color="#4fc3f7", font=ctk.CTkFont(size=12)).pack(side="left")

    def _do_search(self):
        key = self.cfg.get("api_key", "").strip()
        if not key:
            messagebox.showwarning("No API Key", "Go to Settings and enter your API key first.")
            return
        q = self.search_var.get().strip()
        if not q: return
        self.search_btn.configure(state="disabled", text="…")
        self.search_status.set("Searching…")
        self._clear_results()
        threading.Thread(target=self._search_thread, args=(key, q), daemon=True).start()

    def _search_thread(self, key, q):
        try:
            results = api_search(key, q)
            self.after(0, lambda: self._populate_results(results))
        except Exception as e:
            self.after(0, lambda: self.search_status.set(f"Error: {e}"))
        finally:
            self.after(0, lambda: self.search_btn.configure(state="normal", text="Search"))

    def _clear_results(self):
        for w in self._result_widgets: w.destroy()
        self._result_widgets.clear()

    def _populate_results(self, results):
        self._clear_results()
        self.search_status.set(f"{len(results)} results")
        for r in results:
            self._make_card(r)

    def _make_card(self, r):
        avail = r.get("manifest_available", False)
        img_url = r.get("tiny_image", "")
        print(f"[DEBUG] _make_card: {r.get('game_name')} | img_url={img_url if img_url else 'EMPTY'}")

        card = ctk.CTkFrame(self.results_scroll, corner_radius=12,
                             fg_color="#111120", border_width=1, border_color="#1c1c2e")
        card.grid(sticky="ew", padx=2, pady=5)
        card.grid_columnconfigure(2, weight=1)

        # banner image placeholder 
        img_lbl = ctk.CTkLabel(card, text="", width=192,
                                fg_color="#0a0a18", corner_radius=8)
        img_lbl.grid(row=0, column=0, rowspan=2, padx=(10, 14), pady=10, sticky="nsew")

        # accent strip
        ctk.CTkFrame(card, width=3, corner_radius=2,
                     fg_color="#4fc3f7" if avail else "#222233").grid(
            row=0, column=1, rowspan=2, sticky="ns", padx=(0, 12), pady=12)

        ctk.CTkLabel(card, text=r["game_name"],
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#eeeeff", anchor="w").grid(
            row=0, column=2, sticky="w", pady=(14, 2))

        ctk.CTkLabel(card,
                     text=f"App {r['game_id']}   ·   {r.get('uploaded_date', '?')}",
                     font=ctk.CTkFont(size=11), text_color="#44445a", anchor="w").grid(
            row=1, column=2, sticky="w", pady=(0, 14))

        right = ctk.CTkFrame(card, fg_color="transparent")
        right.grid(row=0, column=3, rowspan=2, padx=(0, 16), pady=12, sticky="e")

        if avail:
            ctk.CTkButton(right, text="Fetch", width=84, height=34,
                           corner_radius=8,
                           font=ctk.CTkFont(size=12, weight="bold"),
                           fg_color="#1a3a5c", hover_color="#1f4a74",
                           text_color="#4fc3f7",
                           command=lambda aid=str(r["game_id"]), nm=r["game_name"], img=img_url:
                               self._fetch(aid, nm, img)).pack()
        else:
            ctk.CTkLabel(right, text="unavailable", width=84,
                         font=ctk.CTkFont(size=11), text_color="#333344").pack()

        self._result_widgets.append(card)

        # async load image
        if img_url and _PIL:
            threading.Thread(target=self._load_card_image,
                              args=(img_url, img_lbl), daemon=True).start()

    def _load_card_image(self, url, label):
        print(f"[DEBUG] Loading card image: {url[:80]}")
        img = fetch_image_ctk(url, width=192, height=150)  # Tall to fill full card height
        if img:
            print(f"[DEBUG] Image loaded successfully")
            # Keep a reference to prevent garbage collection
            label._photo_ref = img
            # Configure label to display the image
            self.after(0, lambda: label.configure(image=img, text=""))
        else:
            print(f"[DEBUG] Image load FAILED")

    def _load_picker_image(self, url, label):
        """Load image for game picker with smaller dimensions."""
        print(f"[DEBUG] Loading picker image: {url[:80]}")
        img = fetch_image_ctk(url, width=115, height=43)
        if img:
            print(f"[DEBUG] Picker image loaded successfully")
            # Keep a reference to prevent garbage collection
            label._photo_ref = img
            # Configure label to display the image
            self.after(0, lambda: label.configure(image=img, text=""))
        else:
            print(f"[DEBUG] Picker image load FAILED")

    def _fetch(self, app_id, game_name, img_url=""):
        print(f"[DEBUG] _fetch called for: {game_name} (ID: {app_id})")
        key = self.cfg.get("api_key", "").strip()
        if not key:
            messagebox.showwarning("No API Key", "Set your API key in Settings."); return
        save_dir = self.cfg.get("manifest_save_dir",
                                 os.path.join(os.path.dirname(os.path.abspath(__file__)), "Manifests"))
        
        self.fetch_status.set(f"Fetching {game_name}…")
        
        # Store new game info FIRST
        self._fetched_app_id = app_id
        self._fetched_game_name = game_name
        self._fetched_game_image = img_url
        print(f"[DEBUG] Stored game info - ID: {self._fetched_app_id}, Name: {self._fetched_game_name}")
        
        # Clear the UI to show we're loading new game
        # _game_rows contains tuples of (frame, indicator)
        print(f"[DEBUG] Clearing {len(self._game_rows)} old game rows")
        for row_frame, indicator in self._game_rows:
            row_frame.destroy()
        self._game_rows.clear()
        self._picker_placeholder.grid()  # Show placeholder while loading
        
        print(f"[DEBUG] Starting fetch thread for {game_name}")
        threading.Thread(target=self._fetch_thread,
                          args=(key, app_id, game_name, save_dir), daemon=True).start()
    
    def _clear_game_picker(self):
        """Clear the game picker to remove old game data."""
        for row_frame, indicator in self._game_rows:
            row_frame.destroy()
        self._game_rows.clear()
        self.lua_depots = {}
        self.manifest_files = []
        self._picker_placeholder.grid()  # Show placeholder again

    def _fetch_thread(self, key, app_id, game_name, save_dir):
        print(f"[DEBUG] _fetch_thread started for {game_name}")
        try:
            folder, luas, manifests = api_fetch_zip(key, app_id, save_dir)
            print(f"[DEBUG] Fetched {len(luas)} lua files and {len(manifests)} manifests")
            self.manifest_files = manifests
            self.after(0, lambda: self.fetch_status.set(
                f"✓  {game_name}  —  head to Downloader tab"))
            if luas:
                print(f"[DEBUG] Ingesting lua file: {luas[0]}")
                self.after(0, lambda p=luas[0]: self._ingest_lua(p))
            self.after(0, self._auto_match_all)
            print(f"[DEBUG] Fetch completed successfully for {game_name}")
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}: {e.reason}"
            print(f"[DEBUG] HTTP Error: {err}")
            self.after(0, lambda: [self.fetch_status.set(f"Error: {err}"),
                                    messagebox.showerror("Fetch failed", err)])
        except Exception as e:
            print(f"[DEBUG] Exception in fetch_thread: {e}")
            import traceback
            traceback.print_exc()
            self.after(0, lambda: [self.fetch_status.set(f"Error: {e}"),
                                    messagebox.showerror("Fetch failed", str(e))])

    # 1
    # DOWNLOADER
    # 2
    def _build_downloader(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                         scrollbar_fg_color="#0a0a10")
        scroll.grid(row=0, column=0, sticky="nsew", padx=28, pady=24)
        scroll.grid_columnconfigure(0, weight=1)

        r = 0

        # page title
        ctk.CTkLabel(scroll, text="Downloader",
                     font=ctk.CTkFont(size=26, weight="bold"),
                     text_color="#ffffff").grid(row=r, column=0, sticky="w"); r += 1
        ctk.CTkLabel(scroll, text="Select a depot and output folder, then run",
                     font=ctk.CTkFont(size=13), text_color="#555566").grid(
            row=r, column=0, sticky="w", pady=(2, 24)); r += 1

        #  Game Picker 
        self._section_label(scroll, r, "Game Picker"); r += 1

        self.game_picker_frame = ctk.CTkFrame(scroll, fg_color="#0e0e1c",
                                               corner_radius=12,
                                               border_width=1, border_color="#1a1a2c")
        self.game_picker_frame.grid(row=r, column=0, sticky="ew", pady=(6, 24)); r += 1
        self.game_picker_frame.grid_columnconfigure(0, weight=1)

        self._game_rows = []
        self._selected_depot = None

        # placeholder
        self._picker_placeholder = ctk.CTkLabel(
            self.game_picker_frame,
            text="Fetch a game from the Search tab first",
            font=ctk.CTkFont(size=13), text_color="#333344")
        self._picker_placeholder.grid(row=0, column=0, pady=28)

        # Output folder 
        self._section_label(scroll, r, "Output Folder"); r += 1

        out_card = ctk.CTkFrame(scroll, fg_color="#0e0e1c", corner_radius=12,
                                 border_width=1, border_color="#1a1a2c")
        out_card.grid(row=r, column=0, sticky="ew", pady=(6, 24)); r += 1
        out_card.grid_columnconfigure(0, weight=1)

        out_inner = ctk.CTkFrame(out_card, fg_color="transparent")
        out_inner.pack(fill="x", padx=18, pady=14)
        out_inner.grid_columnconfigure(0, weight=1)

        self.output_dir_var = ctk.StringVar()
        self._out_label = ctk.CTkLabel(out_inner,
                                        text="No folder selected",
                                        font=ctk.CTkFont(size=13),
                                        text_color="#444455", anchor="w")
        self._out_label.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(out_inner, text="Choose Folder", width=130, height=36,
                       corner_radius=8, font=ctk.CTkFont(size=12),
                       fg_color="#1a1a30", hover_color="#252540",
                       command=self._pick_output).grid(row=0, column=1, padx=(12, 0))

        #  Options 
        self._section_label(scroll, r, "Options"); r += 1

        opt_card = ctk.CTkFrame(scroll, fg_color="#0e0e1c", corner_radius=12,
                                 border_width=1, border_color="#1a1a2c")
        opt_card.grid(row=r, column=0, sticky="ew", pady=(6, 24)); r += 1

        opt_inner = ctk.CTkFrame(opt_card, fg_color="transparent")
        opt_inner.pack(fill="x", padx=18, pady=14)

        ctk.CTkLabel(opt_inner, text="Max Downloads",
                     font=ctk.CTkFont(size=13), text_color="#8888aa").pack(side="left")
        self.max_dl_var = ctk.StringVar(value="256")
        ctk.CTkEntry(opt_inner, textvariable=self.max_dl_var,
                     width=64, height=32, font=ctk.CTkFont(size=13)).pack(
            side="left", padx=(10, 28))
        self.verify_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(opt_inner, text="Verify all files",
                       font=ctk.CTkFont(size=13), text_color="#8888aa",
                       variable=self.verify_var).pack(side="left")

        #  Run 
        run_card = ctk.CTkFrame(scroll, fg_color="transparent")
        run_card.grid(row=r, column=0, sticky="ew", pady=(0, 14)); r += 1

        self.run_btn = ctk.CTkButton(run_card, text="▶   Run Download",
                                      width=190, height=48,
                                      corner_radius=10,
                                      font=ctk.CTkFont(size=15, weight="bold"),
                                      command=self._run)
        self.run_btn.pack(side="left", padx=(0, 10))

        self.stop_btn = ctk.CTkButton(run_card, text="■  Stop",
                                       width=100, height=48, corner_radius=10,
                                       fg_color="#2a0f0f", hover_color="#3a1515",
                                       text_color="#e05555",
                                       state="disabled", command=self._stop)
        self.stop_btn.pack(side="left", padx=(0, 10))

        ctk.CTkButton(run_card, text="Clear Log", width=100, height=48,
                       corner_radius=10, fg_color="transparent",
                       border_width=1, border_color="#1e1e32",
                       text_color="#555566",
                       command=self._clear_log).pack(side="left")

        self.run_status_var = ctk.StringVar(value="")
        ctk.CTkLabel(run_card, textvariable=self.run_status_var,
                     text_color="#555566", font=ctk.CTkFont(size=12)).pack(side="right")

        #  Log 
        self._section_label(scroll, r, "Log"); r += 1
        self.log_box = ctk.CTkTextbox(scroll, height=220,
                                       font=ctk.CTkFont(family="Courier", size=11),
                                       fg_color="#080810", corner_radius=12,
                                       border_width=1, border_color="#1a1a2c",
                                       text_color="#8899bb")
        self.log_box.grid(row=r, column=0, sticky="ew", pady=(6, 28))
        self.log_box.configure(state="disabled")

    def _section_label(self, parent, row, text):
        ctk.CTkLabel(parent, text=text,
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#4fc3f7").grid(
            row=row, column=0, sticky="w", pady=(0, 2))

    #  lua ingestion + auto-match 
    def _ingest_lua(self, path):
        self._lua_path = path
        try:
            self.lua_depots = parse_lua(path)
        except Exception as e:
            messagebox.showerror("Lua error", str(e)); return
        self._rebuild_picker()

    def _rebuild_picker(self):
        for w in self._game_rows: w.destroy()
        self._game_rows.clear()
        self._picker_placeholder.grid_remove()

        # Only show depots that have BOTH a key AND a matching manifest file
        # — those are the "real" downloadable depots
        downloadable = []
        for did, info in sorted(self.lua_depots.items(), key=lambda x: int(x[0])):
            matching_mf = self._find_manifest_for(did)
            if info["key"] and matching_mf:
                downloadable.append((did, info, matching_mf))

        if not downloadable:
            # Fall back: show all depots with keys even if no manifest matched yet
            for did, info in sorted(self.lua_depots.items(), key=lambda x: int(x[0])):
                if info["key"]:
                    downloadable.append((did, info, None))

        # ONLY SHOW THE FIRST DEPOT
        if downloadable:
            did, info, mf = downloadable[0]  # Get only the first one
            i = 0
            
            row_fg = "#111122"
            rf = ctk.CTkFrame(self.game_picker_frame, fg_color=row_fg, corner_radius=0)
            rf.grid(row=i, column=0, sticky="ew")
            rf.grid_columnconfigure(2, weight=1)

            # selection indicator
            ind = ctk.CTkFrame(rf, width=4, height=32, corner_radius=2, fg_color="transparent")
            ind.grid(row=0, column=0, rowspan=2, padx=(10, 12), pady=10)

            # ── Game image placeholder ──
            img_lbl = ctk.CTkLabel(rf, text="", width=115, height=43,
                                   fg_color="#0a0a18", corner_radius=6)
            img_lbl.grid(row=0, column=1, rowspan=2, padx=(0, 12), pady=8)

            # Use the stored game name from when we fetched it
            game_name = self._fetched_game_name if self._fetched_game_name else f"Game {did}"
            img_url = self._fetched_game_image

            # depot id + manifest id
            mid = info["manifest"] or (parse_manifest_filename(mf)[1] if mf else "—")
            ctk.CTkLabel(rf, text=game_name,
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color="#ccccee", anchor="w").grid(
                row=0, column=2, sticky="w", pady=(12, 2))
            ctk.CTkLabel(rf, text=f"Manifest  {mid}",
                         font=ctk.CTkFont(size=11), text_color="#444466", anchor="w").grid(
                row=1, column=2, sticky="w", pady=(0, 12))

            sel_btn = ctk.CTkButton(rf, text="Select", width=80, height=30,
                                     corner_radius=8,
                                     fg_color="#151530", hover_color="#1f1f40",
                                     font=ctk.CTkFont(size=12),
                                     command=lambda d=did, m=mf, ix=i, ind_w=ind:
                                         self._select_depot(d, m, ix, ind_w))
            sel_btn.grid(row=0, column=3, rowspan=2, padx=(0, 14), pady=10)

            self._game_rows.append((rf, ind))

            # async load image
            if img_url and _PIL:
                threading.Thread(target=self._load_picker_image,
                                 args=(img_url, img_lbl), daemon=True).start()

            # auto-select it
            self._select_depot(did, mf, 0, ind)

    def _find_manifest_for(self, depot_id):
        for mf in self.manifest_files:
            did, _ = parse_manifest_filename(os.path.basename(mf))
            if did == depot_id:
                return mf
        return None

    def _auto_match_all(self):
        self._rebuild_picker()

    def _select_depot(self, did, mf, row_idx, ind_widget):
        self._selected_depot = did
        info = self.lua_depots.get(did, {})
        self._depot_id      = did
        self._manifest_path = mf or ""

        # manifest ID: prefer lua setManifestid, fall back to filename
        mid_from_lua  = info.get("manifest") or ""
        mid_from_file = parse_manifest_filename(os.path.basename(mf))[1] if mf else ""
        self._manifest_id = mid_from_lua or mid_from_file

        # app_id: use the stored app_id if we have one, otherwise same as depot
        self._app_id = self._fetched_app_id or did

        # update highlight
        for i, (rf, ind) in enumerate(self._game_rows):
            if i == row_idx:
                rf.configure(fg_color="#131a2e")
                ind.configure(fg_color="#4fc3f7")
            else:
                rf.configure(fg_color="#111122" if i % 2 == 0 else "#0e0e1c")
                ind.configure(fg_color="transparent")

    #  output folder 
    def _pick_output(self):
        p = filedialog.askdirectory()
        if p:
            self._output_dir = p
            # show shortened path
            short = p if len(p) < 55 else "…" + p[-52:]
            self._out_label.configure(text=short, text_color="#aaaacc")

    # 
    def _run(self):
        if not os.path.exists(DLL_PATH):
            messagebox.showerror("DLL not found",
                f"Place DepotDownloaderMod.dll in:\n{os.path.dirname(DLL_PATH)}"); return
        if not self._depot_id:
            messagebox.showerror("Nothing selected", "Select a depot from the Game Picker."); return
        if not self._output_dir:
            messagebox.showerror("No output folder", "Choose an output folder first."); return
        if not shutil.which("dotnet"):
            messagebox.showerror("dotnet not found",
                "Install .NET from https://dotnet.microsoft.com"); return
        if not self.cfg.get("steam_username", "").strip():
            if not messagebox.askyesno("No Steam login",
                "No Steam username is set in Settings.\n\n"
                "Most games require a Steam account that owns them.\n"
                "Continue anonymously anyway?"):
                return

        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.run_status_var.set("Running…")
        self._log("─" * 56 + "\n")

        cmd = self._build_cmd()
        self._log("$ " + " ".join(cmd) + "\n\n")
        threading.Thread(target=self._run_thread, args=(cmd,), daemon=True).start()

    def _build_cmd(self):
        dotnet = shutil.which("dotnet") or "dotnet"
        cmd    = [dotnet, DLL_PATH]

        username = self.cfg.get("steam_username", "").strip()
        password = self.cfg.get("steam_password", "").strip()
        if username:
            cmd += ["-username", username]
        if password:
            cmd += ["-password", password]

        if self._app_id:        cmd += ["-app",         self._app_id]
        if self._depot_id:      cmd += ["-depot",        self._depot_id]
        if self._manifest_id:   cmd += ["-manifest",     self._manifest_id]
        if self._manifest_path: cmd += ["-manifestfile", self._manifest_path]
        if self.lua_depots:
            self._tmpkey = write_temp_keyfile(self.lua_depots)
            if self._tmpkey:
                cmd += ["-depotkeys", self._tmpkey]
        cmd += ["-dir",           self._output_dir or "."]
        cmd += ["-max-downloads", self.max_dl_var.get().strip() or "256"]
        if self.verify_var.get(): cmd.append("-verify-all")
        return cmd

    def _cleanup_tmpkey(self):
        if self._tmpkey and os.path.exists(self._tmpkey):
            try: os.remove(self._tmpkey)
            except OSError: pass
        self._tmpkey = None

    def _run_thread(self, cmd):
        try:
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in self.process.stdout: self._log(line)
            self.process.wait()
            rc = self.process.returncode
            msg = "✓  Done" if rc == 0 else f"✗  Exit {rc}"
            self.after(0, lambda: self.run_status_var.set(msg))
            self._log(f"\n{msg}\n")
        except Exception as e:
            self._log(f"\nError: {e}\n")
            self.after(0, lambda: self.run_status_var.set("Error"))
        finally:
            self._cleanup_tmpkey()
            self.process = None
            self.after(0, lambda: (
                self.run_btn.configure(state="normal"),
                self.stop_btn.configure(state="disabled")))

    def _stop(self):
        if self.process:
            self.process.terminate()
            self._log("\n[Stopped]\n")
            self.run_status_var.set("Stopped")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _log(self, text):
        def _do():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", text)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _do)

    # 
    #  DAILY LIMIT
    #
    def _build_quota(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.grid(row=0, column=0, sticky="n", padx=60, pady=40)
        wrap.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(wrap, text="Daily Download Limit",
                     font=ctk.CTkFont(size=26, weight="bold"),
                     text_color="#ffffff").grid(row=0, column=0, sticky="w", pady=(0, 4))
        ctk.CTkLabel(wrap, text="Check how many manifest fetches you have left today",
                     font=ctk.CTkFont(size=13), text_color="#555566").grid(
            row=1, column=0, sticky="w", pady=(0, 24))

        # stats card
        stats_card = ctk.CTkFrame(wrap, fg_color="#0e0e1c", corner_radius=14,
                                   border_width=1, border_color="#1a1a2c")
        stats_card.grid(row=2, column=0, sticky="ew", pady=(0, 20))
        stats_card.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(stats_card, fg_color="transparent")
        inner.pack(fill="x", padx=28, pady=24)
        inner.grid_columnconfigure((0, 1, 2), weight=1)

        # usage / limit big numbers
        self._q_used_var  = ctk.StringVar(value="—")
        self._q_limit_var = ctk.StringVar(value="—")
        self._q_left_var  = ctk.StringVar(value="—")

        for ci, (title, var, color) in enumerate([
            ("Used today",   self._q_used_var,  "#f0a855"),
            ("Daily limit",  self._q_limit_var, "#4fc3f7"),
            ("Remaining",    self._q_left_var,  "#4caf50"),
        ]):
            col_f = ctk.CTkFrame(inner, fg_color="transparent")
            col_f.grid(row=0, column=ci, padx=8, sticky="ew")
            ctk.CTkLabel(col_f, textvariable=var,
                         font=ctk.CTkFont(size=40, weight="bold"),
                         text_color=color).pack()
            ctk.CTkLabel(col_f, text=title,
                         font=ctk.CTkFont(size=12), text_color="#555566").pack(pady=(2, 0))

        # progress bar
        self._q_progress_var = ctk.DoubleVar(value=0)
        self._q_bar = ctk.CTkProgressBar(inner, height=8, corner_radius=4,
                                          progress_color="#4fc3f7",
                                          fg_color="#1a1a2c")
        self._q_bar.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(20, 4))
        self._q_bar.set(0)

        self._q_bar_label = ctk.StringVar(value="")
        ctk.CTkLabel(inner, textvariable=self._q_bar_label,
                     font=ctk.CTkFont(size=11), text_color="#444455").grid(
            row=2, column=0, columnspan=3, sticky="w")

        # ── account details card ──
        acc_card = ctk.CTkFrame(wrap, fg_color="#0e0e1c", corner_radius=14,
                                 border_width=1, border_color="#1a1a2c")
        acc_card.grid(row=3, column=0, sticky="ew", pady=(0, 24))
        acc_card.grid_columnconfigure(0, weight=1)

        acc_inner = ctk.CTkFrame(acc_card, fg_color="transparent")
        acc_inner.pack(fill="x", padx=28, pady=20)
        acc_inner.grid_columnconfigure(1, weight=1)

        self._q_fields = {}
        for ri, (lbl, key) in enumerate([
            ("Username",    "username"),
            ("Role limit",  "role_daily_limit"),
            ("Key expires", "api_key_expires_at"),
            ("Key uses",    "api_key_usage_count"),
        ]):
            ctk.CTkLabel(acc_inner, text=lbl,
                         font=ctk.CTkFont(size=12), text_color="#555566",
                         anchor="w").grid(row=ri, column=0, sticky="w",
                                           padx=(0, 24), pady=4)
            var = ctk.StringVar(value="—")
            self._q_fields[key] = var
            ctk.CTkLabel(acc_inner, textvariable=var,
                         font=ctk.CTkFont(size=12), text_color="#aaaacc",
                         anchor="w").grid(row=ri, column=1, sticky="w", pady=4)

        # refresh button
        btn_row = ctk.CTkFrame(wrap, fg_color="transparent")
        btn_row.grid(row=4, column=0, sticky="w")

        self.quota_btn = ctk.CTkButton(btn_row, text="↻  Refresh", width=140, height=42,
                                        corner_radius=10,
                                        font=ctk.CTkFont(size=13, weight="bold"),
                                        command=self._refresh_quota)
        self.quota_btn.pack(side="left", padx=(0, 16))

        self._q_status = ctk.StringVar(value="")
        ctk.CTkLabel(btn_row, textvariable=self._q_status,
                     font=ctk.CTkFont(size=12), text_color="#555566").pack(side="left")

    def _refresh_quota(self):
        key = self.cfg.get("api_key", "").strip()
        if not key:
            messagebox.showwarning("No API Key", "Set your API key in Settings first.")
            return
        self.quota_btn.configure(state="disabled", text="Loading…")
        self._q_status.set("")
        threading.Thread(target=self._quota_thread, args=(key,), daemon=True).start()

    def _quota_thread(self, key):
        try:
            d = api_user_stats(key)
            self.after(0, lambda: self._populate_quota(d))
        except Exception as e:
            self.after(0, lambda: self._q_status.set(f"Error: {e}"))
        finally:
            self.after(0, lambda: self.quota_btn.configure(state="normal", text="↻  Refresh"))

    def _populate_quota(self, d):
        used  = int(d.get("daily_usage",  0))
        limit = int(d.get("daily_limit",  0))
        left  = max(0, limit - used)
        ratio = (used / limit) if limit > 0 else 0

        self._q_used_var.set(str(used))
        self._q_limit_var.set(str(limit))
        self._q_left_var.set(str(left))

        self._q_bar.set(min(ratio, 1.0))
        # turn bar red when close to limit
        bar_color = "#e05555" if ratio >= 0.9 else "#f0a855" if ratio >= 0.7 else "#4fc3f7"
        self._q_bar.configure(progress_color=bar_color)
        self._q_bar_label.set(f"{used} / {limit} fetches used today")

        exp = d.get("api_key_expires_at", "—")
        if exp and "T" in exp:
            exp = exp.split("T")[0]   # just the date part

        self._q_fields["username"].set(d.get("username", "—"))
        self._q_fields["role_daily_limit"].set(str(d.get("role_daily_limit", "—")))
        self._q_fields["api_key_expires_at"].set(exp)
        self._q_fields["api_key_usage_count"].set(str(d.get("api_key_usage_count", "—")))

        self._q_status.set("Updated just now")

    # 
    # SETTINGS
    # 
    def _build_settings(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Create scrollable frame
        scroll_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll_frame.grid(row=0, column=0, sticky="nsew")
        scroll_frame.grid_columnconfigure(0, weight=1)

        wrap = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        wrap.pack(fill="x", padx=60, pady=40)
        wrap.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(wrap, text="Settings",
                     font=ctk.CTkFont(size=26, weight="bold"),
                     text_color="#ffffff").pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(wrap, text="Configure your API key and storage location",
                     font=ctk.CTkFont(size=13), text_color="#555566").pack(
            anchor="w", pady=(0, 28))

        # API key card
        api_card = ctk.CTkFrame(wrap, fg_color="#0e0e1c", corner_radius=14,
                                 border_width=1, border_color="#1a1a2c")
        api_card.pack(fill="x", pady=(0, 16))

        api_inner = ctk.CTkFrame(api_card, fg_color="transparent")
        api_inner.pack(fill="x", padx=24, pady=20)
        api_inner.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(api_inner, text="API Key",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#ffffff").grid(row=0, column=0, sticky="w", pady=(0, 4))
        ctk.CTkLabel(api_inner, text="Your manifest.morrenus.xyz key",
                     font=ctk.CTkFont(size=11), text_color="#444455").grid(
            row=1, column=0, sticky="w", pady=(0, 10))

        self.api_key_var = ctk.StringVar(value=self.cfg.get("api_key", ""))
        self.api_entry = ctk.CTkEntry(api_inner, textvariable=self.api_key_var,
                                       show="•", height=42, font=ctk.CTkFont(size=13))
        self.api_entry.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        self._show_key = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(api_inner, text="Show key",
                       font=ctk.CTkFont(size=12), text_color="#666677",
                       variable=self._show_key,
                       command=lambda: self.api_entry.configure(
                           show="" if self._show_key.get() else "•")
                       ).grid(row=3, column=0, sticky="w")

        # Steam credentials card
        steam_card = ctk.CTkFrame(wrap, fg_color="#0e0e1c", corner_radius=14,
                                   border_width=1, border_color="#1a1a2c")
        steam_card.pack(fill="x", pady=(0, 16))

        st_inner = ctk.CTkFrame(steam_card, fg_color="transparent")
        st_inner.pack(fill="x", padx=24, pady=20)
        st_inner.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(st_inner, text="Steam Account",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#ffffff").grid(row=0, column=0, columnspan=4,
                                                sticky="w", pady=(0, 4))
        ctk.CTkLabel(st_inner, text="Required for games that need a Steam login",
                     font=ctk.CTkFont(size=11), text_color="#444455").grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(0, 12))

        ctk.CTkLabel(st_inner, text="Username",
                     font=ctk.CTkFont(size=12), text_color="#8888aa").grid(
            row=2, column=0, sticky="w", padx=(0, 10))
        self.steam_user_var = ctk.StringVar(value=self.cfg.get("steam_username", ""))
        ctk.CTkEntry(st_inner, textvariable=self.steam_user_var,
                     height=38, font=ctk.CTkFont(size=13)).grid(
            row=2, column=1, sticky="ew", padx=(0, 20))

        ctk.CTkLabel(st_inner, text="Password",
                     font=ctk.CTkFont(size=12), text_color="#8888aa").grid(
            row=2, column=2, sticky="w", padx=(0, 10))
        self.steam_pass_var = ctk.StringVar(value=self.cfg.get("steam_password", ""))
        self.steam_pass_entry = ctk.CTkEntry(st_inner, textvariable=self.steam_pass_var,
                                              show="•", height=38, font=ctk.CTkFont(size=13))
        self.steam_pass_entry.grid(row=2, column=3, sticky="ew")

        self._show_pass = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(st_inner, text="Show password",
                       font=ctk.CTkFont(size=12), text_color="#666677",
                       variable=self._show_pass,
                       command=lambda: self.steam_pass_entry.configure(
                           show="" if self._show_pass.get() else "•")
                       ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(10, 0))

        # Save folder card
        dir_card = ctk.CTkFrame(wrap, fg_color="#0e0e1c", corner_radius=14,
                                 border_width=1, border_color="#1a1a2c")
        dir_card.pack(fill="x", pady=(0, 24))

        dir_inner = ctk.CTkFrame(dir_card, fg_color="transparent")
        dir_inner.pack(fill="x", padx=24, pady=20)
        dir_inner.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(dir_inner, text="Manifest Save Folder",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#ffffff").grid(row=0, column=0, sticky="w", pady=(0, 4))
        ctk.CTkLabel(dir_inner, text="Where fetched ZIPs are extracted",
                     font=ctk.CTkFont(size=11), text_color="#444455").grid(
            row=1, column=0, sticky="w", pady=(0, 10))

        default_dir = self.cfg.get("manifest_save_dir",
                                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "Manifests"))
        self.save_dir_var = ctk.StringVar(value=default_dir)
        dir_row = ctk.CTkFrame(dir_inner, fg_color="transparent")
        dir_row.grid(row=2, column=0, sticky="ew")
        dir_row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(dir_row, textvariable=self.save_dir_var,
                     height=42, font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkButton(dir_row, text="Browse", width=90, height=42,
                       corner_radius=8, fg_color="#1a1a30", hover_color="#252540",
                       command=lambda: self._pick_dir_var(self.save_dir_var)).grid(row=0, column=1)

        # Clear cache button
        clear_row = ctk.CTkFrame(dir_inner, fg_color="transparent")
        clear_row.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        ctk.CTkButton(clear_row, text="🗑  Clear Manifest Cache", width=200, height=38,
                       corner_radius=8,
                       font=ctk.CTkFont(size=12, weight="bold"),
                       fg_color="#2a1515", hover_color="#3a2020",
                       text_color="#ff6b6b",
                       command=self._clear_manifest_cache).pack(side="left")
        
        self.clear_cache_status = ctk.StringVar()
        ctk.CTkLabel(clear_row, textvariable=self.clear_cache_status,
                     text_color="#666677", font=ctk.CTkFont(size=11)).pack(
            side="left", padx=(12, 0))

        # Save button
        ctk.CTkButton(wrap, text="Save Settings", width=160, height=44,
                       corner_radius=10,
                       font=ctk.CTkFont(size=13, weight="bold"),
                       command=self._save_settings).pack(
            anchor="w", pady=(0, 10))

        self.settings_status = ctk.StringVar()
        ctk.CTkLabel(wrap, textvariable=self.settings_status,
                     text_color="#4caf50", font=ctk.CTkFont(size=12)).pack(
            anchor="w")

    def _pick_dir_var(self, var):
        p = filedialog.askdirectory()
        if p: var.set(p)

    def _save_settings(self):
        self.cfg["api_key"]           = self.api_key_var.get().strip()
        self.cfg["steam_username"]    = self.steam_user_var.get().strip()
        self.cfg["steam_password"]    = self.steam_pass_var.get().strip()
        self.cfg["manifest_save_dir"] = self.save_dir_var.get().strip()
        save_config(self.cfg)
        self.settings_status.set("✓  Saved")
        self.after(2500, lambda: self.settings_status.set(""))
    
    def _clear_manifest_cache(self):
        """Delete all files in the manifest save directory."""
        manifest_dir = self.save_dir_var.get().strip()
        if not manifest_dir or not os.path.exists(manifest_dir):
            self.clear_cache_status.set("No manifest folder found")
            self.after(3000, lambda: self.clear_cache_status.set(""))
            return
        
        # Ask for confirmation
        result = messagebox.askyesno(
            "Clear Manifest Cache",
            f"This will delete all files in:\n{manifest_dir}\n\nAre you sure?",
            icon='warning'
        )
        
        if not result:
            return
        
        try:
            # Delete all files and subdirectories
            deleted_count = 0
            for root, dirs, files in os.walk(manifest_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                    deleted_count += 1
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            
            self.clear_cache_status.set(f"✓  Deleted {deleted_count} files")
            self.after(3000, lambda: self.clear_cache_status.set(""))
            
            # Also clear the game picker
            self._clear_game_picker()
            
        except Exception as e:
            self.clear_cache_status.set(f"Error: {str(e)}")
            self.after(5000, lambda: self.clear_cache_status.set(""))


# start
if __name__ == "__main__":
    app = App()
    app.mainloop()
