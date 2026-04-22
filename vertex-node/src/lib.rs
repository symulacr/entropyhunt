use std::collections::{BTreeMap, HashMap};
use std::net::{IpAddr, Ipv4Addr, SocketAddr};
use std::sync::Arc;
use std::time::{Duration, Instant};

use axum::{
    extract::State,
    response::{IntoResponse, Json},
    routing::{get, post},
    Router,
};
use hmac::{Hmac, Mac};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::Sha256;
use tokio::io::AsyncBufReadExt;
use tokio::sync::RwLock;

pub type HmacSha256 = Hmac<Sha256>;

#[derive(Debug, thiserror::Error)]
pub enum VertexNodeError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),
    #[error("HMAC error: {0}")]
    Hmac(String),
}

impl IntoResponse for VertexNodeError {
    fn into_response(self) -> axum::response::Response {
        let body = Json(serde_json::json!({"error": self.to_string()}));
        (axum::http::StatusCode::INTERNAL_SERVER_ERROR, body).into_response()
    }
}

pub struct PeerRegistry {
    peers: HashMap<String, Instant>,
    ttl: Duration,
}

impl PeerRegistry {
    pub fn new(ttl_secs: u64) -> Self {
        Self {
            peers: HashMap::new(),
            ttl: Duration::from_secs(ttl_secs),
        }
    }

    pub fn register(&mut self, peer_id: impl Into<String>) {
        self.peers.insert(peer_id.into(), Instant::now());
    }

    pub fn evict_stale(&mut self) {
        let now = Instant::now();
        self.peers
            .retain(|_, last_seen| now.duration_since(*last_seen) < self.ttl);
    }

    pub fn peers(&self) -> Vec<(String, u64)> {
        let now = Instant::now();
        self.peers
            .iter()
            .map(|(id, last_seen)| {
                let elapsed = now.duration_since(*last_seen).as_secs();
                (id.clone(), elapsed)
            })
            .collect()
    }

    pub fn len(&self) -> usize {
        self.peers.len()
    }

    pub fn is_empty(&self) -> bool {
        self.peers.is_empty()
    }
}

fn sort_json_value(value: &Value) -> Value {
    match value {
        Value::Object(map) => {
            let mut btree: BTreeMap<String, Value> = BTreeMap::new();
            for (k, v) in map.iter() {
                btree.insert(k.clone(), sort_json_value(v));
            }
            let sorted_map: serde_json::Map<String, Value> = btree.into_iter().collect();
            Value::Object(sorted_map)
        }
        Value::Array(arr) => Value::Array(arr.iter().map(sort_json_value).collect()),
        other => other.clone(),
    }
}

fn canonical_json(value: &Value) -> String {
    let sorted = sort_json_value(value);
    serde_json::to_string(&sorted).expect("serialize JSON value")
}

pub fn sign_envelope(
    topic: &str,
    sender_id: &str,
    message_id: &str,
    timestamp_ms: i64,
    payload: &Value,
    secret: &str,
) -> Result<String, VertexNodeError> {
    let payload_json = canonical_json(payload);
    let data = format!(
        "{}:{}:{}:{}:{}",
        topic, sender_id, message_id, timestamp_ms, payload_json
    );
    let mut mac = HmacSha256::new_from_slice(secret.as_bytes())
        .map_err(|e| VertexNodeError::Hmac(format!("{}", e)))?;
    mac.update(data.as_bytes());
    let result = mac.finalize();
    Ok(hex::encode(result.into_bytes()))
}

pub fn verify_envelope(
    topic: &str,
    sender_id: &str,
    message_id: &str,
    timestamp_ms: i64,
    payload: &Value,
    sig: &str,
    secret: &str,
) -> bool {
    if secret.is_empty() {
        return true;
    }
    if sig.is_empty() {
        return false;
    }
    let expected = match sign_envelope(topic, sender_id, message_id, timestamp_ms, payload, secret) {
        Ok(s) => s,
        Err(_) => return false,
    };
    if sig.len() != expected.len() {
        return false;
    }
    let mut diff = 0u8;
    for (a, b) in sig.bytes().zip(expected.bytes()) {
        diff |= a ^ b;
    }
    diff == 0
}

#[derive(Clone)]
pub struct AppState {
    pub registry: Arc<RwLock<PeerRegistry>>,
    pub messages_relayed: Arc<RwLock<u64>>,
    pub secret: String,
}

#[derive(Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub peers: usize,
}

pub async fn health_handler(State(state): State<AppState>) -> Json<HealthResponse> {
    let registry = state.registry.read().await;
    Json(HealthResponse {
        status: "ok".to_string(),
        peers: registry.len(),
    })
}

#[derive(Serialize)]
pub struct PeerInfo {
    pub id: String,
    pub last_seen_secs: u64,
}

