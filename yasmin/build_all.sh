#!/bin/bash
# Build every generated YASMIN benchmark case (run WITHOUT sudo).
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GEN_DIR="${GEN_DIR:-${SCRIPT_DIR}/gen}"

if [[ ! -d "${GEN_DIR}" ]]; then
	echo "No ${GEN_DIR}; run: python3 generate_case.py" >&2
	exit 1
fi

for case_dir in "${GEN_DIR}"/TU_*/case_*; do
	echo "=== Building ${case_dir#${SCRIPT_DIR}/} ==="
	mkdir -p "${case_dir}/build"
	(cd "${case_dir}/build" && cmake .. -DCMAKE_BUILD_TYPE=Release >cmake.log 2>&1 && make 2>&1 | tail -1)
done

echo "All cases built."
