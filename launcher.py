import os
import sys
import time
import socket
import threading
import webbrowser
from streamlit.web import cli as stcli


def get_resource_path(relative_path):
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, relative_path)

    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_instance:
        socket_instance.bind(("127.0.0.1", 0))
        return socket_instance.getsockname()[1]


def wait_for_server_and_open_browser(url, port):
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.25)

    webbrowser.open(url)


def main():
    app_path = get_resource_path("app.py")
    port = find_free_port()
    url = f"http://127.0.0.1:{port}"

    threading.Thread(
        target=wait_for_server_and_open_browser,
        args=(url, port),
        daemon=True
    ).start()

    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.headless=true",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false"
    ]

    stcli.main()


if __name__ == "__main__":
    main()
