# CLAUDE.md - Train-Ticket Microservice System

## Project Overview

Train-Ticket 是一个基于 Spring Boot + Spring Cloud 的微服务火车票系统，部署在 K8s 集群上，共 56 个 Pod（41 Java 服务 + 5 非 Java 服务 + 基础设施组件）。

## K8s Deployment

- **KUBECONFIG**: `~/.kube/coroot-config`
- **Namespace**: `train-ticket`
- **Harbor 镜像仓库**: `1.94.151.57:85/train-ticket` (HTTP insecure, admin/Harbor12345)
- **NodePort**: Gateway 30467, UI Dashboard 32677
- **部署顺序**: nacosdb(MySQL) -> tsdb(MySQL) -> Nacos -> RabbitMQ -> svc.yaml -> secrets -> deploy-otel.yaml

## Known Issues & Pitfalls

### 1. MySQL Xenon Leader 选举 IPv6 问题
MySQL RadonDB 的 Xenon 组件通过 IPv6 (::1) 连接 MySQL，需要在**每个 MySQL 节点**启动后执行：
```sql
CREATE USER IF NOT EXISTS 'root'@'::1' IDENTIFIED BY '';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'::1' WITH GRANT OPTION;
FLUSH PRIVILEGES;
```
不修复会导致 follower 节点 `PostStartHookError`。

### 2. gen-mysql-secret.sh 必须用 bash
该脚本使用 bash 特有语法 (`[ $# == 4 ]`)，在 zsh 下会报 `= not found` 错误：
```bash
bash -c 'source hack/deploy/gen-mysql-secret.sh && gen_secret_for_services ts Ts_123456 ts tsdb-mysql-leader'
```

### 3. Resilience4j 依赖版本冲突 (ts-preserve-service)
`resilience4j-spring-boot2:1.7.1` 会传递依赖拉入 `resilience4j-spring:1.7.0`，导致 `NoSuchMethodError: SpelResolverConfiguration.spelResolver()`。父 POM 的 `<dependencyManagement>` 已固定 `resilience4j-spring:1.7.1`，但如果 Docker 镜像是在此修复前构建的，需要重新构建。重建镜像后需使用新 tag（如 `1.0.0-fix2`），因为节点的 `imagePullPolicy: IfNotPresent` 会缓存旧镜像。

### 4. CoreDNS 镜像拉取问题
集群 CoreDNS 依赖 Harbor 镜像 `1.94.151.57:85/train-ticket/coredns:v1.10.1`（因 `sealos.hub:5000` 不可达）。从 macOS 推送 amd64 镜像到 Harbor 必须用 `crane copy --platform linux/amd64 --insecure`，不能用 `docker push`（会推 ARM 镜像）。

### 5. Docker 镜像构建注意事项
- 基础镜像使用 `eclipse-temurin:8-jre`（`java:8-jre` 已废弃）
- macOS 上构建需指定 `docker buildx build --platform linux/amd64`
- 更新同 tag 镜像时，K8s 节点会使用缓存，需要改 tag 或设 `imagePullPolicy: Always`

## Credentials

| Component | User | Password |
|-----------|------|----------|
| nacosdb MySQL | nacos | Abcd1234# |
| tsdb MySQL | ts | Ts_123456 |
| Nacos Console | nacos | nacos |
| RabbitMQ | guest | guest |
| Harbor | admin | Harbor12345 |

## Infrastructure

- **Coroot OTLP**: `http://coroot-coroot.coroot:8080`
- **NFS (OTel Agent)**: `1.94.151.57:/data/share`
- **Cluster Nodes**: tcse-flexusx-01(.148), tcse-v100-01(.197), tcse-v100-02(.138), tcse-v100-03(.118)
