#!/usr/bin/env python3
"""Generate a YASMIN benchmark application from a ros2_task_set case YAML.

Input: the exact case_*.yaml files used by the ROS 2 (CIE + SCHED_DEADLINE)
baseline in ros2_task_set. Callbacks with `period_ms` become YASMIN periodic
tasks (DAG sources); the others become non-recurring tasks fired through
YASMIN FIFO channels (one channel per `communications` edge). The callback
carrying `deadline_ms` is the DAG sink; it records the DAG response time
(sink completion time - source task start time, propagated as a channel
token) exactly like dummy_node.cpp does with the ROS 2 message stamp.

Output per case: main.c, yasmin_config.h, CMakeLists.txt.
"""

import argparse
import os
import sys

import yaml

RECORD_CAP = 65536


def load_case(path):
    with open(path) as f:
        data = yaml.safe_load(f)
    callbacks = data["callbacks"]
    communications = data.get("communications", [])

    nodes = {}
    order = []
    for cb in callbacks:
        nid = cb["id"]
        nodes[nid] = {
            "id": nid,
            "exec_ms": cb["execution_time_ms"],
            "period_ms": cb.get("period_ms"),
            "deadline_ms": cb.get("deadline_ms"),
            "in": [],   # edge order = yaml communications order (matches ROS 2)
            "out": [],
        }
        order.append(nid)

    for comm in communications:
        src, dst = comm["from"], comm["to"]
        nodes[src]["out"].append(dst)
        nodes[dst]["in"].append(src)

    # Group nodes into DAGs: a new DAG starts at each callback with period_ms
    # (same grouping rule as ros2_task_set/ActualDAGSet/convert.py).
    dags = []
    current = None
    for nid in order:
        if nodes[nid]["period_ms"] is not None:
            current = {"source": nid, "members": [], "deadline_ms": None,
                       "period_ms": nodes[nid]["period_ms"]}
            dags.append(current)
        current["members"].append(nid)
        if nodes[nid]["deadline_ms"] is not None:
            current["deadline_ms"] = nodes[nid]["deadline_ms"]

    for dag in dags:
        if dag["deadline_ms"] is None:
            dag["deadline_ms"] = dag["period_ms"]  # implicit deadline
        for nid in dag["members"]:
            nodes[nid]["dag_deadline_ms"] = dag["deadline_ms"]

    return nodes, order, dags


