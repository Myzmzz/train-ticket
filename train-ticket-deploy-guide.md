# Train-Ticket 完整部署指令（集群内，train-ticket 命名空间）

## 前置条件

- SSH 到 Master 节点，项目源码已克隆
- NFS 目录 `1.94.151.57:/data/share` 已放置 `opentelemetry-javaagent.jar`（41 个 Java 服务通过 NFS 挂载该 Agent）
- Coroot OTLP 端点 `http://coroot-coroot.coroot:8080` 可达（coroot 命名空间已部署）

---

## 第一步：镜像准备

### 1.1 验证 Harbor 中微服务镜像是否就绪

```bash
# 抽查几个关键镜像
for svc in ts-auth-service ts-order-service ts-travel-service ts-preserve-service ts-gateway-service ts-ui-dashboard; do
  echo -n "$svc: "
  curl -s http://1.94.151.57:85/v2/train-ticket/${svc}/tags/list
  echo
done
```

如果返回 `{"name":"train-ticket/ts-xxx","tags":["1.0.0"]}` 说明镜像已存在，跳到第二步。

### 1.2 如果镜像不存在，需要构建并推送

```bash
cd train-ticket-1.0.0

# 登录 Harbor
docker login 1.94.151.57:85 -u admin -p Harbor12345

# 构建所有 Java 微服务（必须指定 linux/amd64）
for svc in $(ls -d ts-*/); do
  svc_name=${svc%/}
  if [ -f "${svc_name}/Dockerfile" ]; then
    echo "=== Building $svc_name ==="
    docker buildx build --platform linux/amd64 \
      -t 1.94.151.57:85/train-ticket/${svc_name}:1.0.0 \
      -f ${svc_name}/Dockerfile . --push
  fi
done
```

### 1.3 基础设施镜像确认

Helm Chart 默认从 Docker Hub 拉取以下镜像，确认集群节点可以访问：

| 镜像 | Tag | 用途 |
|------|-----|------|
| `radondb/percona` | `5.7.34` | MySQL |
| `radondb/xenon` | `1.1.5-helm` | MySQL HA 选举 |
| `busybox` | `1.32` | 初始化容器 |
| `nacos/nacos-server` | `2.0.1` | 注册中心 |
| `codewisdom/mysqlclient` | `0.1` | Nacos MySQL 初始化 |
| `codewisdom/rabbitmq` | `3` | 消息队列 |

如果节点**无法访问 Docker Hub**，需提前推送到 Harbor：

```bash
# 用 crane 拷贝（保证 linux/amd64 架构）
HARBOR=1.94.151.57:85/train-ticket
crane copy --platform linux/amd64 --insecure radondb/percona:5.7.34 $HARBOR/radondb-percona:5.7.34
crane copy --platform linux/amd64 --insecure radondb/xenon:1.1.5-helm $HARBOR/radondb-xenon:1.1.5-helm
crane copy --platform linux/amd64 --insecure busybox:1.32 $HARBOR/busybox:1.32
crane copy --platform linux/amd64 --insecure nacos/nacos-server:2.0.1 $HARBOR/nacos-nacos-server:2.0.1
crane copy --platform linux/amd64 --insecure codewisdom/mysqlclient:0.1 $HARBOR/codewisdom-mysqlclient:0.1
crane copy --platform linux/amd64 --insecure codewisdom/rabbitmq:3 $HARBOR/codewisdom-rabbitmq:3
crane copy --platform linux/amd64 --insecure prom/mysqld-exporter:v0.12.1 $HARBOR/prom-mysqld-exporter:v0.12.1
```

后续 Helm 安装时需 `--set` 覆盖镜像地址（见各步骤注释）。

---

## 第二步：创建命名空间

```bash
kubectl create namespace train-ticket
```

---

## 第三步：部署 nacosdb（Nacos 专用 MySQL，3 副本 HA）

