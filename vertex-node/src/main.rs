use std::net::{IpAddr, Ipv4Addr, SocketAddr};
use std::sync::Arc;

use tokio::sync::RwLock;
use vertex_node::{
    create_app, run_eviction, run_heartbeat, run_multicast_listener, run_stdin_relay,
    run_udp_listener, AppState, PeerRegistry,
};

const MULTICAST_ADDR: Ipv4Addr = Ipv4Addr::new(239, 255, 0, 1);
const MULTICAST_PORT: u16 = 9001;

#[tokio::main]
async fn main() {
    let args: Vec<String> = std::env::args().collect();
    let mut seed_peers: Vec<SocketAddr> = Vec::new();
    let mut bind_port: u16 = 9000;
    let mut ttl_secs: u64 = 30;
    let mut http_port: u16 = 9002;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--peer" if i + 1 < args.len() => {
                if let Ok(addr) = args[i + 1].parse::<SocketAddr>() {
                    seed_peers.push(addr);
                }
                i += 2;
            }
            "--port" if i + 1 < args.len() => {
                bind_port = args[i + 1].parse().unwrap_or(9000);
                i += 2;
            }
            "--ttl" if i + 1 < args.len() => {
                ttl_secs = args[i + 1].parse().unwrap_or(30);
                i += 2;
            }
            "--http-port" if i + 1 < args.len() => {
                http_port = args[i + 1].parse().unwrap_or(9002);
                i += 2;
            }
            "--keypair" => {
                i += 2;
            }
            _ => {
                i += 1;
            }
        }
    }

    let secret = std::env::var("VERTEX_SECRET")
        .or_else(|_| std::env::var("ENTROPYHUNT_MESH_SECRET"))
        .unwrap_or_default();

    let registry = Arc::new(RwLock::new(PeerRegistry::new(ttl_secs)));
    let messages_relayed = Arc::new(RwLock::new(0u64));

    for p in &seed_peers {
        registry.write().await.register(p.to_string());
    }

    let std_sock = std::net::UdpSocket::bind(SocketAddr::new(
        IpAddr::V4(Ipv4Addr::UNSPECIFIED),
        bind_port,
    ))
    .expect("bind main socket failed");
    std_sock
        .set_nonblocking(true)
        .expect("set main socket nonblocking failed");
    let sock = Arc::new(
        tokio::net::UdpSocket::from_std(std_sock).expect("convert main socket to tokio failed"),
    );

    let std_mc = std::net::UdpSocket::bind(SocketAddr::new(
        IpAddr::V4(Ipv4Addr::UNSPECIFIED),
        MULTICAST_PORT,
    ))
    .expect("bind multicast socket failed");
    std_mc
        .join_multicast_v4(&MULTICAST_ADDR, &Ipv4Addr::UNSPECIFIED)
        .expect("join multicast failed");
    std_mc
        .set_nonblocking(true)
        .expect("set multicast socket nonblocking failed");
    let mc_sock = Arc::new(
        tokio::net::UdpSocket::from_std(std_mc).expect("convert multicast socket to tokio failed"),
    );

    let hello = format!(r#"{{"type":"HELLO","port":{}}}"#, bind_port);
    let _ = mc_sock
        .send_to(
            hello.as_bytes(),
            SocketAddr::new(IpAddr::V4(MULTICAST_ADDR), MULTICAST_PORT),
        )
        .await;

    println!("[EVENT] READY");

    let state = AppState {
        registry: Arc::clone(&registry),
        messages_relayed: Arc::clone(&messages_relayed),
        secret: secret.clone(),
    };

    let app = create_app(state);

    let http_listener = tokio::net::TcpListener::bind(format!("0.0.0.0:{}", http_port))
        .await
        .expect("bind HTTP listener failed");

    let http_task = tokio::spawn(async move {
        axum::serve(http_listener, app)
            .await
            .expect("HTTP server failed");
    });

    let heartbeat_task = tokio::spawn(run_heartbeat());

    let eviction_task = tokio::spawn(run_eviction(Arc::clone(&registry), ttl_secs));

    let stdin_task = tokio::spawn(run_stdin_relay(
        Arc::clone(&sock),
        Arc::clone(&mc_sock),
        Arc::clone(&registry),
        Arc::clone(&messages_relayed),
        secret.clone(),
    ));

    let udp_task = tokio::spawn(run_udp_listener(
        Arc::clone(&sock),
        Arc::clone(&registry),
        secret.clone(),
    ));

    let mc_task = tokio::spawn(run_multicast_listener(
        Arc::clone(&mc_sock),
        Arc::clone(&registry),
    ));

    let _ = tokio::join!(
        http_task,
        heartbeat_task,
        eviction_task,
        stdin_task,
        udp_task,
        mc_task
    );
}