def gen_main_c(nodes, order, dags):
    edges = []
    for nid in order:
        for dst in nodes[nid]["out"]:
            edges.append((nid, dst))

    lines = []
    a = lines.append
    a('#include "yasmin_config.h"')
    a('#include "yasmin_api.h"')
    a('#include "yasmin_api_channels.h"')
    a("")
    a("#include <stdio.h>")
    a("#include <stdint.h>")
    a("#include <stdlib.h>")
    a("#include <string.h>")
    a("#include <time.h>")
    a("#include <errno.h>")
    a("#include <sys/stat.h>")
    a("")
    a("#define MS2NS(x) ((yas_time_t)(x) * 1000000ull)")
    a(f"#define RECORD_CAP {RECORD_CAP}")
    a("#define STAMP_NONE INT64_MIN")
    a("")
    a("static int64_t now_ns(void) {")
    a("    struct timespec ts;")
    a("    clock_gettime(CLOCK_MONOTONIC, &ts);")
    a("    return (int64_t)ts.tv_sec * 1000000000ll + (int64_t)ts.tv_nsec;")
    a("}")
    a("")
    a("/* Busy-work calibration: measure the exact volatile-increment loop that")
    a(" * dummy_work() executes (same measurement idea as dummy_node.cpp). */")
    a("static unsigned long long increments_per_ms;")
    a("")
    a("static void dummy_work(unsigned long long ms) {")
    a("    unsigned long long needed = increments_per_ms * ms;")
    a("    volatile unsigned long long count = 0;")
    a("    for (unsigned long long i = 0; i < needed; ++i) ++count;")
    a("}")
    a("")
    a("static void calibrate(void) {")
    a("    const unsigned long long n = 50000000ull;")
    a("    volatile unsigned long long count = 0;")
    a("    int64_t best = INT64_MAX;")
    a("    for (unsigned long long i = 0; i < n; ++i) ++count; /* warmup */")
    a("    for (int r = 0; r < 3; ++r) {")
    a("        int64_t t0 = now_ns();")
    a("        for (unsigned long long i = 0; i < n; ++i) ++count;")
    a("        int64_t t1 = now_ns();")
    a("        if (t1 - t0 < best) best = t1 - t0;")
    a("    }")
    a("    increments_per_ms = (unsigned long long)((double)n * 1e6 / (double)best);")
    a('    printf("calibration: %llu increments/ms (%.4f ns/increment)\\n",')
    a("           increments_per_ms, (double)best / (double)n);")
    a("    int64_t t0 = now_ns();")
    a("    dummy_work(10);")
    a("    int64_t t1 = now_ns();")
    a('    printf("calibration check: dummy_work(10 ms) took %.3f ms\\n",')
    a("           (double)(t1 - t0) / 1e6);")
    a("}")
    a("")
    a("/* one channel per DAG edge; capacity 1 token (stamp of the DAG job),")
    a(" * mirroring the depth-1 subscription queue of the ROS 2 baseline */")
    for (s, d) in edges:
        a(f"yas_channel_decl(ch_{s}_{d}, int64_t, 1)")
    a("")

    # per-node bookkeeping
    for nid in order:
        n = nodes[nid]
        a(f"static long long fire_cnt_{nid} = 0, drop_cnt_{nid} = 0;")
        if n["deadline_ms"] is not None:
            a(f"static int64_t rt_us_{nid}[RECORD_CAP];")
            a(f"static long long rt_cnt_{nid} = 0;")
    a("")

    # task functions
    for nid in order:
        n = nodes[nid]
        a(f"static void task_{nid}(void *unused) {{")
        a("    (void)unused;")
        if n["period_ms"] is not None:
            # source: chain start = own start time (ROS 2 timer callback start)
            a("    int64_t stamp = now_ns();")
        else:
            a("    int64_t stamp = STAMP_NONE;")
            a("    int64_t tmp;")
            a("    (void)tmp;")
            for i, src in enumerate(n["in"]):
                if i == 0:
                    # stamp source = first incoming edge (ROS 2 uses msg0->stamp)
                    a(f"    yas_channel_pop(ch_{src}_{nid}, stamp);")
                else:
                    a("    tmp = STAMP_NONE;")
                    a(f"    yas_channel_pop(ch_{src}_{nid}, tmp);")
            a("    if (stamp == STAMP_NONE) {")
            a("        /* spurious double activation (see y_channel_check race) */")
            a(f"        __atomic_fetch_add(&drop_cnt_{nid}, 1, __ATOMIC_RELAXED);")
            a("        return;")
            a("    }")
        a(f"    __atomic_fetch_add(&fire_cnt_{nid}, 1, __ATOMIC_RELAXED);")
        a(f"    dummy_work({n['exec_ms']});")
        for dst in n["out"]:
            a(f"    yas_channel_push(ch_{nid}_{dst}, stamp);")
        if n["deadline_ms"] is not None:
            a("    int64_t rt = (now_ns() - stamp) / 1000; /* us */")
            a(f"    long long idx = __atomic_fetch_add(&rt_cnt_{nid}, 1, __ATOMIC_RELAXED);")
            a(f"    if (idx < RECORD_CAP) rt_us_{nid}[idx] = rt;")
        a("}")
        a("")

    # CSV writer
    a("static void write_results(void) {")
    a('    mkdir("exec_time_logs", 0755);')
    for nid in order:
        n = nodes[nid]
        if n["deadline_ms"] is None:
            continue
        a("    {")
        a(f'        FILE *f = fopen("exec_time_logs/response_time_task{nid}.csv", "w");')
        a("        if (f == NULL) {")
        a(f'            perror("fopen response_time_task{nid}.csv");')
        a("        } else {")
        a('            fprintf(f, "index,response_time_us,deadline_us\\n");')
        a(f"            long long cnt = rt_cnt_{nid};")
        a("            if (cnt > RECORD_CAP) cnt = RECORD_CAP;")
        a("            for (long long i = 0; i < cnt; ++i)")
        a(f'                fprintf(f, "%lld,%lld,%lld\\n", i,')
        a(f"                        (long long)rt_us_{nid}[i],")
        a(f"                        (long long){n['deadline_ms']}000ll);")
        a("            fclose(f);")
        a(f'            printf("task {nid}: wrote %lld response times '
          f'(deadline %d ms)\\n", cnt, {n["deadline_ms"]});')
        a("        }")
        a("    }")
    a("}")
    a("")

    # main
    a("int main(int argc, char **argv) {")
    a("    int duration_s = (argc > 1) ? atoi(argv[1]) : 60;")
    a("    calibrate();")
    a("")
    a("    yas_init();")
    a("")
    a("    yas_task_data_t td;")
    for nid in order:
        a(f"    yas_task_id_t tid_{nid};")
    a("")
    for nid in order:
        n = nodes[nid]
        period = n["period_ms"] if n["period_ms"] is not None else 0
        a("    memset(&td, 0, sizeof(td));")
        a(f'    strncpy(td.name, "task_{nid}", sizeof(td.name) - 1);')
        a(f"    td.period = MS2NS({period});")
        a(f"    td.deadline = MS2NS({n['dag_deadline_ms']});")
        a(f"    tid_{nid} = yas_task_decl(&td, &task_{nid}, NULL);")
        a(f"    if (tid_{nid} < 0) {{ fprintf(stderr, \"task_decl {nid} failed\\n\"); return 1; }}")
    a("")
    for (s, d) in edges:
        a(f"    yas_channel_connect(tid_{s}, tid_{d}, ch_{s}_{d});")
    a("")
    a("    if (!yas_start()) {")
    a('        fprintf(stderr, "yas_start failed\\n");')
    a("        return 1;")
    a("    }")
    a('    printf("running for %d s ...\\n", duration_s);')
    a("    fflush(stdout);")
    a("    {")
    a("        struct timespec ts = { duration_s, 0 };")
    a("        while (nanosleep(&ts, &ts) == -1 && errno == EINTR) ;")
    a("    }")
    a("    yas_stop();")
    a("    yas_cleanup();")
    a("")
    a("    write_results();")
    for nid in order:
        a(f'    printf("task {nid}: fired %lld, dropped %lld\\n", '
          f"fire_cnt_{nid}, drop_cnt_{nid});")
    a("    return 0;")
    a("}")
    return "\n".join(lines) + "\n"


