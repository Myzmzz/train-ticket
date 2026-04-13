# Train-Ticket 微服务系统部署指南

## 目录

- [系统概览](#系统概览)
- [方案一：本地 kubectl 远程部署](#方案一本地-kubectl-远程部署)
- [方案二：集群内直接部署](#方案二集群内直接部署)
- [部署后验证](#部署后验证)
- [常见问题与修复](#常见问题与修复)
- [清理与重置](#清理与重置)
- [附录：凭证与端口表](#附录凭证与端口表)

---

## 系统概览

Train-Ticket 是一个基于 Spring Boot + Spring Cloud 的微服务火车票预订系统，包含 56 个 Pod：

| 组件类型 | 数量 | 技术栈 |
|---------|------|--------|
| nacosdb (Nacos 专用 MySQL) | 3 Pod (RadonDB HA) | Percona 5.7.34 + Xenon |
| tsdb (应用 MySQL) | 3 Pod (RadonDB HA) | Percona 5.7.34 + Xenon |
| Nacos 注册中心 | 3 Pod (集群模式) | Nacos 2.0.1 |
| RabbitMQ 消息队列 | 1 Pod | RabbitMQ 3 |
| Java 微服务 | 41 Pod | Spring Boot 2.3.12 + OTel Agent |
| 非 Java 服务 | 5 Pod | Python / Go / Node.js / Nginx |

### 架构依赖关系

```
nacosdb (MySQL) ──> Nacos Server ──> 所有微服务 (服务注册/发现)
tsdb (MySQL) ──────────────────────> 所有微服务 (业务数据)
RabbitMQ ──────────────────────────> 部分微服务 (异步消息)
```

### 部署顺序（严格）

```
1. nacosdb (Nacos MySQL)  ──  必须先就绪
2. tsdb (应用 MySQL)      ──  可与 nacosdb 并行部署
3. MySQL IPv6 修复        ──  所有 MySQL 节点就绪后立即执行
4. Nacos Server           ──  依赖 nacosdb
5. RabbitMQ               ──  可与 Nacos 并行部署
6. svc.yaml (Services)    ──  创建 K8s Service 资源
7. secret.yaml (Secrets)  ──  MySQL 连接凭证
8. deploy-otel.yaml       ──  应用 Deployment 资源
```

---

## 方案一：本地 kubectl 远程部署

适用场景：在本地开发机（macOS/Linux）上通过 kubectl 远程管理 K8s 集群部署。

### 1.1 前置条件

#### 工具安装

```bash
# macOS (Homebrew)
brew install kubectl helm

# Linux (apt)
sudo apt-get update && sudo apt-get install -y kubectl
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

#### 配置 kubeconfig

将集群的 kubeconfig 文件放到本地，例如 `~/.kube/coroot-config`：

```bash
# 方式 1：从管理员处获取 kubeconfig 文件并拷贝到本地
scp admin@<master-node>:/etc/kubernetes/admin.conf ~/.kube/coroot-config

# 方式 2：如果已有文件，设置环境变量
export KUBECONFIG=~/.kube/coroot-config

# 验证连接
kubectl cluster-info
kubectl get nodes
```

> **提示**：后续所有 kubectl/helm 命令都需要 `KUBECONFIG` 环境变量，建议在当前 Shell 会话中 `export KUBECONFIG=~/.kube/coroot-config`，或在每条命令前加上 `KUBECONFIG=~/.kube/coroot-config`。

#### 获取项目源码

```bash
git clone <repo-url> train-ticket
cd train-ticket
```

### 1.2 创建 Namespace

```bash
kubectl create namespace train-ticket
```

### 1.3 部署基础设施

#### 步骤 1：部署 nacosdb (Nacos 专用 MySQL)

```bash
helm install nacosdb \
  --set mysql.mysqlUser=nacos \
  --set mysql.mysqlPassword='Abcd1234#' \
  --set mysql.mysqlDatabase=nacos \
  deployment/kubernetes-manifests/quickstart-k8s/charts/mysql \
  -n train-ticket
```

等待 nacosdb 就绪：

```bash
kubectl rollout status statefulset/nacosdb-mysql -n train-ticket
```

#### 步骤 2：部署 tsdb (应用 MySQL)

```bash
helm install tsdb \
  --set mysql.mysqlUser=ts \
  --set mysql.mysqlPassword=Ts_123456 \
  --set mysql.mysqlDatabase=ts \
  deployment/kubernetes-manifests/quickstart-k8s/charts/mysql \
  -n train-ticket
```

等待 tsdb 就绪：

```bash
kubectl rollout status statefulset/tsdb-mysql -n train-ticket
```

#### 步骤 3：修复 MySQL Xenon IPv6 Leader 选举问题

> **重要**：RadonDB 的 Xenon 组件通过 IPv6 (`::1`) 连接 MySQL 进行 Leader 选举。如果不执行此修复，follower 节点会出现 `PostStartHookError`，导致 MySQL 集群无法正常工作。

在所有 6 个 MySQL Pod 上执行：

```bash
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
```

验证修复：

```bash
# 检查所有 MySQL Pod 是否 3/3 Ready
kubectl get pods -n train-ticket -l app=nacosdb-mysql
kubectl get pods -n train-ticket -l app=tsdb-mysql
```

#### 步骤 4：部署 Nacos

```bash
helm install nacos \
  --set nacos.db.host=nacosdb-mysql-leader \
  --set nacos.db.username=nacos \
  --set nacos.db.name=nacos \
  --set nacos.db.password='Abcd1234#' \
  deployment/kubernetes-manifests/quickstart-k8s/charts/nacos \
  -n train-ticket
```

等待 Nacos 就绪：

```bash
kubectl rollout status statefulset/nacos -n train-ticket
```

#### 步骤 5：部署 RabbitMQ

```bash
helm install rabbitmq \
  deployment/kubernetes-manifests/quickstart-k8s/charts/rabbitmq \
  -n train-ticket
```

等待 RabbitMQ 就绪：

```bash
kubectl rollout status deployment/rabbitmq -n train-ticket
```

### 1.4 部署应用服务

#### 步骤 6：创建 Service 资源

```bash
kubectl apply -f deployment/kubernetes-manifests/quickstart-k8s/yamls/svc.yaml \
  -n train-ticket
```

#### 步骤 7：生成并应用 MySQL Secrets

> **注意**：`gen-mysql-secret.sh` 使用 bash 特有语法，必须用 bash 执行，不能用 zsh。

```bash
# 生成 secret.yaml（所有服务共享一个 MySQL 集群）
bash -c 'source hack/deploy/gen-mysql-secret.sh && \
  gen_secret_for_services ts Ts_123456 ts tsdb-mysql-leader'

# 应用 Secrets
kubectl apply -f deployment/kubernetes-manifests/quickstart-k8s/yamls/secret.yaml \
  -n train-ticket
```

#### 步骤 8：部署微服务 (含 OpenTelemetry)

```bash
kubectl apply -f deployment/kubernetes-manifests/quickstart-k8s/yamls/deploy-otel.yaml \
  -n train-ticket
```

### 1.5 等待所有 Pod 就绪

Java 微服务启动较慢（Spring Boot 初始化 + Hibernate + Nacos 注册），通常需要 3-5 分钟。

```bash
# 监控 Pod 启动进度
watch -n 5 'kubectl get pods -n train-ticket --no-headers | grep "0/1" | wc -l'

# 或者逐个等待
kubectl wait --for=condition=ready pod --all -n train-ticket --timeout=600s

# 查看完整状态
kubectl get pods -n train-ticket
```

预期结果：56 个 Pod 全部 `Running`，READY 为 `1/1`（微服务）或 `3/3`（MySQL）。

---

## 方案二：集群内直接部署

适用场景：直接 SSH 登录到 K8s Master 节点或集群内已配置 kubectl 的节点上执行部署。

### 2.1 前置条件

#### SSH 登录到 Master 节点

```bash
ssh root@<master-node-ip>
```

#### 验证集群状态

```bash
# Master 节点通常已预配置 kubectl
kubectl get nodes
kubectl cluster-info

# 确认 Helm 已安装
helm version
```

如果 Helm 未安装：

```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

#### 获取项目源码

```bash
git clone <repo-url> /opt/train-ticket
cd /opt/train-ticket
```

### 2.2 使用一键部署脚本（推荐）

项目提供了自动化部署脚本，在集群内可直接使用：

#### 快速部署（默认模式，共享数据库）

```bash
# 创建 Namespace
kubectl create namespace train-ticket

# 一键部署（所有服务共享一个 MySQL 集群）
bash hack/deploy/deploy.sh train-ticket
```

脚本将自动按顺序执行：
1. `deploy_infrastructures`: 部署 nacosdb → tsdb → Nacos → RabbitMQ
2. `deploy_tt_mysql_all_in_one`: 部署应用 MySQL（共享模式）
3. `deploy_tt_secret`: 生成并应用 MySQL Secrets
4. `deploy_tt_svc`: 创建所有 Service 资源
5. `deploy_tt_dp`: 部署所有微服务 Deployment

#### 完整部署（独立数据库 + 监控 + 链路追踪）

```bash
bash hack/deploy/deploy.sh train-ticket "--all"
```

#### 自定义组合部署

```bash
# 独立数据库（每个服务一个 MySQL 集群）
bash hack/deploy/deploy.sh train-ticket "--independent-db"

# 共享数据库 + 链路追踪 (SkyWalking)
bash hack/deploy/deploy.sh train-ticket "--with-tracing"

# 共享数据库 + 监控 (Prometheus/Grafana)
bash hack/deploy/deploy.sh train-ticket "--with-monitoring"
```

### 2.3 脚本部署后的手动修复

> **重要**：自动化脚本不包含 MySQL IPv6 修复步骤，需要手动执行。

```bash
# 等待所有 MySQL Pod 就绪
kubectl wait --for=condition=ready pod -l app=nacosdb-mysql -n train-ticket --timeout=300s
kubectl wait --for=condition=ready pod -l app=tsdb-mysql -n train-ticket --timeout=300s

# 执行 IPv6 修复
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
```

### 2.4 手动逐步部署（不使用脚本）

如果需要更精细的控制，可以按以下步骤手动执行：

```bash
# 0. 创建 Namespace
kubectl create namespace train-ticket

# 1. 部署 nacosdb
helm install nacosdb \
  --set mysql.mysqlUser=nacos \
  --set mysql.mysqlPassword='Abcd1234#' \
  --set mysql.mysqlDatabase=nacos \
  deployment/kubernetes-manifests/quickstart-k8s/charts/mysql \
  -n train-ticket
kubectl rollout status statefulset/nacosdb-mysql -n train-ticket

# 2. 部署 tsdb
helm install tsdb \
  --set mysql.mysqlUser=ts \
  --set mysql.mysqlPassword=Ts_123456 \
  --set mysql.mysqlDatabase=ts \
  deployment/kubernetes-manifests/quickstart-k8s/charts/mysql \
  -n train-ticket
kubectl rollout status statefulset/tsdb-mysql -n train-ticket

# 3. 修复 MySQL IPv6（同上，此处省略，参见 2.3 节）

# 4. 部署 Nacos
helm install nacos \
  --set nacos.db.host=nacosdb-mysql-leader \
  --set nacos.db.username=nacos \
  --set nacos.db.name=nacos \
  --set nacos.db.password='Abcd1234#' \
  deployment/kubernetes-manifests/quickstart-k8s/charts/nacos \
  -n train-ticket
kubectl rollout status statefulset/nacos -n train-ticket

# 5. 部署 RabbitMQ
helm install rabbitmq \
  deployment/kubernetes-manifests/quickstart-k8s/charts/rabbitmq \
  -n train-ticket
kubectl rollout status deployment/rabbitmq -n train-ticket

# 6. 部署 Services
kubectl apply -f deployment/kubernetes-manifests/quickstart-k8s/yamls/svc.yaml \
  -n train-ticket

# 7. 生成并部署 Secrets
bash -c 'source hack/deploy/gen-mysql-secret.sh && \
  gen_secret_for_services ts Ts_123456 ts tsdb-mysql-leader'
kubectl apply -f deployment/kubernetes-manifests/quickstart-k8s/yamls/secret.yaml \
  -n train-ticket

# 8. 部署微服务
kubectl apply -f deployment/kubernetes-manifests/quickstart-k8s/yamls/deploy-otel.yaml \
  -n train-ticket
```

---

## 部署后验证

### 检查 Pod 状态

```bash
# 查看所有 Pod
kubectl get pods -n train-ticket

# 统计各状态数量
kubectl get pods -n train-ticket --no-headers | awk '{print $3}' | sort | uniq -c

# 查看非 Ready 的 Pod
kubectl get pods -n train-ticket | grep -v "1/1\|3/3\|READY"
```

预期输出：56 个 Pod 全部 `Running`，0 个 `CrashLoopBackOff`。

### 检查 Helm Releases

```bash
helm list -n train-ticket
```

预期 4 个 release：`nacosdb`, `tsdb`, `nacos`, `rabbitmq`，状态均为 `deployed`。

### 检查 Service 暴露

```bash
# 查看 NodePort 服务
kubectl get svc -n train-ticket | grep NodePort
```

预期：
- `ts-gateway-service`: NodePort `30467`
- `ts-ui-dashboard`: NodePort `32677`

### 访问验证

```bash
# 通过任意集群节点 IP 访问
# UI Dashboard
curl -s -o /dev/null -w "%{http_code}" http://<node-ip>:32677

# Gateway API
curl -s -o /dev/null -w "%{http_code}" http://<node-ip>:30467

# Nacos Console
curl -s -o /dev/null -w "%{http_code}" http://<node-ip>:<nacos-nodeport>/nacos/
```

### 检查服务注册

```bash
# 进入 Nacos Console 检查注册的服务数量
# 浏览器访问 http://<node-ip>:<nacos-nodeport>/nacos/
# 登录凭证：nacos / nacos
# 在"服务管理 > 服务列表"中应看到所有微服务已注册
```

---

## 常见问题与修复

### 问题 1：MySQL Pod 出现 PostStartHookError

**症状**：MySQL follower Pod 状态为 `PostStartHookError`，无法启动。

**原因**：Xenon 通过 IPv6 (`::1`) 连接 MySQL 进行 Leader 选举，但默认未创建 IPv6 root 用户。

**修复**：

```bash
# 在每个 MySQL Pod 上执行
kubectl exec -n train-ticket <pod-name> -c mysql -- \
  mysql -uroot -e "
    CREATE USER IF NOT EXISTS 'root'@'::1' IDENTIFIED BY '';
    GRANT ALL PRIVILEGES ON *.* TO 'root'@'::1' WITH GRANT OPTION;
    FLUSH PRIVILEGES;
  "
```

### 问题 2：gen-mysql-secret.sh 报 `= not found` 错误

**症状**：运行 secret 生成脚本时报错。

**原因**：脚本使用 bash 语法 `[ $# == 4 ]`，在 zsh 下不兼容。

**修复**：始终使用 bash 执行：

```bash
bash -c 'source hack/deploy/gen-mysql-secret.sh && gen_secret_for_services ts Ts_123456 ts tsdb-mysql-leader'
```

### 问题 3：服务 CrashLoopBackOff（依赖版本冲突）

**症状**：某些服务反复重启，日志中出现 `NoSuchMethodError: SpelResolverConfiguration.spelResolver()`。

**原因**：`resilience4j-spring-boot2:1.7.1` 传递依赖拉入 `resilience4j-spring:1.7.0`，版本不匹配。

**修复**：
1. 确认父 POM 的 `<dependencyManagement>` 已固定 `resilience4j-spring:1.7.1`
2. 重新构建受影响服务的 Docker 镜像
3. 使用新 tag 推送镜像（K8s 节点 `imagePullPolicy: IfNotPresent` 会缓存旧镜像）

### 问题 4：deploy-otel.yaml 命名空间不匹配

**症状**：部署到非 `train-ticket` 命名空间时，资源创建在错误的 namespace。

**原因**：`deploy-otel.yaml` 中硬编码了 `namespace: train-ticket`。

**修复**：部署到其他命名空间前，先替换：

```bash
NEW_NS="your-namespace"
sed "s/namespace: train-ticket/namespace: ${NEW_NS}/g" \
  deployment/kubernetes-manifests/quickstart-k8s/yamls/deploy-otel.yaml \
  | kubectl apply -n ${NEW_NS} -f -
```

### 问题 5：ImagePullBackOff（私有镜像仓库）

**症状**：Pod 无法拉取镜像。

**原因**：默认 Helm Chart 使用公网镜像，私有环境需指向内部 Harbor 仓库。

**修复**：在 Helm 安装时通过 `--set` 指定私有镜像仓库地址：

```bash
# MySQL 示例
helm install nacosdb \
  --set mysql.image=<harbor-addr>/train-ticket/radondb-percona \
  --set mysql.tag=5.7.34 \
  --set xenon.image=<harbor-addr>/train-ticket/radondb-xenon \
  --set xenon.tag=1.1.5-helm \
  --set busybox.image=<harbor-addr>/train-ticket/busybox \
  --set busybox.tag=1.32 \
  --set metrics.image=<harbor-addr>/train-ticket/prom-mysqld-exporter \
  --set metrics.tag=v0.12.1 \
  deployment/kubernetes-manifests/quickstart-k8s/charts/mysql \
  -n train-ticket

# Nacos 示例
helm install nacos \
  --set nacos.image.repository=<harbor-addr>/train-ticket/nacos-nacos-server \
  --set nacos.image.tag=2.0.1 \
  --set initmysql.image=<harbor-addr>/train-ticket/codewisdom-mysqlclient:0.1 \
  ...

# RabbitMQ 示例
helm install rabbitmq \
  --set rabbitmq.image.repository=<harbor-addr>/train-ticket/codewisdom-rabbitmq \
  --set rabbitmq.image.tag=3 \
  ...
```

---

## 清理与重置

### 使用脚本清理

```bash
bash hack/deploy/reset.sh train-ticket
```

### 手动完整清理

```bash
NS=train-ticket

# 1. 删除应用 Deployment
kubectl delete -f deployment/kubernetes-manifests/quickstart-k8s/yamls/deploy-otel.yaml \
  -n $NS --ignore-not-found

# 2. 删除 Secrets
kubectl delete -f deployment/kubernetes-manifests/quickstart-k8s/yamls/secret.yaml \
  -n $NS --ignore-not-found

# 3. 删除 Services
kubectl delete -f deployment/kubernetes-manifests/quickstart-k8s/yamls/svc.yaml \
  -n $NS --ignore-not-found

# 4. 卸载 Helm Releases（逆序）
helm uninstall rabbitmq -n $NS
helm uninstall nacos -n $NS
helm uninstall tsdb -n $NS
helm uninstall nacosdb -n $NS

# 5. 清理 PVC（可选，删除后数据不可恢复）
kubectl delete pvc --all -n $NS

# 6. 删除 Namespace（可选）
kubectl delete namespace $NS
```

---

## 附录：凭证与端口表

### 凭证信息

| 组件 | 用户名 | 密码 | 用途 |
|------|--------|------|------|
| nacosdb MySQL | nacos | Abcd1234# | Nacos 注册中心后端数据库 |
| tsdb MySQL | ts | Ts_123456 | 微服务业务数据库 |
| MySQL root | root | (空) | 数据库管理 |
| Nacos Console | nacos | nacos | Nacos Web 管理界面 |
| RabbitMQ | guest | guest | 消息队列管理 |

### 端口映射

| 服务 | ClusterIP 端口 | NodePort |
|------|---------------|----------|
| ts-gateway-service | 18888 | 30467 |
| ts-ui-dashboard | 8080 | 32677 |
| nacos | 8848 | 自动分配 |

### 微服务端口列表

| 服务名 | 端口 | 服务名 | 端口 |
|--------|------|--------|------|
| ts-auth-service | 12340 | ts-order-service | 12031 |
| ts-user-service | 12342 | ts-order-other-service | 12032 |
| ts-contacts-service | 12347 | ts-travel-service | 12346 |
| ts-station-service | 12345 | ts-travel2-service | 16346 |
| ts-train-service | 14567 | ts-travel-plan-service | 14322 |
| ts-route-service | 11178 | ts-seat-service | 18898 |
| ts-config-service | 15679 | ts-basic-service | 15680 |
| ts-price-service | 16579 | ts-ticketinfo-service | 15681 |
| ts-security-service | 11188 | ts-preserve-service | 14568 |
| ts-inside-payment-service | 18673 | ts-preserve-other-service | 14569 |
| ts-payment-service | 19001 | ts-food-service | 18856 |
| ts-rebook-service | 18886 | ts-consign-service | 16111 |
| ts-cancel-service | 18885 | ts-consign-price-service | 16110 |
| ts-execute-service | 12386 | ts-admin-basic-info-service | 18767 |
| ts-notification-service | 17853 | ts-admin-order-service | 16112 |
| ts-avatar-service | 17001 | ts-admin-route-service | 16113 |
| ts-news-service | 12862 | ts-admin-travel-service | 16114 |
| ts-voucher-service | 16101 | ts-admin-user-service | 16115 |
| ts-assurance-service | 18888 | ts-delivery-service | 18808 |
| ts-ticket-office-service | 16108 | ts-food-delivery-service | 18957 |
| ts-verification-code-service | 15678 | ts-wait-order-service | 18009 |
| ts-gateway-service | 18888 | ts-station-food-service | 18855 |
| ts-train-food-service | 19999 | ts-ui-dashboard | 8080 |
| ts-route-plan-service | 14578 | | |
