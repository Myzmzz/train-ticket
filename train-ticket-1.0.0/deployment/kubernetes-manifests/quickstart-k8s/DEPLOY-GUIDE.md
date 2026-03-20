# Train-Ticket K8s 部署指南

> 基于 quickstart-k8s 的完整部署流程，所有镜像使用 Harbor 私有仓库。

## 环境信息

| 项目 | 值 |
|------|-----|
| K8s 集群 | `KUBECONFIG=~/.kube/coroot-config` |
| Namespace | `train-ticket` |
| Harbor 仓库 | `1.94.151.57:85/train-ticket`（admin/Harbor12345，HTTP） |
| Coroot OTLP | `http://coroot-coroot.coroot:8080` |
| NFS（OTel Agent） | `1.94.151.57:/data/share` |
| Gateway NodePort | 30467 |
| UI Dashboard NodePort | 32677 |

### 集群节点

| 节点 | 内网 IP | 角色 |
|------|---------|------|
| tcse-flexusx-01 | 192.168.0.148 | worker |
| tcse-v100-01 | 192.168.0.197 | control-plane |
| tcse-v100-02 | 192.168.0.138 | worker |
| tcse-v100-03 | 192.168.0.118 | worker |

### 凭证

| 组件 | 用户名 | 密码 | 用途 |
|------|--------|------|------|
| Nacos Console | nacos | nacos | Nacos Web UI |
| nacosdb MySQL | nacos | Abcd1234# | Nacos 存储后端 |
| tsdb MySQL | ts | Ts_123456 | 应用服务数据库 |
| MySQL root | root | （空） | MySQL 管理 |
| RabbitMQ | guest | guest | 默认凭证 |

---

## 部署流程

以下命令均在项目根目录 `train-ticket-1.0.0/` 下执行。

### 0. 前置准备

```bash
export KUBECONFIG=~/.kube/coroot-config
kubectl create namespace train-ticket
```

### 1. 部署 nacosdb（Nacos 专用 MySQL，3 副本 RadonDB HA）

```bash
helm install nacosdb \
  --set mysql.mysqlUser=nacos \
  --set mysql.mysqlPassword='Abcd1234#' \
  --set mysql.mysqlDatabase=nacos \
  --set mysql.image=1.94.151.57:85/train-ticket/radondb-percona \
  --set mysql.tag=5.7.34 \
  --set xenon.image=1.94.151.57:85/train-ticket/radondb-xenon \
  --set xenon.tag=1.1.5-helm \
  --set busybox.image=1.94.151.57:85/train-ticket/busybox \
  --set busybox.tag=1.32 \
  --set metrics.image=1.94.151.57:85/train-ticket/prom-mysqld-exporter \
  --set metrics.tag=v0.12.1 \
  deployment/kubernetes-manifests/quickstart-k8s/charts/mysql \
  -n train-ticket
```

### 2. 部署 tsdb（应用 MySQL，3 副本 RadonDB HA）

```bash
helm install tsdb \
  --set mysql.mysqlUser=ts \
  --set mysql.mysqlPassword=Ts_123456 \
  --set mysql.mysqlDatabase=ts \
  --set mysql.image=1.94.151.57:85/train-ticket/radondb-percona \
  --set mysql.tag=5.7.34 \
  --set xenon.image=1.94.151.57:85/train-ticket/radondb-xenon \
  --set xenon.tag=1.1.5-helm \
  --set busybox.image=1.94.151.57:85/train-ticket/busybox \
  --set busybox.tag=1.32 \
  --set metrics.image=1.94.151.57:85/train-ticket/prom-mysqld-exporter \
  --set metrics.tag=v0.12.1 \
  deployment/kubernetes-manifests/quickstart-k8s/charts/mysql \
  -n train-ticket
```

### 3. 等待 MySQL 就绪 + 修复 IPv6 root 用户

MySQL 的 Xenon（RadonDB）通过 Go MySQL 驱动连接时会走 IPv6（`::1`），需要为每个节点创建 IPv6 root 用户，否则 leader 选举会失败。

```bash
# 等待 MySQL Pod 全部 Running
kubectl wait --for=condition=Ready pod -l app=nacosdb-mysql -n train-ticket --timeout=300s
kubectl wait --for=condition=Ready pod -l app=tsdb-mysql -n train-ticket --timeout=300s

# 在每个 MySQL 节点创建 IPv6 root 用户
for pod in nacosdb-mysql-0 nacosdb-mysql-1 nacosdb-mysql-2 \
           tsdb-mysql-0 tsdb-mysql-1 tsdb-mysql-2; do
  kubectl exec "$pod" -n train-ticket -c mysql -- mysql -uroot -e \
    "CREATE USER IF NOT EXISTS 'root'@'::1' IDENTIFIED BY ''; \
     GRANT ALL PRIVILEGES ON *.* TO 'root'@'::1' WITH GRANT OPTION; \
     FLUSH PRIVILEGES;"
done
```

### 4. 部署 Nacos（3 节点集群）