def gen_config_h(nodes, order, edges_count, local):
    n_periodic = sum(1 for nid in order if nodes[nid]["period_ms"] is not None)
    n_nonrec = len(order) - n_periodic

    lines = []
    a = lines.append
    a("#ifndef CONFIG_H")
    a("#define CONFIG_H")
    a("")
    a("#include <time.h>")
    a("#include <pthread.h>")
    a("")
    a('#include "constants.h"')
    a("")
    a("/* Raspberry Pi 4: CPU 0 = release management (scheduler thread + main),")
    a(" * CPUs 1-3 = worker threads. Mirrors the Awkernel evaluation setup. */")
    a("#define YAS_THREAD_SIZE 3")
    a("#define YAS_THREAD_AFFINITIES {1, 2, 3}")
    if local:
        a("#define YAS_THREAD_PRIORITIES {0, 0, 0}")
        a("#define YAS_THREAD_SCHED_POLICY SCHED_OTHER")
    else:
        a("#define YAS_THREAD_PRIORITIES {80, 80, 80}")
        a("#define YAS_THREAD_SCHED_POLICY SCHED_FIFO")
        a("#define YAS_MAIN_THREAD_PRIORITY 95")
        a("#define YAS_SCHEDULER_THREAD_PRIORITY 90")
    a("#define YAS_MAIN_THREAD_AFFINITY 0")
    a("#define YAS_SCHEDULER_THREAD_AFFINITY 0")
    a("")
    a(f"#define YAS_PERIODIC_TASK_SIZE {n_periodic}")
    a(f"#define YAS_NONRECURRING_TASK_SIZE {n_nonrec}")
    a("#define YAS_TASK_POOL_JOBS_SIZE 1024")
    a(f"#define YAS_CHANNEL_SIZE {edges_count}")
    a("")
    a("#define YAS_SCHEDULER_IMPLEM YAS_SCHED_IMPLEM_THR")
    a("#define YAS_TASK_MAPPING YAS_MAPPING_GLOBAL_SCHEME")
    a("#define YAS_PRIORITY_ASSIGNMENT YAS_TASK_PRIORITY_EDF")
    a("#define YAS_PREEMPTION_MODEL YAS_SCHED_PREEMPTIVE")
    a("#define YAS_TASK_RECURRING_MODEL YAS_TASK_RECMODEL_PERIODIC")
    a("")
    a("#define YAS_SYNCHRO_FORCE_POSIX")
    a("")
    a("#endif /* CONFIG_H */")
    return "\n".join(lines) + "\n"