pub async fn peers_handler(State(state): State<AppState>) -> Json<Vec<PeerInfo>> {
    let registry = state.registry.read().await;
    let peers = registry
        .peers()
        .into_iter()
        .map(|(id, elapsed)| PeerInfo {
            id,
            last_seen_secs: elapsed,
        })
        .collect();
    Json(peers)
}

#[derive(Serialize)]
pub struct MetricsResponse {
    pub messages_relayed: u64,
}

pub async fn metrics_handler(State(state): State<AppState>) -> Json<MetricsResponse> {
    let count = *state.messages_relayed.read().await;
    Json(MetricsResponse {
        messages_relayed: count,
    })
}

#[derive(Deserialize)]
pub struct HmacSignRequest {
    pub topic: String,
    pub sender_id: String,
    pub message_id: String,
    pub timestamp_ms: i64,
    pub payload: Value,
    pub secret: String,
}

#[derive(Serialize)]
pub struct HmacSignResponse {
    pub signature: String,
}

pub async fn hmac_sign_handler(
    Json(req): Json<HmacSignRequest>,
) -> Result<Json<HmacSignResponse>, VertexNodeError> {
    let sig = sign_envelope(
        &req.topic,
        &req.sender_id,
        &req.message_id,
        req.timestamp_ms,
        &req.payload,
        &req.secret,
    )?;
    Ok(Json(HmacSignResponse { signature: sig }))
}

#[derive(Deserialize)]
pub struct HmacVerifyRequest {
    pub topic: String,
    pub sender_id: String,
    pub message_id: String,
    pub timestamp_ms: i64,
    pub payload: Value,
    pub signature: String,
    pub secret: String,
}

#[derive(Serialize)]
pub struct HmacVerifyResponse {
    pub valid: bool,
}

pub async fn hmac_verify_handler(
    Json(req): Json<HmacVerifyRequest>,
) -> Json<HmacVerifyResponse> {
    let valid = verify_envelope(
        &req.topic,
        &req.sender_id,
        &req.message_id,
        req.timestamp_ms,
        &req.payload,
        &req.signature,
        &req.secret,
    );
    Json(HmacVerifyResponse { valid })
}

pub fn create_app(state: AppState) -> Router {
    Router::new()
        .route("/health", get(health_handler))
        .route("/peers", get(peers_handler))
        .route("/metrics", get(metrics_handler))
        .route("/hmac/sign", post(hmac_sign_handler))
        .route("/hmac/verify", post(hmac_verify_handler))
        .with_state(state)
}

