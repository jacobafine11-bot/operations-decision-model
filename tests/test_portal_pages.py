"""Execute every portal page through Streamlit's AppTest and fail on any
exception or error box. Run from the repository root:
    python tests/test_portal_pages.py
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portal"))

from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = ["views/home.py", "views/is2.py", "views/workbench.py", "views/mock.py", "views/sim_lab.py",
         "views/stats_lab.py", "views/benchmark.py", "views/journal.py", "views/real_data.py",
         "views/verification.py", "views/pipeline.py", "views/docs.py"]


def main() -> int:
    failures = 0
    for page in PAGES:
        t = time.time()
        at = AppTest.from_file(str(ROOT / "portal" / "app.py"), default_timeout=180)
        at.run()
        at.switch_page(page)
        at.run()
        # A red box that states a recorded test verdict is content, not a bug.
        errs = [e.value for e in at.error if not str(e.value).startswith("**Verdict")]
        ok = not at.exception and not errs
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {page:<24} {time.time() - t:5.1f}s  "
              f"{len(at.markdown)} text blocks, {len(at.dataframe)} tables"
              + ("" if ok else f"\n      exception: {at.exception}\n      errors: {errs}"))
    print(f"{len(PAGES) - failures}/{len(PAGES)} pages render cleanly")

    # Buttons that run real work.
    for page, label, expect in [("views/mock.py", "Run the check", "Model promised"),
                                ("views/verification.py", "Run all checks now", "checks passed")]:
        at = AppTest.from_file(str(ROOT / "portal" / "app.py"), default_timeout=300)
        at.run()
        at.switch_page(page)
        at.run()
        btn = [b for b in at.button if b.label == label][0]
        btn.click().run()
        texts = [m.label for m in at.metric] + [s.value for s in at.success] + [w.value for w in at.warning]
        ok = not at.exception and any(expect in str(t) for t in texts)
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  button '{label}' on {page}"
              + ("" if ok else f": exception={at.exception} texts={texts[:4]}"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