```bash
helm install nacosdb \
  --set mysql.mysqlUser=nacos \
  --set mysql.mysqlPassword='Abcd1234#' \
  --set mysql.mysqlDatabase=nacos \
  deployment/kubernetes-manifests/quickstart-k8s/charts/mysql \
  -n train-ticket

# 如果基础设施镜像也推到了 Harbor，加上：
# --set mysql.image=1.94.151.57:85/train-ticket/radondb-percona \
# --set mysql.tag=5.7.34 \
# --set xenon.image=1.94.151.57:85/train-ticket/radondb-xenon \
# --set xenon.tag=1.1.5-helm \
# --set busybox.image=1.94.151.57:85/train-ticket/busybox \
# --set busybox.tag=1.32 \

kubectl rollout status statefulset/nacosdb-mysql -n train-ticket --timeout=300s
```

---

## 第四步：部署 tsdb（应用 MySQL，3 副本 HA）

```bash
helm install tsdb \
  --set mysql.mysqlUser=ts \
  --set mysql.mysqlPassword=Ts_123456 \
  --set mysql.mysqlDatabase=ts \
  deployment/kubernetes-manifests/quickstart-k8s/charts/mysql \
  -n train-ticket

kubectl rollout status statefulset/tsdb-mysql -n train-ticket --timeout=300s
```

---

## 第五步：修复 MySQL Xenon IPv6 问题（关键！）

> RadonDB 的 Xenon 组件通过 IPv6 (`::1`) 连接 MySQL 进行 Leader 选举。不修复会导致 follower 节点 `PostStartHookError`，MySQL 集群无法正常选主。

```bash
# 等待所有 MySQL Pod 完全就绪
kubectl wait --for=condition=ready pod -l app=nacosdb-mysql -n train-ticket --timeout=300s
kubectl wait --for=condition=ready pod -l app=tsdb-mysql -n train-ticket --timeout=300s

# 在 6 个 MySQL Pod 上创建 IPv6 root 用户
for pod in nacosdb-mysql-0 nacosdb-mysql-1 nacosdb-mysql-2 \
           tsdb-mysql-0 tsdb-mysql-1 tsdb-mysql-2; do
  echo "=== Fixing $pod ==="
  kubectl exec -n train-ticket $pod -c mysql -- \
    mysql -uroot -e "
      CREATE USER IF NOT EXISTS 'root'@'::1' IDENTIFIED BY '';
      GRANT ALL PRIVILEGES ON *.* TO 'root'@'::1' WITH GRANT OPTION;
      FLUSH PRIVILEGES;
    "
done

# 验证：所有 Pod 应为 3/3 Ready
kubectl get pods -n train-ticket -l app=nacosdb-mysql
kubectl get pods -n train-ticket -l app=tsdb-mysql
```

---

## 第六步：部署 Nacos（3 副本集群）

```bash
helm install nacos \
  --set nacos.db.host=nacosdb-mysql-leader \
  --set nacos.db.username=nacos \
  --set nacos.db.name=nacos \
  --set nacos.db.password='Abcd1234#' \
  deployment/kubernetes-manifests/quickstart-k8s/charts/nacos \
  -n train-ticket

# 如果 nacos 镜像在 Harbor：
# --set nacos.image.repository=1.94.151.57:85/train-ticket/nacos-nacos-server \
# --set nacos.image.tag=2.0.1 \
# --set initmysql.image=1.94.151.57:85/train-ticket/codewisdom-mysqlclient:0.1 \

kubectl rollout status statefulset/nacos -n train-ticket --timeout=300s
```

---

## 第七步：部署 RabbitMQ

```bash
helm install rabbitmq \
  deployment/kubernetes-manifests/quickstart-k8s/charts/rabbitmq \
  -n train-ticket

# 如果 rabbitmq 镜像在 Harbor：
# --set rabbitmq.image.repository=1.94.151.57:85/train-ticket/codewisdom-rabbitmq \
# --set rabbitmq.image.tag=3 \

kubectl rollout status deployment/rabbitmq -n train-ticket --timeout=120s
```

---

## 第八步：创建 Service 资源

```bash
kubectl apply -f deployment/kubernetes-manifests/quickstart-k8s/yamls/svc.yaml \
  -n train-ticket
```

