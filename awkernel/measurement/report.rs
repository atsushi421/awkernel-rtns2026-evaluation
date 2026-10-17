//! Sends the DAG timestamp table to the PC over UDP, because the measurement
//! board has no UART connection.
//!
//! The PC receives every datagram on `PORT`. Rows use the format of
//! `print_timestamp_table()`, so `aw_log_to_csv.py` converts them unchanged.

use alloc::{format, string::String, vec::Vec};
use awkernel_async_lib::net::{
    udp::{UdpConfig, UdpSocket},
    IpAddr,
};
use core::{
    sync::atomic::{AtomicBool, Ordering},
    time::Duration,
};

/// Once set, the subtasks skip their simulated execution time, so the
/// network service tasks get CPU time again after the measurement.
pub static STOP: AtomicBool = AtomicBool::new(false);

const PORT: u16 = 26099;
const MAX_DATAGRAM: usize = 1200;
const ROUNDS: usize = 3;

pub fn setup_network() -> u64 {
    let id = awkernel_lib::net::get_all_interface()
        .first()
        .map(|s| s.interface_id)
        .unwrap_or(0);
    awkernel_lib::net::add_ipv4_addr(id, crate::IFACE_ADDR, 24);
    id
}

fn bind(id: u64) -> Option<UdpSocket> {
    match UdpSocket::bind_on_interface(
        id,
        &UdpConfig {
            addr: IpAddr::new_v4(crate::IFACE_ADDR),
            ..Default::default()
        },
    ) {
        Ok(socket) => Some(socket),
        Err(e) => {
            log::error!("report: bind failed: {e:?}");
            None
        }
    }
}

async fn send(socket: &mut UdpSocket, text: &str) {
    let dst = IpAddr::new_v4(crate::DEST_ADDR);
    if let Err(e) = socket.send(text.as_bytes(), &dst, PORT).await {
        log::error!("report: send failed: {e:?}");
    }
}

fn link(id: u64) -> String {
    match awkernel_lib::net::get_interface(id) {
        Ok(s) => format!("{} {:?} {}Mbps", s.device_name, s.link_status, s.link_speed_mbs),
        Err(_) => String::from("no interface"),
    }
}

/// Tells the PC that the board booted, before the DAGs start.
pub async fn hello(id: u64) {
    let Some(mut socket) = bind(id) else {
        return;
    };
    for i in 0..5 {
        let msg = format!("#HELLO TU={} try={i} if={id} {}\n", crate::TU, link(id));
        log::info!("{}", msg.trim_end());
        send(&mut socket, &msg).await;
        awkernel_async_lib::sleep(Duration::from_secs(1)).await;
    }
}

fn ts(v: u64) -> String {
    if v == 0 {
        String::from("-")
    } else {
        format!("{v}")
    }
}

/// Waits for the measurement window, takes the table, stops the load, and
/// sends the table `ROUNDS` times.
pub async fn report(id: u64) {
    let Some(mut socket) = bind(id) else {
        return;
    };
    send(&mut socket, &format!("#DAGS TU={}\n", crate::TU)).await;

    awkernel_async_lib::sleep(Duration::from_secs(crate::MEASURE_SECS)).await;
    let rows = awkernel_async_lib::task::perf::timestamp_rows();
    STOP.store(true, Ordering::Relaxed);
    log::info!("report: {} rows", rows.len());
    awkernel_async_lib::sleep(Duration::from_secs(2)).await;

    let mut datagrams: Vec<String> = Vec::new();
    let mut cur = String::new();
    for &(i, dag_id, send_outer, recv_outer, abs, rel) in rows.iter() {
        let latency = if send_outer != 0 && recv_outer != 0 {
            format!("{}", recv_outer.saturating_sub(send_outer))
        } else {
            String::from("-")
        };
        let line = format!(
            "{i} | {dag_id} | {} | {} | {latency} | {} | {}\n",
            ts(send_outer),
            ts(recv_outer),
            ts(abs),
            ts(rel)
        );
        if cur.len() + line.len() > MAX_DATAGRAM {
            datagrams.push(core::mem::take(&mut cur));
        }
        cur.push_str(&line);
    }
    if !cur.is_empty() {
        datagrams.push(cur);
    }

    let total = datagrams.len();
    for round in 0..ROUNDS {
        let header = format!(
            "#BEGIN TU={} rows={} datagrams={total} round={round}\n",
            crate::TU,
            rows.len()
        );
        send(&mut socket, &header).await;
        for (seq, body) in datagrams.iter().enumerate() {
            send(&mut socket, &format!("#SEQ {seq}/{total}\n{body}")).await;
            awkernel_async_lib::sleep(Duration::from_millis(2)).await;
        }
        send(&mut socket, &format!("#END TU={} round={round}\n", crate::TU)).await;
        awkernel_async_lib::sleep(Duration::from_secs(1)).await;
    }
    log::info!("report: sent {total} datagrams x {ROUNDS}");
}
