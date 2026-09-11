#!/bin/bash

set -euo pipefail

PYTHON=${PYTHON:-python}
BROWSER=${1:-}
BROWSER_VERSION=${2:-stable}

if [[ $# -gt 2 ]] || [[ -n "${BROWSER}" && "${BROWSER}" != "chrome" && "${BROWSER}" != "firefox" ]]; then
  echo "Usage: $0 [chrome|firefox] [browser-version]" >&2
  exit 2
fi

if ! "${PYTHON}" -c "import selenium" >/dev/null 2>&1; then
  echo "Selenium is required. Install requirements.txt before running this script." >&2
  exit 1
fi

if [[ -n "${BROWSER}" ]]; then
  BROWSERS=("${BROWSER}")
else
  BROWSERS=(chrome firefox)
fi

for browser in "${BROWSERS[@]}"; do
  "${PYTHON}" - "${browser}" "${BROWSER_VERSION}" <<'PY'
import sys

from selenium.webdriver.common.selenium_manager import SeleniumManager

browser, browser_version = sys.argv[1:]
paths = SeleniumManager().binary_paths(
    [
        "--browser",
        browser,
        "--browser-version",
        browser_version,
        "--force-browser-download",
        "--skip-browser-in-path",
        "--skip-driver-in-path",
        "--avoid-stats",
    ]
)

print(f"{browser} {browser_version} installed at {paths['browser_path']}")
print(f"Matching driver installed at {paths['driver_path']}")
PY
done
