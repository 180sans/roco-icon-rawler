"""Entry point for the standalone Windows GUI executable."""
import sys


def main():
    if "--smoke-test" in sys.argv:
        # Verify the bundled runtime without network access or showing a window.
        from io import BytesIO
        from pathlib import Path
        import tkinter as tk
        from unittest.mock import patch
        import ssl
        import requests
        from bs4 import BeautifulSoup
        from PIL import Image
        from crawler import DEFAULT_OUTPUT
        from gui import App

        assert BeautifulSoup("<p>OK</p>", "html.parser").p.text == "OK"
        buffer = BytesIO()
        Image.new("RGBA", (2, 2), (255, 0, 0, 0)).save(buffer, format="PNG")
        buffer.seek(0)
        with Image.open(buffer) as image:
            image.verify()
        ssl.create_default_context(cafile=requests.certs.where())
        root = tk.Tk()
        root.withdraw()
        with patch.object(App, "load"):
            app = App(root, DEFAULT_OUTPUT)
        root.update_idletasks()
        assert app.output.get() == str(DEFAULT_OUTPUT)
        assert app.page_scrollbar.winfo_exists()
        root.destroy()
        if getattr(sys, "frozen", False):
            assert DEFAULT_OUTPUT == Path(sys.executable).resolve().parent
        return 0

    from gui import run_gui
    run_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
