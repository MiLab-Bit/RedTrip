# Cloudflare 命名隧道 · sy-realm.ltd

RedTrip 正式域名通过 Cloudflare Named Tunnel 对外提供 HTTPS，源站仍是阿里云 SWAS 上的 nginx（`/redtrip/` → 静态 + `/redtrip/v1` → API `:8799`）。

## 现状

| 项 | 值 |
|---|---|
| 域名 | `sy-realm.ltd` / `www.sy-realm.ltd` |
| Zone | Cloudflare（NS：`hugh.ns.cloudflare.com` / `lady.ns.cloudflare.com`） |
| Tunnel 名 | `redtrip-sy-realm` |
| Tunnel ID | `12a1b53c-545e-4ee4-86b5-39f15182dfe7` |
| 源站 | `http://127.0.0.1:80`（本机 nginx） |
| systemd | `cloudflared-redtrip-sy-realm.service` |
| 配置 | `/etc/cloudflared/config-redtrip-sy-realm.yml` |
| 凭证 | `/etc/cloudflared/redtrip-sy-realm.json`（**勿入库**） |

DNS（Cloudflare，橙云代理）：

- `@` / `www` → CNAME → `12a1b53c-545e-4ee4-86b5-39f15182dfe7.cfargotunnel.com`

## 本机配置样例

```yaml
tunnel: 12a1b53c-545e-4ee4-86b5-39f15182dfe7
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

1. **命名隧道自定义域名需要域名 NS 切到 Cloudflare**；仅在阿里云 DNS 做 CNAME → `*.cfargotunnel.com` 不够（该主机名无公网 A 记录）。
2. 阿里云改 NS 用 Domain API 时参数名为 `DomainNameServer.N`（不是 `DomainNameServerList`），且 `AliyunDns=false`。
3. Tunnel token / credentials / Cloudflare API Token / R2 密钥一律放服务器环境文件，不要提交 git。
4. 同机其它 `cloudflared-*.service`（quick tunnel）与本命名隧道无关，勿误停 `bizatlas` 等业务隧道。
