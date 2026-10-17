"""Move the sink's end timestamp after f(args), so that the recorded latency
runs from the source start to the sink completion, as in the 2/27 data and
in the ROS 2 and YASMIN baselines."""
import sys

path = sys.argv[1]
src = open(path).read()
old = """                let timenow = awkernel_lib::time::Time::now().uptime().as_nanos() as u64;
                if period_index != 0 {
                    update_cycle_end_timestamp(period_index as usize, timenow, dag_info.dag_id);
                }

                if dag.has_stale_deadline(node_idx) {
                    crate::r#yield().await;
                }

                f(args);
            }
"""
new = """                if dag.has_stale_deadline(node_idx) {
                    crate::r#yield().await;
                }

                f(args);

                // The response time ends when the sink finishes.
                let timenow = awkernel_lib::time::Time::now().uptime().as_nanos() as u64;
                if period_index != 0 {
                    update_cycle_end_timestamp(period_index as usize, timenow, dag_info.dag_id);
                }
            }
"""
assert src.count(old) == 1, "sink block not found exactly once"
open(path, "w").write(src.replace(old, new))