---

## 第九步：生成并应用 MySQL Secrets

> `gen-mysql-secret.sh` 使用 bash 特有语法（`[ $# == 4 ]`），必须用 bash 执行，zsh 会报 `= not found` 错误。

```bash
bash -c 'source hack/deploy/gen-mysql-secret.sh && \
  gen_secret_for_services ts Ts_123456 ts tsdb-mysql-leader'

kubectl apply -f deployment/kubernetes-manifests/quickstart-k8s/yamls/secret.yaml \
  -n train-ticket
```

---

## 第十步：部署 46 个微服务（含 OTel Agent）

```bash
kubectl apply -f deployment/kubernetes-manifests/quickstart-k8s/yamls/deploy-otel.yaml \
  -n train-ticket
```

> 该文件中 46 个微服务镜像均指向 `1.94.151.57:85/train-ticket/<service>:1.0.0`（Harbor）。
> 41 个 Java 服务通过 NFS 挂载 `1.94.151.57:/data/share` 获取 `opentelemetry-javaagent.jar`，链路数据发送到 `http://coroot-coroot.coroot:8080`。

---

## 第十一步：等待全部就绪并验证

```bash
# 等待（Java 服务启动慢，约 3-5 分钟）
kubectl wait --for=condition=ready pod --all -n train-ticket --timeout=600s

# 或实时监控未就绪的 Pod
watch -n 5 'echo "Not Ready:"; kubectl get pods -n train-ticket --no-headers | grep -v Running'

# 最终确认：预期 56 Pod
kubectl get pods -n train-ticket --no-headers | wc -l
kubectl get pods -n train-ticket --no-headers | awk '{print $3}' | sort | uniq -c

# Helm releases：预期 4 个（nacosdb, tsdb, nacos, rabbitmq）
helm list -n train-ticket

# NodePort 访问测试
curl -s -o /dev/null -w "UI Dashboard: %{http_code}\n" http://1.94.151.57:32677
curl -s -o /dev/null -w "Gateway API: %{http_code}\n" http://1.94.151.57:30467
```

---

## 完整卸载

```bash
NS=train-ticket

# 1. 删除应用层（逆序）
kubectl delete -f deployment/kubernetes-manifests/quickstart-k8s/yamls/deploy-otel.yaml \
  -n $NS --ignore-not-found
kubectl delete -f deployment/kubernetes-manifests/quickstart-k8s/yamls/secret.yaml \
  -n $NS --ignore-not-found
kubectl delete -f deployment/kubernetes-manifests/quickstart-k8s/yamls/svc.yaml \
  -n $NS --ignore-not-found

# 2. 卸载 Helm releases（逆序）
helm uninstall rabbitmq -n $NS
helm uninstall nacos -n $NS
helm uninstall tsdb -n $NS
helm uninstall nacosdb -n $NS

# 3. 清理 PVC（删除 MySQL 持久化数据，不可恢复！）
kubectl delete pvc --all -n $NS

# 4.（可选）删除命名空间
kubectl delete namespace $NS

# 5. 验证清理干净
kubectl get all -n $NS
helm list -n $NS
```

---

## 速查：凭证与端口

| 组件 | 用户 | 密码 | 端口 |
|------|------|------|------|
| nacosdb MySQL | nacos | Abcd1234# | 3306 |
| tsdb MySQL | ts | Ts_123456 | 3306 |
| MySQL root | root | (空) | 3306 |
| Nacos Console | nacos | nacos | 8848 (NodePort 自动分配) |
| RabbitMQ | guest | guest | 5672 |
| Gateway API | - | - | **30467** |
| UI Dashboard | - | - | **32677** |
| Harbor | admin | Harbor12345 | 85 |

## 部署顺序总览

```
nacosdb (MySQL HA) ─┐
                    ├─> IPv6 修复 ─> Nacos ─┐
tsdb (MySQL HA) ────┘                       ├─> svc.yaml ─> secret.yaml ─> deploy-otel.yaml
                         RabbitMQ ──────────┘
```