```bash
helm install nacos \
  --set nacos.db.host=nacosdb-mysql-leader \
  --set nacos.db.username=nacos \
  --set nacos.db.name=nacos \
  --set nacos.db.password='Abcd1234#' \
  --set nacos.image.repository=1.94.151.57:85/train-ticket/nacos-nacos-server \
  --set nacos.image.tag=2.0.1 \
  --set initmysql.image=1.94.151.57:85/train-ticket/codewisdom-mysqlclient:0.1 \
  deployment/kubernetes-manifests/quickstart-k8s/charts/nacos \
  -n train-ticket
```

### 5. 部署 RabbitMQ

```bash
helm install rabbitmq \
  --set rabbitmq.image.repository=1.94.151.57:85/train-ticket/codewisdom-rabbitmq \
  --set rabbitmq.image.tag=3 \
  deployment/kubernetes-manifests/quickstart-k8s/charts/rabbitmq \
  -n train-ticket
```

### 6. 创建应用 MySQL Secret

> **注意：必须用 bash 执行，zsh 不兼容。**

```bash
bash -c 'source hack/deploy/gen-mysql-secret.sh && \
  gen_secret_for_services ts Ts_123456 ts tsdb-mysql-leader'

kubectl apply -f mysql-secret.yaml -n train-ticket
```

### 7. 部署应用 Services 和 Deployments

```bash
kubectl apply -f deployment/kubernetes-manifests/quickstart-k8s/yamls/svc.yaml -n train-ticket
kubectl apply -f deployment/kubernetes-manifests/quickstart-k8s/yamls/deploy-otel.yaml -n train-ticket
```

### 8. 验证部署

```bash
# 等待所有 Pod 就绪（Java 服务启动约需 2-3 分钟）
kubectl get pods -n train-ticket

# 检查 Nacos 集群状态
kubectl logs nacos-0 -n train-ticket --tail=5

# 检查 MySQL leader 选举
kubectl exec nacosdb-mysql-0 -n train-ticket -c xenon -- xenoncli raft status
kubectl exec tsdb-mysql-0 -n train-ticket -c xenon -- xenoncli raft status
```

预期：约 59 个 Pod 全部 Running（3 Nacos + 9 MySQL + 1 RabbitMQ + 46 应用服务）。

---

## 架构概览

```
用户 → ts-ui-dashboard(:32677) → ts-gateway-service(:30467)
         ↓
    46 个微服务（Java + OTel Agent）
         ↓                    ↓
    tsdb-mysql (3副本HA)    Nacos (3节点集群)
                               ↓
                          nacosdb-mysql (3副本HA)
```

- Java 服务通过 NFS 挂载 OpenTelemetry Java Agent 2.5.0
- Trace 上报到 Coroot（`http://coroot-coroot.coroot:8080`）
- 服务注册发现使用 Nacos

---

## 常用运维命令

### 重新部署应用服务（不动基础设施）

```bash
kubectl apply -f deployment/kubernetes-manifests/quickstart-k8s/yamls/deploy-otel.yaml -n train-ticket
```

### 重启某个服务

```bash
kubectl rollout restart deployment/<service-name> -n train-ticket
```

### 清理并完整卸载

```bash
kubectl delete -f deployment/kubernetes-manifests/quickstart-k8s/yamls/deploy-otel.yaml -n train-ticket
kubectl delete -f deployment/kubernetes-manifests/quickstart-k8s/yamls/svc.yaml -n train-ticket
helm uninstall rabbitmq -n train-ticket
helm uninstall nacos -n train-ticket
helm uninstall tsdb -n train-ticket
helm uninstall nacosdb -n train-ticket
kubectl delete namespace train-ticket
```

---

## 已知问题与修复

1. **Xenon MySQL Leader 选举失败**：Go MySQL 驱动通过 IPv6（`::1`）连接，需在所有 MySQL 节点创建 IPv6 root 用户（见步骤 3）。

2. **gen-mysql-secret.sh 必须用 bash**：该脚本使用了 zsh 不兼容的语法，必须通过 `bash -c` 执行。

3. **tcse-v100-03 节点 Docker 代理配置**：该节点的 `/etc/systemd/system/docker.service.d/http-proxy.conf` 中 `NO_PROXY` 需包含 Harbor 地址 `1.94.151.57`，否则镜像拉取会走代理失败。正确配置：
   ```ini
   [Service]
   Environment="HTTP_PROXY=http://127.0.0.1:7890"
   Environment="HTTPS_PROXY=http://127.0.0.1:7890"
   Environment="NO_PROXY=localhost,127.0.0.1,1.94.151.57,192.168.0.0/16,10.0.0.0/8"
   ```

4. **ts-wait-order-service**：缺少 Dockerfile（已创建），且 env var 名不匹配（`WAIT_ORDER_PASSWORD` vs `WAIT_ORDER_MYSQL_PASSWORD`），在 `deploy-otel.yaml` 中已加额外 env 映射。

5. **ts-avatar-service**：需要 `build-essential`/`libopenblas-dev`/`liblapack-dev`，依赖版本已升级到兼容 Python 3.10。

6. **Docker 基础镜像**：`java:8-jre` 已废弃，已改用 `eclipse-temurin:8-jre`。
