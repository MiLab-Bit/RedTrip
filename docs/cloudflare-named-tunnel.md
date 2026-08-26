# Cloudflare 命名隧道 · sy-realm.ltd

RedTrip 正式域名通过 Cloudflare Named Tunnel 对外提供 HTTPS，源站为本机 nginx（`/redtrip/` → 静态 + `/redtrip/v1` → API）。

## 架构（不含密钥）

| 项 | 说明 |
|---|---|
| 域名 | `sy-realm.ltd` / `www.sy-realm.ltd` |
| DNS | Cloudflare 托管（橙云代理） |
| Tunnel 名 | `redtrip-sy-realm` |
| Tunnel ID | 见服务器 `/etc/cloudflared/` 配置（**勿入库**） |
| 源站 | `http://127.0.0.1:80` |
| systemd | `cloudflared-redtrip-sy-realm.service` |

DNS（Cloudflare，橙云）：

- `@` / `www` → CNAME → `<TUNNEL_ID>.cfargotunnel.com`

## 本机配置样例

```yaml
tunnel: <TUNNEL_ID>
credentials-file: /etc/cloudflared/redtrip-sy-realm.json
ingress:
  - hostname: sy-realm.ltd
    service: http://127.0.0.1:80
  - hostname: www.sy-realm.ltd
    service: http://127.0.0.1:80
  - service: http_status:404
```

```bash
systemctl status cloudflared-redtrip-sy-realm
curl -sI https://sy-realm.ltd/redtrip/
curl -s https://sy-realm.ltd/redtrip/v1/health
```

## 注意

1. **命名隧道自定义域名需要域名 NS 切到 Cloudflare**；仅在注册商 DNS 做 CNAME → `*.cfargotunnel.com` 不够（该主机名无公网 A 记录）。
2. 阿里云改 NS 用 Domain API 时参数名为 `DomainNameServer.N`（不是 `DomainNameServerList`），且 `AliyunDns=false`。
3. Tunnel token / credentials / Cloudflare API Token / R2 / 云厂商 AccessKey **一律放服务器环境文件，禁止提交 git**。
4. 同机其它 `cloudflared-*.service`（quick tunnel）与本命名隧道无关，勿误停其它业务隧道。