pub async fn run_heartbeat() {
    let mut interval = tokio::time::interval(Duration::from_secs(5));
    loop {
        interval.tick().await;
        let ts = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("time went backwards")
            .as_secs();
        println!(r#"{{"type":"HEARTBEAT","timestamp":{}}}"#, ts);
    }
}

pub async fn run_eviction(registry: Arc<RwLock<PeerRegistry>>, ttl_secs: u64) {
    let interval_secs = if ttl_secs <= 5 { 1 } else { 5 };
    let mut interval = tokio::time::interval(Duration::from_secs(interval_secs));
    loop {
        interval.tick().await;
        registry.write().await.evict_stale();
    }
}

pub async fn run_stdin_relay(
    sock: Arc<tokio::net::UdpSocket>,
    mc_sock: Arc<tokio::net::UdpSocket>,
    peers: Arc<RwLock<PeerRegistry>>,
    messages_relayed: Arc<RwLock<u64>>,
    secret: String,
) -> Result<(), VertexNodeError> {
    let mc_addr = SocketAddr::new(IpAddr::V4(Ipv4Addr::new(239, 255, 0, 1)), 9001);

    let mut stdin = tokio::io::BufReader::new(tokio::io::stdin());
    let mut line = String::new();

    loop {
        line.clear();
        let n = stdin.read_line(&mut line).await?;
        if n == 0 {
            break;
        }
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
            if let Ok(mut v) = serde_json::from_str::<Value>(trimmed) {
            if !secret.is_empty() {
                if let (Some(topic), Some(sender_id), Some(message_id), Some(timestamp_ms)) = (
                    v.get("topic").and_then(|t| t.as_str()),
                    v.get("sender_id").and_then(|s| s.as_str()),
                    v.get("message_id").and_then(|m| m.as_str()),
                    v.get("timestamp_ms").and_then(|t| t.as_i64()),
                ) {
                    let payload = v.get("payload").cloned().unwrap_or(Value::Null);
                    if let Ok(sig) = sign_envelope(
                        topic,
                        sender_id,
                        message_id,
                        timestamp_ms,
                        &payload,
                        &secret,
                    ) {
                        v.as_object_mut()
                            .expect("value is object")
                            .insert("hmac_sig".to_string(), Value::String(sig));
                    }
                }
            }
            let signed = serde_json::to_string(&v)?;
            let bytes = signed.as_bytes();

            let peer_addrs: Vec<SocketAddr> = {
                let reg = peers.read().await;
                reg.peers()
                    .iter()
                    .filter_map(|(peer_id, _)| peer_id.parse().ok())
                    .collect()
            };
            for addr in &peer_addrs {
                let _ = sock.send_to(bytes, addr).await;
            }
            let _ = mc_sock.send_to(bytes, mc_addr).await;

            let mut count = messages_relayed.write().await;
            *count += 1;

            if let Ok(v2) = serde_json::from_str::<Value>(trimmed) {
                let topic = v2
                    .get("topic")
                    .and_then(|t| t.as_str())
                    .unwrap_or("unknown");
                println!("[EVENT] topic={}", topic);
            }
        }
    }

    Ok(())
}

pub async fn run_udp_listener(
    sock: Arc<tokio::net::UdpSocket>,
    peers: Arc<RwLock<PeerRegistry>>,
    secret: String,
) -> Result<(), VertexNodeError> {
    let mut buf = vec![0u8; 65507];
    loop {
        match sock.recv_from(&mut buf).await {
            Ok((n, src)) => {
                peers.write().await.register(src.to_string());
                if let Ok(s) = std::str::from_utf8(&buf[..n]) {
                    let s = s.trim();
                    if !s.is_empty() {
                        let mut should_print = true;
                        if let Ok(v) = serde_json::from_str::<Value>(s) {
                            if let (
                                Some(topic),
                                Some(sender_id),
                                Some(message_id),
                                Some(timestamp_ms),
                                Some(sig),
                            ) = (
                                v.get("topic").and_then(|t| t.as_str()),
                                v.get("sender_id").and_then(|s| s.as_str()),
                                v.get("message_id").and_then(|m| m.as_str()),
                                v.get("timestamp_ms").and_then(|t| t.as_i64()),
                                v.get("hmac_sig").and_then(|h| h.as_str()),
                            ) {
                                let payload = v.get("payload").cloned().unwrap_or(Value::Null);
                                if !verify_envelope(
                                    topic, sender_id, message_id, timestamp_ms, &payload, sig,
                                    &secret,
                                ) {
                                    should_print = false;
                                }
                            }
                        }
                        if should_print {
                            println!("[EVENT] {}", s);
                        }
                    }
                }
            }
            Err(_e) => {
            }
        }
    }
}

pub async fn run_multicast_listener(
    mc_sock: Arc<tokio::net::UdpSocket>,
    peers: Arc<RwLock<PeerRegistry>>,
) -> Result<(), VertexNodeError> {
    let mut buf = vec![0u8; 65507];
    loop {
        match mc_sock.recv_from(&mut buf).await {
            Ok((n, src)) => {
                if let Ok(s) = std::str::from_utf8(&buf[..n]) {
                    if let Ok(v) = serde_json::from_str::<Value>(s.trim()) {
                        if let Some(port) = v.get("port").and_then(|p| p.as_u64()) {
                            let peer = SocketAddr::new(src.ip(), port as u16);
                            peers.write().await.register(peer.to_string());
                        }
                    }
                }
            }
            Err(_e) => {}
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn peer_registry_eviction() {
        let mut reg = PeerRegistry::new(1);
        reg.register("peer1");
        assert_eq!(reg.len(), 1);
        std::thread::sleep(Duration::from_secs(2));
        reg.evict_stale();
        assert_eq!(reg.len(), 0);
    }

    #[test]
    fn hmac_sign_and_verify() {
        let secret = "test-secret";
        let payload = serde_json::json!({"x": 1, "y": {"z": 2}});
        let sig = sign_envelope("t", "s", "m", 42, &payload, secret).expect("sign envelope should succeed");
        assert!(verify_envelope("t", "s", "m", 42, &payload, &sig, secret));
        assert!(!verify_envelope("t", "s", "m", 42, &payload, &sig, "wrong-secret"));
        let tampered = serde_json::json!({"x": 2, "y": {"z": 2}});
        assert!(!verify_envelope("t", "s", "m", 42, &tampered, &sig, secret));
    }

    #[test]
    fn hmac_verify_empty_secret_always_true() {
        let payload = serde_json::json!({"a": 1});
        assert!(verify_envelope("t", "s", "m", 1, &payload, "", ""));
        assert!(verify_envelope("t", "s", "m", 1, &payload, "some-sig", ""));
    }

    #[test]
    fn hmac_verify_empty_sig_fails_when_secret_set() {
        let payload = serde_json::json!({"a": 1});
        assert!(!verify_envelope("t", "s", "m", 1, &payload, "", "secret"));
    }
}
