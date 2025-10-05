#!/bin/bash

######################################
# 一键安装 IPv6 DDNS + Telegram + Nyanpass + Nezha
# 作者: ChatGPT整理
######################################

# --- 1. 下载并修改 ddns.sh 实现 IPv6 自动启用 ---
wget -O /tmp/ddns.sh https://raw.githubusercontent.com/mocchen/cssmeihua/mochen/shell/ddns.sh
# 将 IPv6 询问改为默认 y
sed -i 's/read -p "\[提示\]是否开启 IPv6 解析？(y\/n)"/ipv6_enable="y"\necho "\[信息\]IPv6 自动启用"/' /tmp/ddns.sh

# --- 2. 自动执行 DDNS 安装 (IPv6 + Telegram) ---
bash /tmp/ddns.sh <<EOF
tutu119216@gmail.com
6HuEmDY_BRwvHhbMSsESOie2IOKM61Qvahw0pB8f

aws1485-28-12wa.484845845.xyz
y
8371117300:AAHHMYPBTx8SAxhfexcw3jTcQMVVSOuDc
6133126873
EOF

echo "[INFO] IPv6 DDNS + Telegram 配置完成！"

# --- 3. 安装 Nyanpass ---
echo "[INFO] 开始安装 Nyanpass..."
echo -e "nyanpass\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) rel_nodeclient "-t 90a1ff7e-b2a2-41d7-88ac-8e4d253086c9 -u https://ny.qwqa.link"
echo -e "nuan\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) rel_nodeclient "-o -t 7a510a72-8f0e-45a6-8937-42c1c545ff9c -u https://materelay.com"

# --- 4. 安装 Nezha 监控代理 ---
echo "[INFO] 开始安装 Nezha 监控代理..."
curl -L https://raw.githubusercontent.com/nezhahq/scripts/main/install.sh -o /tmp/nezha.sh
chmod +x /tmp/nezha.sh
/tmp/nezha.sh install_agent 23.94.83.24 5555 oer1NSgoX8i6DRmgW0

# --- 5. 完成提示 ---
echo "[INFO] 所有安装完成！"
