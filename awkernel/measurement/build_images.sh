#!/bin/bash
# Builds measurement images of the fixed GEDF scheduler of Awkernel
# (tier4/awkernel commit abbd2095, PR #715). Each image runs one DAG
# set of the RTNS 2026 response-time comparison and sends the DAG timestamp
# table to the PC over UDP, so that no UART connection is needed.
#
#   bash build_images.sh        five Raspberry Pi 4 images, one per DAG set
#   bash build_images.sh qemu   one QEMU aarch64 virt image for testing
#
# Environment variables:
#   AWKERNEL_REPO  repository to clone (default: tier4/awkernel on GitHub)
#   COMMIT         commit to build (default: abbd2095). The images of the paper
#                  used commit 6243e474 of the fork atsushi421/awkernel, which
#                  differs from abbd2095 only in the panic messages of dag.rs.
#   WORK           work directory (default: ./work next to this script)
#   OBJCOPY        objcopy for the raw image (default: llvm-objcopy-18)
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
MODE=${1:-raspi}
AWKERNEL_REPO=${AWKERNEL_REPO:-https://github.com/tier4/awkernel.git}
COMMIT=${COMMIT:-abbd2095}
WORK=${WORK:-$HERE/work}
SRC=$WORK/awkernel
OUT=$WORK/images
OBJCOPY=${OBJCOPY:-llvm-objcopy-18}
D=$(cd "$HERE/../../dags" && pwd)

# TU label -> the three RD-Gen DAGs of case_1..5 (the sets of ROS 2 and YASMIN)
declare -A SETS=(
    [10]="TU=0.4/DAGs/dag_0 TU=0.3/DAGs/dag_0 TU=0.3/DAGs/dag_3"
    [15]="TU=0.5/DAGs/dag_0 TU=0.5/DAGs/dag_7 TU=0.5/DAGs/dag_8"
    [20]="TU=1/DAGs/dag_0 TU=0.5/DAGs/dag_0 TU=0.5/DAGs/dag_7"
    [25]="TU=1/DAGs/dag_0 TU=1/DAGs/dag_2 TU=0.5/DAGs/dag_0"
    [30]="TU=1/DAGs/dag_0 TU=1/DAGs/dag_1 TU=1/DAGs/dag_2"
)

if [ "$MODE" = qemu ]; then
    BSP=aarch64_virt FEAT=aarch64_virt TUS="10" SECS=15
    IFACE="10, 0, 2, 64" DEST="10, 0, 2, 2"
else
    BSP=raspi4 FEAT=raspi TUS="10 15 20 25 30" SECS=90
    IFACE="192, 168, 77, 2" DEST="192, 168, 77, 1"
fi

mkdir -p "$WORK"
[ -d "$SRC" ] || git clone --quiet "$AWKERNEL_REPO" "$SRC"
cd "$SRC"
git cat-file -e "$COMMIT^{commit}" 2>/dev/null || git fetch --quiet origin
git checkout --quiet --force "$COMMIT"
git checkout --quiet -- .
rm -f applications/rd_gen_to_dags/src/report.rs
echo "source: $(git log -1 --format='%h %s')"

LIB=applications/rd_gen_to_dags/src/lib.rs
sed -i 's/^default = \[\]$/default = ["rd_gen_to_dags"]/' userland/Cargo.toml
sed -i 's/^    SchedulerType::PrioritizedFIFO(0)$/    SchedulerType::GEDF(0)/' $LIB
sed -i 's|let dag_files = \[/\*DAG_FILE_0, DAG_FILE_1\*/\];|let dag_files = [DAG_FILE_0, DAG_FILE_1, DAG_FILE_2];|' $LIB
grep -q 'default = \["rd_gen_to_dags"\]' userland/Cargo.toml
grep -q 'SchedulerType::GEDF(0)' $LIB
grep -q 'let dag_files = \[DAG_FILE_0, DAG_FILE_1, DAG_FILE_2\];' $LIB
python3 "$HERE/patch_sink_end.py" awkernel_async_lib/src/dag.rs
python3 "$HERE/patch_udp_report.py" . "$HERE/report.rs"
cp $LIB $LIB.base

mkdir -p "$OUT"
for tu in $TUS; do
    read -r f0 f1 f2 <<< "${SETS[$tu]}"
    # Appended, because #![no_std] must stay the first line of lib.rs
    {
        cat $LIB.base
        echo "const DAG_FILE_0: &str = concat!(include_str!(\"$D/$f0.yaml\"), \"\\n\");"
        echo "const DAG_FILE_1: &str = concat!(include_str!(\"$D/$f1.yaml\"), \"\\n\");"
        echo "const DAG_FILE_2: &str = concat!(include_str!(\"$D/$f2.yaml\"), \"\\n\");"
        echo "const TU: &str = \"$tu\";"
        echo "const IFACE_ADDR: core::net::Ipv4Addr = core::net::Ipv4Addr::new($IFACE);"
        echo "const DEST_ADDR: core::net::Ipv4Addr = core::net::Ipv4Addr::new($DEST);"
        echo "const MEASURE_SECS: u64 = $SECS;"
    } > $LIB
    log="$OUT/build_${MODE}_TU$tu.log"
    # make keeps an old link script across BSPs, and its load address differs per BSP
    rm -f kernel/ld/aarch64-link-bsp.lds
    # The ELF is built by make and converted here, because rust-objcopy of the
    # nightly toolchain may fail to load its LLVM library.
    make target/aarch64-kernel/release/awkernel BSP=$BSP RELEASE=1 \
        AARCH64_OPT="--release --features $FEAT,period-index-propagation" > "$log" 2>&1 \
        || { tail -40 "$log"; exit 1; }
    name=kernel8_TU$tu.img
    [ "$MODE" = qemu ] && name=kernel8_qemu_TU$tu.img
    "$OBJCOPY" -O binary target/aarch64-kernel/release/awkernel "$OUT/$name"
    echo "TU=$tu ($f0 $f1 $f2) -> $OUT/$name"
done