CMAKE_TEMPLATE = """cmake_minimum_required(VERSION 3.10)

project({name} C ASM)

get_filename_component(YAS_ROOT "${{CMAKE_CURRENT_LIST_DIR}}/{rel_root}" ABSOLUTE)
set(CMAKE_MODULE_PATH ${{CMAKE_MODULE_PATH}} "${{YAS_ROOT}}/cmake/")

set(CMAKE_BUILD_TYPE "Release")
set(YAS_RUNTIME_APP_PATH "${{CMAKE_CURRENT_LIST_DIR}}")
set(YAS_CUSTOM_LIB_NAME yasmin_core_{name})

find_package(yasmin_runtime_core REQUIRED)

add_executable(yasmin_case main.c)
target_link_libraries(yasmin_case PUBLIC ${{YAS_CUSTOM_LIB_NAME}})
"""


def generate(case_path, out_dir, rel_root, local):
    nodes, order, dags = load_case(case_path)
    edges_count = sum(len(nodes[nid]["out"]) for nid in order)
    os.makedirs(out_dir, exist_ok=True)
    name = os.path.splitext(os.path.basename(case_path))[0]

    with open(os.path.join(out_dir, "main.c"), "w") as f:
        f.write(gen_main_c(nodes, order, dags))
    with open(os.path.join(out_dir, "yasmin_config.h"), "w") as f:
        f.write(gen_config_h(nodes, order, edges_count, local))
    with open(os.path.join(out_dir, "CMakeLists.txt"), "w") as f:
        f.write(CMAKE_TEMPLATE.format(name=name, rel_root=rel_root))

    sinks = [nid for nid in order if nodes[nid]["deadline_ms"] is not None]
    print(f"{case_path}: {len(order)} tasks ({len(dags)} DAGs), "
          f"{edges_count} edges, sinks={sinks} -> {out_dir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases-dir", default="../ros2/ActualDAGSet2",
                    help="directory containing TU_*/case_*.yaml")
    ap.add_argument("--out-dir", default="gen")
    ap.add_argument("--local", action="store_true",
                    help="SCHED_OTHER config for a non-root local smoke test")
    ap.add_argument("case", nargs="*",
                    help="specific case yaml paths (default: all in cases-dir)")
    args = ap.parse_args()

    base = os.path.dirname(os.path.abspath(__file__))
    if args.case:
        targets = [(os.path.abspath(c), None) for c in args.case]
    else:
        targets = []
        cases_dir = os.path.join(base, args.cases_dir)
        for tu in sorted(os.listdir(cases_dir)):
            tu_dir = os.path.join(cases_dir, tu)
            if not os.path.isdir(tu_dir):
                continue
            for y in sorted(os.listdir(tu_dir)):
                if y.startswith("case_") and y.endswith(".yaml"):
                    targets.append((os.path.join(tu_dir, y), tu))

    if not targets:
        print("no case files found", file=sys.stderr)
        sys.exit(1)

    for case_path, tu in targets:
        name = os.path.splitext(os.path.basename(case_path))[0]
        sub = os.path.join(tu, name) if tu else name
        out_dir = os.path.join(base, args.out_dir, sub)
        # gen/TU_X/case_Y -> ../../../coordinationruntime
        depth = len([p for p in sub.split(os.sep) if p]) + 1
        rel_root = "/".join([".."] * depth) + "/coordinationruntime"
        generate(case_path, out_dir, rel_root, args.local)


if __name__ == "__main__":
    main()
