import os
import sys
import time
import socket
import webbrowser
import multiprocessing
import tkinter as tk
from tkinter import ttk
from streamlit.web import cli as stcli


def get_resource_path(relative_path):
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, relative_path)

    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_instance:
        socket_instance.bind(("127.0.0.1", 0))
        return socket_instance.getsockname()[1]


def wait_for_server(port, timeout_seconds=45):
    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.4):
                return True
        except OSError:
            time.sleep(0.25)

    return False


def run_streamlit(app_path, port):
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.headless=true",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
        "--logger.level=error",
    ]

    stcli.main()


def terminate_process(process):
    if process and process.is_alive():
        try:
            process.terminate()
            process.join(timeout=3)
        except Exception:
            pass

        if process.is_alive():
            try:
                process.kill()
            except Exception:
                pass


def main():
    app_path = get_resource_path("app.py")
    port = find_free_port()
    url = f"http://127.0.0.1:{port}"

    streamlit_process = multiprocessing.Process(
        target=run_streamlit,
        args=(app_path, port),
    )
    streamlit_process.start()

    root = tk.Tk()
    root.title("Generátor grafov")
    root.geometry("460x230")
    root.resizable(False, False)

    def quit_app():
        terminate_process(streamlit_process)

        try:
            root.destroy()
        except Exception:
            pass

        os._exit(0)

    root.protocol("WM_DELETE_WINDOW", quit_app)

    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)

    title_label = ttk.Label(
        frame,
        text="Generátor grafov",
        font=("Arial", 18, "bold")
    )
    title_label.pack(anchor="w")

    status_label = ttk.Label(
        frame,
        text="Spúšťam lokálnu aplikáciu...",
        wraplength=390
    )
    status_label.pack(anchor="w", pady=(12, 16))

    button_frame = ttk.Frame(frame)
    button_frame.pack(anchor="w", pady=(4, 0))

    open_button = ttk.Button(
        button_frame,
        text="Otvoriť v browseri",
        command=lambda: webbrowser.open(url)
    )
    open_button.grid(row=0, column=0, padx=(0, 10))

    quit_button = ttk.Button(
        button_frame,
        text="Ukončiť aplikáciu",
        command=quit_app
    )
    quit_button.grid(row=0, column=1)

    def check_server():
        is_ready = wait_for_server(port)

        if is_ready and streamlit_process.is_alive():
            status_label.config(
                text=f"Aplikácia beží lokálne na adrese:\n{url}"
            )
            webbrowser.open(url)
        else:
            status_label.config(
                text=(
                    "Aplikáciu sa nepodarilo spustiť. "
                    "Skús ju ukončiť a spustiť znova. "
                    "Ak sa chyba opakuje, treba spraviť debug build."
                )
            )

    root.after(500, check_server)
    root.mainloop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()