"""The deployable site must stay in sync and stay self-contained.

`/index.html` is what GitHub Pages serves; `website/index.html` is the copy kept in an
obvious place for a manual upload. If they drift, someone ships a stale landing page.
"""
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parent.parent
ROOT_PAGE = REPO / "index.html"
WEBSITE_PAGE = REPO / "website" / "index.html"


def test_both_copies_exist():
    assert ROOT_PAGE.is_file(), "repo-root index.html is what GitHub Pages serves"
    assert WEBSITE_PAGE.is_file(), "website/index.html is the copy to upload manually"


def test_copies_are_byte_identical():
    root = ROOT_PAGE.read_bytes()
    site = WEBSITE_PAGE.read_bytes()
    assert root == site, (
        "index.html and website/index.html have drifted "
        f"({len(root)} vs {len(site)} bytes). Re-sync with: cp index.html website/index.html"
    )


def test_page_is_self_contained():
    """No external resources — the uploaded file must work on its own."""
    html = ROOT_PAGE.read_text(encoding="utf-8")
    external_src = re.findall(r'src\s*=\s*["\'](?!data:)(?:https?:)?//[^"\']*', html)
    assert not external_src, f"page loads off-origin resources: {external_src}"
    assert "@import" not in html
    assert not re.search(r'url\(\s*["\']?https?:', html), "CSS pulls a remote url()"


def test_hero_screenshot_is_embedded():
    html = ROOT_PAGE.read_text(encoding="utf-8")
    assert "data:image/webp;base64," in html, "hero screenshot should be inlined"


def test_page_points_at_the_repo_and_the_licence():
    html = ROOT_PAGE.read_text(encoding="utf-8")
    assert "github.com/titusblair/argybargy" in html
    assert "MIT" in html


def test_nojekyll_present_so_pages_serves_files_as_is():
    assert (REPO / ".nojekyll").is_file(), "GitHub Pages would otherwise run Jekyll"
