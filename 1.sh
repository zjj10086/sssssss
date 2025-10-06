#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail

# ------------------------
# Cloudflare DDNS 自动更新脚本
# ------------------------

# 配置区域
CFKEY="6HuEmDY_BRwvHhbMSsESOie2IOKM61Qvahw0pB8f"
CFUSER="tutu119216@gmail.com"
CFZONE_NAME="484845845.xyz"
CFRECORD_NAME="aws1485-28-12wa.484845845.xyz"
CFRECORD_TYPE="AAAA"  # A 或 AAAA
CFTTL=60
FORCE=false

# 日志文件
LOG_FILE="/root/cf-ddns.log"

# 获取公网 IP
if [ "$CFRECORD_TYPE" = "A" ]; then
    WAN_IP=$(curl -s https://api.ipify.org)
elif [ "$CFRECORD_TYPE" = "AAAA" ]; then
    WAN_IP=$(curl -s https://api64.ipify.org)
else
    echo "$(date '+%F %T') Invalid CFRECORD_TYPE" | tee -a "$LOG_FILE"
    exit 2
fi

WAN_IP_FILE="$HOME/.cf-wan_ip_$CFRECORD_NAME.txt"
OLD_WAN_IP=""
if [ -f "$WAN_IP_FILE" ]; then
    OLD_WAN_IP=$(cat "$WAN_IP_FILE")
fi

# 如果 IP 没变化并且没有 FORCE，跳过
if [ "$WAN_IP" = "$OLD_WAN_IP" ] && [ "$FORCE" = false ]; then
    echo "$(date '+%F %T') WAN IP unchanged ($WAN_IP), skipping" | tee -a "$LOG_FILE"
    exit 0
fi

# 获取 zone_id 和 record_id
ID_FILE="$HOME/.cf-id_$CFRECORD_NAME.txt"
if [ -f "$ID_FILE" ] && [ $(wc -l < "$ID_FILE") -eq 4 ]; then
    CFZONE_ID=$(sed -n '1p' "$ID_FILE")
    CFRECORD_ID=$(sed -n '2p' "$ID_FILE")
else
    echo "$(date '+%F %T') Updating zone_identifier & record_identifier" | tee -a "$LOG_FILE"
    CFZONE_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=$CFZONE_NAME" \
      -H "X-Auth-Email: $CFUSER" \
      -H "X-Auth-Key: $CFKEY" \
      -H "Content-Type: application/json" | grep -Po '(?<="id":")[^"]*' | head -1)
    CFRECORD_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$CFZONE_ID/dns_records?name=$CFRECORD_NAME" \
      -H "X-Auth-Email: $CFUSER" \
      -H "X-Auth-Key: $CFKEY" \
      -H "Content-Type: application/json" | grep -Po '(?<="id":")[^"]*' | head -1)
    echo -e "$CFZONE_ID\n$CFRECORD_ID\n$CFZONE_NAME\n$CFRECORD_NAME" > "$ID_FILE"
fi

# 更新 DNS
echo "$(date '+%F %T') Updating DNS to $WAN_IP" | tee -a "$LOG_FILE"

RESPONSE=$(curl -s -X PUT "https://api.cloudflare.com/client/v4/zones/$CFZONE_ID/dns_records/$CFRECORD_ID" \
  -H "X-Auth-Email: $CFUSER" \
  -H "X-Auth-Key: $CFKEY" \
  -H "Content-Type: application/json" \
  --data "{\"id\":\"$CFZONE_ID\",\"type\":\"$CFRECORD_TYPE\",\"name\":\"$CFRECORD_NAME\",\"content\":\"$WAN_IP\", \"ttl\":$CFTTL}")

if echo "$RESPONSE" | grep -q '"success":true'; then
    echo "$(date '+%F %T') Updated successfully!" | tee -a "$LOG_FILE"
    echo "$WAN_IP" > "$WAN_IP_FILE"
else
    echo "$(date '+%F %T') Something went wrong :(" | tee -a "$LOG_FILE"
    echo "Response: $RESPONSE" | tee -a "$LOG_FILE"
fi

# ------------------------
# 后台循环模式（每分钟更新一次）
# ------------------------
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    nohup bash -c 'while true; do /root/1.sh; sleep 60; done' >/root/cf-ddns.log 2>&1 &
fi
