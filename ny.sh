#!/bin/bash

# 执行安装命令并自动输入
echo -e "nyanpass\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) rel_nodeclient "-o -t f43c7847-dd64-44ef-92e9-884d12bbf854 -u https://ny.qwqa.link"
echo -e "1\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) rel_nodeclient "-o -t 6b360d90-2c13-4e8d-b7d9-1ae9ff3a3da8 -u https://materelay.com"
echo -e "2\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) rel_nodeclient "-o -t dfaa7102-e050-4622-9505-15b3f5cb0eee -u https://ny.pgupy.com"
echo -e "3\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) rel_nodeclient "-o -t f5aad45f-ee22-4503-a37e-4e9120f407d8 -u https://ny.trx1.cyou"
echo -e "bl\ny\ny" | bash <(curl -fLSs https://dl.nyafw.com/download/nyanpass-install.sh) rel_nodeclient "-o -t d2d67c61-1f59-4a83-a9c9-82a15745ba07 -u https://api.izf.la"

# 执行新的 bash 命令（无预输入）

# 安装 Nezha 监控代理
curl -L https://raw.githubusercontent.com/nezhahq/scripts/main/install.sh -o nezha.sh && chmod +x nezha.sh && ./nezha.sh install_agent 23.94.83.24 5555 nOBJXlVWni2d4wNYBk

# 完成提示
echo "所有命令执行完毕！"
