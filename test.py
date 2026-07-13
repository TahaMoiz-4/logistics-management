import subprocess
import time
import ctypes
from datetime import datetime, timedelta

# =================== SETTINGS ===================
URL = "https://www.tapmad.com/watch/usa-vs-belgium-fifa-world-cup-live-free/1142851"          # the match/stream page link
KICKOFF_TIME = "05:00:00"            # 24-hour format, HH:MM:SS (e.g. 5:00 PM = 17:00:00)
OPEN_MINUTES_BEFORE = 15             # launch Edge this many minutes before kickoff
REFRESH_INTERVAL_SECONDS = 60        # how often to reload the page
REFRESH_FOR_MINUTES_AFTER = 2       # keep reloading until this many minutes after kickoff
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
# ==================================================


def wait_until(target_dt):
    while datetime.now() < target_dt:
        time.sleep(1)


def launch_edge_kiosk(url):
    """Launch Edge fullscreen in kiosk mode pointed at the URL."""
    subprocess.Popen([
        EDGE_PATH,
        f"--kiosk", url,
        "--edge-kiosk-type=fullscreen",
        "--no-first-run",
        "--noerrdialogs",
        "--disable-translate",
    ])


def reload_page():
    """Send F5 to refresh the active (kiosk) window."""
    VK_F5 = 0x74
    ctypes.windll.user32.keybd_event(VK_F5, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(VK_F5, 0, 2, 0)  # key up


def main():
    today = datetime.now().date()
    kickoff_dt = datetime.combine(today, datetime.strptime(KICKOFF_TIME, "%H:%M:%S").time())
    open_dt = kickoff_dt - timedelta(minutes=OPEN_MINUTES_BEFORE)
    stop_dt = kickoff_dt + timedelta(minutes=REFRESH_FOR_MINUTES_AFTER)

    now = datetime.now()
    if now < open_dt:
        print(f"Waiting until {open_dt.strftime('%H:%M:%S')} to launch the stream...")
        wait_until(open_dt)

    print(f"Launching Edge in kiosk mode: {URL}")
    launch_edge_kiosk(URL)

    # Give Edge a moment to open and come into focus before sending refreshes
    time.sleep(5)

    print(f"Will refresh every {REFRESH_INTERVAL_SECONDS}s until {stop_dt.strftime('%H:%M:%S')}")
    while datetime.now() < stop_dt:
        time.sleep(REFRESH_INTERVAL_SECONDS)
        print(f"Refreshing at {datetime.now().strftime('%H:%M:%S')}...")
        reload_page()

    print("Done. Stream should be live and playing — leaving it as is.")


if __name__ == "__main__":
    main()