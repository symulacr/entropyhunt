#!/usr/bin/env bash
# Start a 4-node FoxMQ cluster for true BFT consensus (tolerates f=1 Byzantine fault)
# Node 0 must already be running on mqtt=1884, cluster=19793
set -e
cd "$(dirname "$0")/.."

foxmq run --allow-anonymous-login --secret-key-file=foxmq.d/key_1.pem --mqtt-addr=127.0.0.1:1885 --cluster-addr=127.0.0.1:19794 --log=json foxmq.d > /tmp/foxmq_1.log 2>&1 &
foxmq run --allow-anonymous-login --secret-key-file=foxmq.d/key_2.pem --mqtt-addr=127.0.0.1:1886 --cluster-addr=127.0.0.1:19795 --log=json foxmq.d > /tmp/foxmq_2.log 2>&1 &
foxmq run --allow-anonymous-login --secret-key-file=foxmq.d/key_3.pem --mqtt-addr=127.0.0.1:1887 --cluster-addr=127.0.0.1:19796 --log=json foxmq.d > /tmp/foxmq_3.log 2>&1 &

echo "4-node FoxMQ cluster started (nodes 1-3). Node 0 must already be running."
echo "MQTT ports: 1884 (node0), 1885 (node1), 1886 (node2), 1887 (node3)"
