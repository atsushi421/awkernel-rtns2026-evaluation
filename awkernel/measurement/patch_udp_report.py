"""Adds the UDP report to the measurement clone of Awkernel.

Usage: patch_udp_report.py <awkernel clone> <report.rs>
"""
import shutil
import sys

root, report_rs = sys.argv[1], sys.argv[2]


def patch(rel, old, new):
    path = f"{root}/{rel}"
    src = open(path).read()
    assert src.count(old) == 1, f"{rel}: anchor not found exactly once"
    open(path, "w").write(src.replace(old, new))


# 1. Table rows without printing them, for the UDP report.
patch(
    "awkernel_async_lib/src/task.rs",
    "    // For precision of the cycle\n    pub fn print_timestamp_table() {",
    """    /// Rows of the timestamp table as (index, DAG ID, send outer, receive outer,
    /// absolute deadline, relative deadline), with no row limit.
    pub fn timestamp_rows() -> Vec<(usize, u32, u64, u64, u64, u64)> {
        let mut node1 = MCSNode::new();
        let mut node2 = MCSNode::new();
        let mut node3 = MCSNode::new();
        let mut node4 = MCSNode::new();
        let send_outer_opt = SEND_OUTER_TIMESTAMP.lock(&mut node1);
        let recv_outer_opt = RECV_OUTER_TIMESTAMP.lock(&mut node2);
        let absolute_deadline_opt = ABSOLUTE_DEADLINE.lock(&mut node3);
        let relative_deadline_opt = RELATIVE_DEADLINE.lock(&mut node4);
        let get = |table: &Option<Box<DagTimestampTable>>, i: usize, dag_id: u32| -> u64 {
            table
                .as_ref()
                .and_then(|arr| arr[i].get(&dag_id).copied())
                .unwrap_or(0)
        };

        let mut rows = Vec::new();
        for i in 0..MAX_LOGS {
            let mut dag_ids = Vec::new();
            for table in [
                &*send_outer_opt,
                &*recv_outer_opt,
                &*absolute_deadline_opt,
                &*relative_deadline_opt,
            ] {
                if let Some(arr) = table {
                    dag_ids.extend(arr[i].keys().copied());
                }
            }
            dag_ids.sort_unstable();
            dag_ids.dedup();
            for dag_id in dag_ids {
                let row = (
                    i,
                    dag_id,
                    get(&*send_outer_opt, i, dag_id),
                    get(&*recv_outer_opt, i, dag_id),
                    get(&*absolute_deadline_opt, i, dag_id),
                    get(&*relative_deadline_opt, i, dag_id),
                );
                if row.2 != 0 || row.3 != 0 || row.4 != 0 || row.5 != 0 {
                    rows.push(row);
                }
            }
        }
        rows
    }

    // For precision of the cycle
    pub fn print_timestamp_table() {""",
)

# 2. Stop the simulated load once the table is taken.
patch(
    "applications/rd_gen_to_dags/src/time_unit.rs",
    """#[cfg(feature = "milliseconds")]
pub(super) fn simulated_execution_time(duration: u64) {
    wait_millisec(duration);
}""",
    """#[cfg(feature = "milliseconds")]
pub(super) fn simulated_execution_time(duration: u64) {
    if !crate::report::STOP.load(core::sync::atomic::Ordering::Relaxed) {
        wait_millisec(duration);
    }
}""",
)

# 3. Network setup before the DAGs, the report after them.
lib = "applications/rd_gen_to_dags/src/lib.rs"
patch(lib, "mod time_unit;\n", "mod report;\nmod time_unit;\n")
patch(
    lib,
    "    wait_millisec(1000);\n",
    "    wait_millisec(1000);\n\n    let iface = report::setup_network();\n    report::hello(iface).await;\n",
)
patch(
    lib,
    '            log::info!("DAGs created successfully.");\n',
    '            log::info!("DAGs created successfully.");\n'
    "            awkernel_async_lib::spawn(\n"
    '                "udp report".into(),\n'
    "                report::report(iface),\n"
    "                SchedulerType::GEDF(1_000),\n"
    "            )\n"
    "            .await;\n",
)
shutil.copy(report_rs, f"{root}/applications/rd_gen_to_dags/src/report.rs")

# 4. No UART table print: CPU 0 would stall timers for about 35 s.
patch(
    "kernel/src/main.rs",
    "const PERF_PRINT_INTERVAL_SECS: u64 = 30;",
    "const PERF_PRINT_INTERVAL_SECS: u64 = 1_000_000;",
)
print("patched")
