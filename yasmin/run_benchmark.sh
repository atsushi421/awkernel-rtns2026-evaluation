#!/bin/bash
# Run every built YASMIN benchmark case and collect response-time CSVs.
#
# Run as root (sudo bash run_benchmark.sh): the workers use SCHED_FIFO and the
# main/scheduler threads set real-time priorities.
#
# Results: benchmark_results/<timestamp>/TU_<tu>/case_<n>/response_time_task*.csv
# (same layout and CSV schema as ros2_task_set/run_benchmark.sh, so
# compare_response_time.ipynb / plot_comparison.py can read them directly).
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GEN_DIR="${GEN_DIR:-${SCRIPT_DIR}/gen}"
DURATION="${DURATION:-60}"
RESULT_DIR="${SCRIPT_DIR}/benchmark_results"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RESULT_FILE="${RESULT_DIR}/results_${TIMESTAMP}.txt"

if [[ "$(id -u)" -ne 0 ]]; then
	echo "This script must run as root (SCHED_FIFO + RT priorities)." >&2
	exit 1
fi

mkdir -p "${RESULT_DIR}"

# Disable RT throttling for the duration of the benchmark. SCHED_FIFO workers
# saturate CPUs 1-3 at high TU; the default 950 ms/s budget would stall them
# 50 ms every second and pollute the measurements. CPU 0 stays free for the OS
# (the YASMIN scheduler thread sleeps between releases).
OLD_RT_RUNTIME="$(sysctl -n kernel.sched_rt_runtime_us)"
sysctl -qw kernel.sched_rt_runtime_us=-1

# Pin all CPUs to the maximum frequency (equivalent to
# ros2_task_set/scripts/fix_frequencies.bash, used for the ROS 2 baseline).
# With the default ondemand/schedutil governor the busy-loop calibration and
# the actual task execution run at different frequencies, so execution times
# deviate by up to 2.5x on a Raspberry Pi 4 (600 MHz idle vs 1.5 GHz max) and
# mid-utilization cases become effectively overloaded.
declare -A OLD_GOVERNOR
for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
	[[ -f "${g}" ]] || continue
	OLD_GOVERNOR["${g}"]="$(cat "${g}")"
	echo performance > "${g}"
done
if [[ "${#OLD_GOVERNOR[@]}" -eq 0 ]]; then
	echo "[WARN] no cpufreq interface found; could not pin CPU frequency" >&2
fi

restore_sys() {
	sysctl -qw kernel.sched_rt_runtime_us="${OLD_RT_RUNTIME}"
	for g in "${!OLD_GOVERNOR[@]}"; do
		echo "${OLD_GOVERNOR[${g}]}" > "${g}" || true
	done
}
trap restore_sys EXIT

echo "=== YASMIN benchmark started at $(date) ===" | tee "${RESULT_FILE}"
echo "Duration per case: ${DURATION}s" | tee -a "${RESULT_FILE}"
echo "" | tee -a "${RESULT_FILE}"

for tu_dir in "${GEN_DIR}"/TU_*; do
	tu_name="$(basename "${tu_dir}")"
	echo "========================================" | tee -a "${RESULT_FILE}"
	echo " ${tu_name}" | tee -a "${RESULT_FILE}"
	echo "========================================" | tee -a "${RESULT_FILE}"

	for case_dir in "${tu_dir}"/case_*; do
		case_name="$(basename "${case_dir}")"
		bin="${case_dir}/build/yasmin_case"
		echo "--- ${tu_name}/${case_name} ---" | tee -a "${RESULT_FILE}"
		if [[ ! -x "${bin}" ]]; then
			echo "  [WARN] binary not found; run build_all.sh first" | tee -a "${RESULT_FILE}"
			continue
		fi

		rm -rf "${case_dir}/build/exec_time_logs"
		case_log="$(mktemp)"
		if ! (cd "${case_dir}/build" && timeout "$((DURATION + 60))" ./yasmin_case "${DURATION}") \
			> >(tee "${case_log}" -a "${RESULT_FILE}") 2>&1; then
			echo "  [WARN] run failed" | tee -a "${RESULT_FILE}"
			rm -f "${case_log}"
			continue
		fi

		# Calibration drift guard: "dummy_work(10 ms) took X ms" must stay
		# within 3% of nominal, otherwise the frequency was not stable and the
		# measured response times are unusable.
		awk '/calibration check/ { for (i = 1; i <= NF; ++i) if ($i == "took") d = $(i+1);
			if (d < 9.7 || d > 10.3) {
				printf "  [WARN] calibration drift: dummy_work(10 ms) took %s ms\n", d; exit 1
			} }' "${case_log}" | tee -a "${RESULT_FILE}" || true
		rm -f "${case_log}"

		case_result_dir="${RESULT_DIR}/${TIMESTAMP}/${tu_name}/${case_name}"
		rt_csvs=("${case_dir}"/build/exec_time_logs/response_time_task*.csv)
		if [[ -e "${rt_csvs[0]}" ]]; then
			mkdir -p "${case_result_dir}"
			cp "${case_dir}"/build/exec_time_logs/response_time_task*.csv "${case_result_dir}/"
			echo "  Response time CSVs saved to ${case_result_dir}/" | tee -a "${RESULT_FILE}"
		else
			echo "  [WARN] No response time CSVs found" | tee -a "${RESULT_FILE}"
		fi
		echo "" | tee -a "${RESULT_FILE}"
	done
done

echo "=== Benchmark finished at $(date) ===" | tee -a "${RESULT_FILE}"
echo "Results saved to: ${RESULT_DIR}/${TIMESTAMP}"
