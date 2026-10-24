"""GUI tests: skipped automatically when there is no display (e.g. a headless server)."""

import shutil

import pytest

tk = pytest.importorskip("tkinter")


@pytest.fixture
def root():
    try:
        window = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    window.withdraw()
    yield window
    window.destroy()


def test_window_is_fixed_size_and_fits_content(root, tmp_path):
    from mosaik.gui.app import MosaikApp

    app = MosaikApp(root)
    root.update()
    assert root.resizable() == (0, 0)
    assert int(root.geometry().split("x")[1].split("+")[0]) >= root.winfo_reqheight()
    assert app.status.get().startswith("Add a few")


def test_add_files_and_folders_and_skip_unsupported(root, tmp_path, face_jpg):
    from mosaik.gui.app import MosaikApp

    folder = tmp_path / "album"
    (folder / "sub").mkdir(parents=True)
    shutil.copy(face_jpg, folder / "a.jpg")
    shutil.copy(face_jpg, folder / "sub" / "b.JPG")
    (folder / "notes.txt").write_text("x")
    app = MosaikApp(root)
    app.add_paths([str(folder), str(folder / "a.jpg"), str(folder / "notes.txt")])
    assert len(app.files) == 2          # recursive, de-duplicated, .txt ignored
    assert "unsupported" in app.status.get()
    app.clear_files()
    assert app.files == []


def test_builtin_browser_lists_filters_and_returns_selection(root, tmp_path, face_jpg):
    from mosaik.gui.filepicker import FILTER_ALL, FileBrowser

    (tmp_path / "folder").mkdir()
    (tmp_path / ".hidden.jpg").write_bytes(b"x")
    shutil.copy(face_jpg, tmp_path / "photo.jpg")
    (tmp_path / "notes.txt").write_text("x")

    browser = FileBrowser(root, "Test", "files", start=tmp_path, modal=False)
    names = [browser.tree.item(i, "text") for i in browser.tree.get_children()]
    assert names == ["folder/", "photo.jpg"]          # folders first, no hidden, no .txt

    browser.kind_filter.set(FILTER_ALL)
    browser._refresh()
    assert "notes.txt" in [browser.tree.item(i, "text") for i in browser.tree.get_children()]

    browser.tree.selection_set(str(tmp_path / "photo.jpg"))
    browser._accept()
    assert browser.result == [str(tmp_path / "photo.jpg")]


def test_builtin_browser_folder_mode_and_navigation(root, tmp_path):
    from mosaik.gui.filepicker import FileBrowser

    (tmp_path / "inner").mkdir()
    browser = FileBrowser(root, "Test", "dir", start=tmp_path, modal=False)
    browser._go(tmp_path / "inner")
    assert browser.cwd == tmp_path / "inner"
    browser.go_up()
    assert browser.cwd == tmp_path
    browser.tree.selection_set(str(tmp_path / "inner"))
    browser._accept()
    assert browser.result == [str(tmp_path / "inner")]
