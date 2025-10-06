#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail

# ---------------- 配置 ----------------
# Cloudflare API Token
CFTOKEN="tKFEe3lbC08Il4JH6aNrgMvPdA6VU809tFLlC3TD"

# 域名和记录
CFZONE_NAME="484845845.xyz"
CFRECORD_NAME="aws1485-28-12wa.484845845.xyz"

# 记录类型，A=IPv4, AAAA=IPv6
CFRECORD_TYPE="AAAA"

# TTL (120-86400)
CFTTL=60

# 强制更新
FORCE=false

# IPv6 地址获取
WANIPSITE="http://ipv6.icanhazip.com"
if [ "$CFRECORD_TYPE" = "A" ]; then
    WANIPSITE="http://ipv4.icanhazip.com"
elif [ "$CFRECORD_TYPE" != "AAAA" ]; then
    echo "CFRECORD_TYPE 只能是 A 或 AAAA"
    exit 1
fi

# --------------------------------------

WAN_IP=$(curl -s "$WANIPSITE")
WAN_IP_FILE="$HOME/.cf-wan_ip_$CFRECORD_NAME.txt"
ID_FILE="$HOME/.cf-id_$CFRECORD_NAME.txt"

# 检查是否需要更新
OLD_WAN_IP=""
if [ -f "$WAN_IP_FILE" ]; then
    OLD_WAN_IP=$(cat "$WAN_IP_FILE")
fi

if [ "$WAN_IP" = "$OLD_WAN_IP" ] && [ "$FORCE" = false ]; then
    echo "$(date '+%F %T') WAN IP Unchanged: $WAN_IP"
    exit 0
fi

# 获取 zone_id 和 record_id
if [ -f "$ID_FILE" ]; then
    CFZONE_ID=$(sed -n '1p' "$ID_FILE")
    CFRECORD_ID=$(sed -n '2p' "$ID_FILE")
else
    echo "$(date '+%F %T') Fetching zone_id and record_id from Cloudflare..."
    CFZONE_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=$CFZONE_NAME" \
        -H "Authorization: Bearer $CFTOKEN" \
        -H "Content-Type: application/json" | grep -Po '(?<="id":")[^"]*' | head -1)
    if [ -z "$CFZONE_ID" ]; then
        echo "Error: Cannot get zone_id"
        exit 1
    fi

    CFRECORD_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$CFZONE_ID/dns_records?name=$CFRECORD_NAME" \
        -H "Authorization: Bearer $CFTOKEN" \
        -H "Content-Type: application/json" | grep -Po '(?<="id":")[^"]*' | head -1)
    if [ -z "$CFRECORD_ID" ]; then
        echo "Error: Cannot get record_id"
        exit 1
    fi

    echo "$CFZONE_ID" > "$ID_FILE"
    echo "$CFRECORD_ID" >> "$ID_FILE"
fi

# 更新 DNS
echo "$(date '+%F %T') Updating $CFRECORD_NAME to $WAN_IP..."
RESPONSE=$(curl -s -X PUT "https://api.cloudflare.com/client/v4/zones/$CFZONE_ID/dns_records/$CFRECORD_ID" \
    -H "Authorization: Bearer $CFTOKEN" \
    -H "Content-Type: application/json" \
    --data "{\"type\":\"$CFRECORD_TYPE\",\"name\":\"$CFRECORD_NAME\",\"content\":\"$WAN_IP\",\"ttl\":$CFTTL}")

if echo "$RESPONSE" | grep -q '"success":true'; then
    echo "$(date '+%F %T') Updated successfully!"
    echo "$WAN_IP" > "$WAN_IP_FILE"
else
    echo "$(date '+%F %T') Update failed!"
    echo "Response: $RESPONSE"
fi
