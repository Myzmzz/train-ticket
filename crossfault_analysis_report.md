# CrossFault 分析报告：TrainTicket 系统跨维度耦合故障场景分析

> 生成时间：2026-03-17 | 分析工具：CrossFault v1.0 | 模型：Claude Opus 4.6 + Claude Sonnet 4


## 1. 系统概览

| 指标 | 数值 |
|------|------|
| 微服务总数 | 47 |
| 调用边总数（去重） | 90 |
| 集群节点数 | 4 |
| 业务路径数 | 12 |
| 命名空间 | train-ticket |

### 节点与服务分布

| 节点 | CPU | 内存 | 服务数 |
|------|-----|------|--------|
| tcse-flexusx-01 | 8 | 32370284Ki | 15 |
| tcse-v100-01 | 8 | 65544216Ki | 0 |
| tcse-v100-02 | 8 | 65544356Ki | 22 |
| tcse-v100-03 | 8 | 65544356Ki | 19 |

### 业务路径列表

| 路径名 | 入口服务 | 深度 | 涉及服务 |
|--------|----------|------|----------|
| 购票流程 | ts-preserve-service | 7 | ts-preserve-service, ts-seat-service, ts-security-service, ts-order-service, ts-contacts-service, ts-travel-service... |
| 购票流程（其他） | ts-preserve-other-service | 7 | ts-preserve-other-service, ts-seat-service, ts-security-service, ts-order-other-service, ts-travel2-service, ts-contacts-service... |
| 改签流程 | ts-rebook-service | 8 | ts-rebook-service, ts-seat-service, ts-inside-payment-service, ts-order-other-service, ts-travel2-service, ts-order-service... |
| 退票流程 | ts-cancel-service | 5 | ts-cancel-service, ts-inside-payment-service, ts-order-other-service, ts-order-service, ts-user-service |
| 支付流程 | ts-inside-payment-service | 4 | ts-inside-payment-service, ts-order-other-service, ts-order-service, ts-payment-service |
| 行程查询 | ts-travel-service | 7 | ts-travel-service, ts-seat-service, ts-train-service, ts-route-service, ts-order-service, ts-price-service... |
| 行程查询（其他） | ts-travel2-service | 7 | ts-travel2-service, ts-seat-service, ts-train-service, ts-route-service, ts-order-other-service, ts-price-service... |
| 路线规划 | ts-travel-plan-service | 6 | ts-travel-plan-service, ts-seat-service, ts-travel2-service, ts-travel-service, ts-route-plan-service, ts-station-service |
| 执行/检票流程 | ts-execute-service | 3 | ts-execute-service, ts-order-other-service, ts-order-service |
| 管理后台-基础信息 | ts-admin-basic-info-service | 6 | ts-admin-basic-info-service, ts-train-service, ts-price-service, ts-config-service, ts-contacts-service, ts-station-service |
| 管理后台-旅行管理 | ts-admin-travel-service | 3 | ts-admin-travel-service, ts-travel2-service, ts-travel-service |
| 管理后台-订单管理 | ts-admin-order-service | 3 | ts-admin-order-service, ts-order-other-service, ts-order-service |


## 2. 风险图谱摘要

### 2.1 K8s 配置风险统计

| 风险类型 | 数量 | 比例 | 严重程度 |
|----------|------|------|----------|
| 单副本部署 | 47/47 | 100% | 严重 |
| 缺少存活探针 | 47/47 | 100% | 高 |
| 缺少就绪探针 | 1/47 | 2% | 中 |
| 缺少资源限制 | 1/47 | 2% | 高 |
| 缺少反亲和性 | 47/47 | 100% | 低 |

**关键发现**：所有 47 个业务服务均为单副本部署，且全部缺少存活探针（livenessProbe）。这意味着任何服务发生进程假死（如死锁、内存泄漏导致的无响应），K8s 都无法自动重启，形成「僵死永久不可用」风险。

缺少就绪探针的服务：rabbitmq

缺少资源限制的服务：rabbitmq

### 2.2 调用拓扑风险

#### 扇入度 Top-10 服务

| 排名 | 服务 | 扇入度 | 上游调用方 |
|------|------|--------|-----------|
| 1 | ts-order-other-service | 8 | ts-admin-order-service, ts-cancel-service, ts-execute-service, ts-inside-payment-service, ts-preserve-other-service... |
| 2 | ts-order-service | 8 | ts-admin-order-service, ts-cancel-service, ts-execute-service, ts-inside-payment-service, ts-preserve-service... |
| 3 | ts-station-service | 8 | ts-admin-basic-info-service, ts-admin-route-service, ts-admin-travel-service, ts-basic-service, ts-order-other-service... |
| 4 | ts-route-service | 7 | ts-admin-route-service, ts-admin-travel-service, ts-basic-service, ts-rebook-service, ts-route-plan-service... |
| 5 | ts-train-service | 7 | ts-admin-basic-info-service, ts-admin-travel-service, ts-basic-service, ts-rebook-service, ts-travel-plan-service... |
| 6 | ts-seat-service | 6 | ts-preserve-other-service, ts-preserve-service, ts-rebook-service, ts-travel-plan-service, ts-travel-service... |
| 7 | ts-travel-service | 6 | ts-admin-travel-service, ts-food-service, ts-preserve-service, ts-rebook-service, ts-route-plan-service... |
| 8 | ts-travel2-service | 5 | ts-admin-travel-service, ts-preserve-other-service, ts-rebook-service, ts-route-plan-service, ts-travel-plan-service |
| 9 | ts-basic-service | 4 | ts-preserve-other-service, ts-preserve-service, ts-travel-service, ts-travel2-service |
| 10 | ts-user-service | 4 | ts-admin-user-service, ts-cancel-service, ts-preserve-other-service, ts-preserve-service |

#### 路径交叉度 Top-10 服务

| 排名 | 服务 | 路径交叉度 | 所在路径 |
|------|------|-----------|---------|
| 1 | ts-order-other-service | 7 | 购票流程（其他）, 改签流程, 退票流程, 支付流程 |
| 2 | ts-order-service | 7 | 购票流程, 改签流程, 退票流程, 支付流程 |
| 3 | ts-station-service | 7 | 购票流程, 购票流程（其他）, 改签流程, 行程查询 |
| 4 | ts-seat-service | 6 | 购票流程, 购票流程（其他）, 改签流程, 行程查询 |
| 5 | ts-travel-service | 5 | 购票流程, 改签流程, 行程查询, 路线规划 |
| 6 | ts-travel2-service | 5 | 购票流程（其他）, 改签流程, 行程查询（其他）, 路线规划 |
| 7 | ts-contacts-service | 3 | 购票流程, 购票流程（其他）, 管理后台-基础信息 |
| 8 | ts-inside-payment-service | 3 | 改签流程, 退票流程, 支付流程 |
| 9 | ts-price-service | 3 | 行程查询, 行程查询（其他）, 管理后台-基础信息 |
| 10 | ts-train-service | 3 | 行程查询, 行程查询（其他）, 管理后台-基础信息 |

#### 最深业务路径

- **改签流程**：深度=8，路径: ts-rebook-service → ts-seat-service → ts-inside-payment-service → ts-order-other-service → ts-travel2-service → ts-order-service → ts-travel-service → ts-station-service
- **购票流程**：深度=7，路径: ts-preserve-service → ts-seat-service → ts-security-service → ts-order-service → ts-contacts-service → ts-travel-service → ts-station-service
- **购票流程（其他）**：深度=7，路径: ts-preserve-other-service → ts-seat-service → ts-security-service → ts-order-other-service → ts-travel2-service → ts-contacts-service → ts-station-service

### 2.3 容错配置分析

#### 各保护级别的调用边数量分布

| 保护级别 | 数量 | 比例 | 说明 |
|----------|------|------|------|
| none | 70 | 78% | 完全无保护，故障直接传播 |
| timeout_only | 12 | 13% | 仅有超时保护，不能阻止级联 |
| flawed_retry | 4 | 4% | 有重试但无熔断器，会放大故障 |
| effective_cb | 3 | 3% | 有效的熔断器保护 |
| flawed_cb | 1 | 1% | 熔断器配置有缺陷（如阈值过高） |

#### 完全无保护的调用边（共70条）

| 调用方 | 被调方 | β系数 |
|--------|--------|-------|
| ts-admin-basic-info-service | ts-train-service | 10 |
| ts-admin-basic-info-service | ts-price-service | 10 |
| ts-admin-basic-info-service | ts-config-service | 10 |
| ts-admin-basic-info-service | ts-contacts-service | 10 |
| ts-admin-basic-info-service | ts-station-service | 10 |
| ts-admin-order-service | ts-order-other-service | 10 |
| ts-admin-order-service | ts-order-service | 10 |
| ts-admin-route-service | ts-route-service | 10 |
| ts-admin-route-service | ts-station-service | 10 |
| ts-admin-travel-service | ts-train-service | 10 |
| ts-admin-travel-service | ts-travel2-service | 10 |
| ts-admin-travel-service | ts-travel-service | 10 |
| ts-admin-travel-service | ts-route-service | 10 |
| ts-admin-travel-service | ts-station-service | 10 |
| ts-admin-user-service | ts-user-service | 10 |
| ts-auth-service | ts-verification-code-service | 10 |
| ts-basic-service | ts-price-service | 10 |
| ts-basic-service | ts-train-service | 10 |
| ts-basic-service | ts-route-service | 10 |
| ts-basic-service | ts-station-service | 10 |
| ... | ... | ... |
| *共70条* | | |

#### 有缺陷保护的调用边（重试无熔断器）

| 调用方 | 被调方 | 重试次数 | 退避 | β系数 | 来源 |
|--------|--------|----------|------|-------|------|
| ts-preserve-service | ts-seat-service | 3 | fixed 500ms | 1.8 | ts-preserve-service/src/main/java/preserve/service/PreserveS |
| ts-preserve-service | ts-order-service | 5 | none | 5 | ts-preserve-service/src/main/java/preserve/service/PreserveS |
| ts-rebook-service | ts-order-other-service | 5 | none | 5 | ts-rebook-service/src/main/java/rebook/service/RebookService |
| ts-rebook-service | ts-order-service | 5 | none | 5 | ts-rebook-service/src/main/java/rebook/service/RebookService |

#### 传播放大系数 β 最高的 Top-10 调用边

| 排名 | 调用方 | 被调方 | β系数 | 保护级别 |
|------|--------|--------|-------|----------|
| 1 | ts-admin-basic-info-service | ts-train-service | 10 | none |
| 2 | ts-admin-basic-info-service | ts-price-service | 10 | none |
| 3 | ts-admin-basic-info-service | ts-config-service | 10 | none |
| 4 | ts-admin-basic-info-service | ts-contacts-service | 10 | none |
| 5 | ts-admin-basic-info-service | ts-station-service | 10 | none |
| 6 | ts-admin-order-service | ts-order-other-service | 10 | none |
| 7 | ts-admin-order-service | ts-order-service | 10 | none |
| 8 | ts-admin-route-service | ts-route-service | 10 | none |
| 9 | ts-admin-route-service | ts-station-service | 10 | none |
| 10 | ts-admin-travel-service | ts-train-service | 10 | none |

### 2.4 物理资源风险

#### 各节点的服务分布

**tcse-flexusx-01** (15 个服务)：
  nacos, nacosdb-mysql, ts-assurance-service, ts-contacts-service, ts-delivery-service, ts-food-delivery-service, ts-payment-service, ts-preserve-service, ts-route-plan-service, ts-station-food-service, ts-train-food-service, ts-train-service, ts-user-service, ts-wait-order-service, tsdb-mysql

**tcse-v100-02** (22 个服务)：
  nacos, nacosdb-mysql, rabbitmq, ts-admin-basic-info-service, ts-admin-order-service, ts-admin-route-service, ts-admin-travel-service, ts-avatar-service, ts-basic-service, ts-consign-price-service, ts-consign-service, ts-execute-service, ts-inside-payment-service, ts-notification-service, ts-price-service, ts-route-service, ts-ticket-office-service, ts-travel-plan-service, ts-travel-service, ts-ui-dashboard, ts-verification-code-service, tsdb-mysql

**tcse-v100-03** (19 个服务)：
  nacos, nacosdb-mysql, ts-admin-user-service, ts-auth-service, ts-cancel-service, ts-config-service, ts-food-service, ts-gateway-service, ts-news-service, ts-order-other-service, ts-order-service, ts-preserve-other-service, ts-rebook-service, ts-seat-service, ts-security-service, ts-station-service, ts-travel2-service, ts-voucher-service, tsdb-mysql

#### 同节点共置且无资源限制的服务组


#### QoS 等级分布

- Burstable: 47 个服务


## 3. RiskRank 排序结果

### 服务风险排名 Top-15

| 排名 | 服务 | RiskRank | 本地风险 | 扇入度 | 扇出度 | 路径交叉度 | 主要风险因素 |
|------|------|----------|----------|--------|--------|-----------|------------|
| 1 | ts-user-service | 100.00 | 0 | 4 | 1 | 1 | 单副本, 无存活探针 |
| 2 | ts-auth-service | 95.00 | 0 | 1 | 1 | 0 | 单副本, 无存活探针 |
| 3 | ts-verification-code-service | 80.49 | 0 | 1 | 0 | 0 | 单副本, 无存活探针 |
| 4 | ts-preserve-service | 49.01 | 0 | 1 | 11 | 1 | 单副本, 无存活探针 |
| 5 | ts-wait-order-service | 39.55 | 0 | 0 | 1 | 0 | 单副本, 无存活探针 |
| 6 | ts-preserve-other-service | 28.34 | 0 | 0 | 11 | 1 | 单副本, 无存活探针 |
| 7 | ts-station-service | 16.59 | 0 | 8 | 0 | 7 | 单副本, 无存活探针, 高扇入(8) |
| 8 | ts-cancel-service | 16.27 | 0 | 0 | 5 | 1 | 单副本, 无存活探针 |
| 9 | ts-admin-user-service | 13.18 | 0 | 0 | 1 | 0 | 单副本, 无存活探针 |
| 10 | ts-order-other-service | 11.21 | 0 | 8 | 1 | 7 | 单副本, 无存活探针, 高扇入(8) |
| 11 | ts-consign-service | 10.21 | 0 | 2 | 1 | 0 | 单副本, 无存活探针 |
| 12 | ts-basic-service | 9.53 | 0 | 4 | 4 | 0 | 单副本, 无存活探针 |
| 13 | ts-order-service | 9.47 | 0 | 8 | 1 | 7 | 单副本, 无存活探针, 高扇入(8) |
| 14 | ts-food-service | 8.37 | 0 | 2 | 3 | 0 | 单副本, 无存活探针 |
| 15 | ts-security-service | 7.30 | 0 | 2 | 2 | 2 | 单副本, 无存活探针 |

### 业务路径风险排名

| 排名 | 路径 | PathRisk | 深度 | 关键瓶颈 |
|------|------|----------|------|----------|
| 1 | 退票流程 | 138.19 | 5 | ts-user-service(RR=100.0) |
| 2 | 购票流程 | 101.33 | 7 | ts-preserve-service(RR=49.0) |
| 3 | 购票流程（其他） | 81.87 | 7 | ts-preserve-other-service(RR=28.3) |
| 4 | 改签流程 | 61.10 | 8 | ts-station-service(RR=16.6) |
| 5 | 行程查询（其他） | 49.78 | 7 | ts-station-service(RR=16.6) |
| 6 | 行程查询 | 48.57 | 7 | ts-station-service(RR=16.6) |
| 7 | 路线规划 | 35.52 | 6 | ts-station-service(RR=16.6) |
| 8 | 管理后台-基础信息 | 35.00 | 6 | ts-station-service(RR=16.6) |
| 9 | 执行/检票流程 | 22.32 | 3 | ts-order-other-service(RR=11.2) |
| 10 | 管理后台-订单管理 | 22.32 | 3 | ts-order-other-service(RR=11.2) |
| 11 | 支付流程 | 21.92 | 4 | ts-order-other-service(RR=11.2) |
| 12 | 管理后台-旅行管理 | 15.61 | 3 | ts-travel-service(RR=6.3) |

### 焦点服务列表

共 23 个焦点服务（RiskRank Top-15 + 路径交叉度>1）：

- **ts-user-service** (RR=100.00, 路径交叉度=1)
- **ts-auth-service** (RR=95.00, 路径交叉度=0)
- **ts-verification-code-service** (RR=80.49, 路径交叉度=0)
- **ts-preserve-service** (RR=49.01, 路径交叉度=1)
- **ts-wait-order-service** (RR=39.55, 路径交叉度=0)
- **ts-preserve-other-service** (RR=28.34, 路径交叉度=1)
- **ts-station-service** (RR=16.59, 路径交叉度=7)
- **ts-cancel-service** (RR=16.27, 路径交叉度=1)
- **ts-admin-user-service** (RR=13.18, 路径交叉度=0)
- **ts-order-other-service** (RR=11.21, 路径交叉度=7)
- **ts-consign-service** (RR=10.21, 路径交叉度=0)
- **ts-basic-service** (RR=9.53, 路径交叉度=0)
- **ts-order-service** (RR=9.47, 路径交叉度=7)
- **ts-food-service** (RR=8.37, 路径交叉度=0)
- **ts-security-service** (RR=7.30, 路径交叉度=2)
- **ts-seat-service** (RR=6.40, 路径交叉度=6)
- **ts-travel-service** (RR=6.31, 路径交叉度=5)
- **ts-contacts-service** (RR=6.26, 路径交叉度=3)
- **ts-travel2-service** (RR=5.78, 路径交叉度=5)
- **ts-train-service** (RR=3.89, 路径交叉度=3)
- **ts-route-service** (RR=3.88, 路径交叉度=2)
- **ts-price-service** (RR=2.03, 路径交叉度=3)
- **ts-inside-payment-service** (RR=1.24, 路径交叉度=3)


## 4. 故障模式分析

### 4.1 ts-user-service 的故障模式 (RR=100.00)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| USE-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| USE-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| USE-FM3 | 不可预测的超时传播 | R_TF2 | 拓扑×容错 | 高 | 5 |

**USE-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**USE-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-flexusx-01
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**USE-FM3: 不可预测的超时传播** (高)

- **匹配规则**: R_TF2
- **涉及风险**: 深调用链(路径'退票流程'深度=5); 链上超时配置不一致
- **触发条件**: 链末端服务响应变慢
- **本地影响**: 超时在链上逐级放大，行为不可预测
- **传播方向**: 沿调用链向上游逐级传播
- **放大系数**: 5


### 4.2 ts-auth-service 的故障模式 (RR=95.00)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| AUT-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| AUT-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |

**AUT-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**AUT-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-03
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1


### 4.3 ts-verification-code-service 的故障模式 (RR=80.49)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| VER-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| VER-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |

**VER-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**VER-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-02
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1


### 4.4 ts-preserve-service 的故障模式 (RR=49.01)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| PRE-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| PRE-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| PRE-FM3 | 不可预测的超时传播 | R_TF2 | 拓扑×容错 | 高 | 7 |
| PRE-FM4 | 双通道耦合 | R_FR1 | 容错×资源 | 高 | 2 |

**PRE-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**PRE-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-flexusx-01
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**PRE-FM3: 不可预测的超时传播** (高)

- **匹配规则**: R_TF2
- **涉及风险**: 深调用链(路径'购票流程'深度=7); 链上超时配置不一致
- **触发条件**: 链末端服务响应变慢
- **本地影响**: 超时在链上逐级放大，行为不可预测
- **传播方向**: 沿调用链向上游逐级传播
- **放大系数**: 7

**PRE-FM4: 双通道耦合** (高)

- **匹配规则**: R_FR1
- **涉及风险**: 出边 ts-preserve-service→ts-assurance-service: 无超时; 两服务同节点(tcse-flexusx-01)共置
- **触发条件**: ts-assurance-service高负载或资源争抢
- **本地影响**: 调用链阻塞 + 同节点资源争抢双重影响
- **传播方向**: 调用链传播 + 物理层传播
- **放大系数**: 2


### 4.5 ts-wait-order-service 的故障模式 (RR=39.55)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| WAI-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| WAI-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| WAI-FM3 | 双通道耦合 | R_FR1 | 容错×资源 | 高 | 2 |

**WAI-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**WAI-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-flexusx-01
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**WAI-FM3: 双通道耦合** (高)

- **匹配规则**: R_FR1
- **涉及风险**: 出边 ts-wait-order-service→ts-preserve-service: 无超时; 两服务同节点(tcse-flexusx-01)共置
- **触发条件**: ts-preserve-service高负载或资源争抢
- **本地影响**: 调用链阻塞 + 同节点资源争抢双重影响
- **传播方向**: 调用链传播 + 物理层传播
- **放大系数**: 2


### 4.6 ts-preserve-other-service 的故障模式 (RR=28.34)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| PRE-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| PRE-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| PRE-FM3 | 不可预测的超时传播 | R_TF2 | 拓扑×容错 | 高 | 7 |
| PRE-FM4 | 双通道耦合 | R_FR1 | 容错×资源 | 高 | 2 |

**PRE-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**PRE-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-03
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**PRE-FM3: 不可预测的超时传播** (高)

- **匹配规则**: R_TF2
- **涉及风险**: 深调用链(路径'购票流程（其他）'深度=7); 链上超时配置不一致
- **触发条件**: 链末端服务响应变慢
- **本地影响**: 超时在链上逐级放大，行为不可预测
- **传播方向**: 沿调用链向上游逐级传播
- **放大系数**: 7

**PRE-FM4: 双通道耦合** (高)

- **匹配规则**: R_FR1
- **涉及风险**: 出边 ts-preserve-other-service→ts-seat-service: 无超时; 两服务同节点(tcse-v100-03)共置
- **触发条件**: ts-seat-service高负载或资源争抢
- **本地影响**: 调用链阻塞 + 同节点资源争抢双重影响
- **传播方向**: 调用链传播 + 物理层传播
- **放大系数**: 2


### 4.7 ts-station-service 的故障模式 (RR=16.59)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| STA-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| STA-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| STA-FM3 | 汇聚放大 | R_TF1 | 拓扑×容错 | 严重 | 80.0 |
| STA-FM4 | 不可预测的超时传播 | R_TF2 | 拓扑×容错 | 高 | 7 |
| STA-FM5 | 多路径峰值叠加 | R_TR1 | 拓扑×资源 | 高 | 7 |

**STA-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**STA-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-03
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**STA-FM3: 汇聚放大** (严重)

- **匹配规则**: R_TF1
- **涉及风险**: 高扇入度(in_degree=8); 有风险入边7条(flawed_retry=0, none=7)
- **触发条件**: 服务响应变慢或间歇性失败
- **本地影响**: 多个上游同时重试/阻塞，流量激增
- **传播方向**: 多个上游同时受影响
- **放大系数**: 80.0

**STA-FM4: 不可预测的超时传播** (高)

- **匹配规则**: R_TF2
- **涉及风险**: 深调用链(路径'购票流程'深度=7); 链上超时配置不一致
- **触发条件**: 链末端服务响应变慢
- **本地影响**: 超时在链上逐级放大，行为不可预测
- **传播方向**: 沿调用链向上游逐级传播
- **放大系数**: 7

**STA-FM5: 多路径峰值叠加** (高)

- **匹配规则**: R_TR1
- **涉及风险**: 路径交叉度=7; 同节点共置业务服务: ts-cancel-service, ts-config-service, ts-order-other-service, ts-order-service, ts-preserve-other-service
- **触发条件**: 多条业务路径同时高负载
- **本地影响**: 多路径流量叠加，节点资源饱和
- **传播方向**: 影响同节点所有服务 + 向多条业务路径传播
- **放大系数**: 7


### 4.8 ts-cancel-service 的故障模式 (RR=16.27)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| CAN-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| CAN-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| CAN-FM3 | 不可预测的超时传播 | R_TF2 | 拓扑×容错 | 高 | 5 |
| CAN-FM4 | 双通道耦合 | R_FR1 | 容错×资源 | 高 | 2 |

**CAN-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**CAN-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-03
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**CAN-FM3: 不可预测的超时传播** (高)

- **匹配规则**: R_TF2
- **涉及风险**: 深调用链(路径'退票流程'深度=5); 链上超时配置不一致
- **触发条件**: 链末端服务响应变慢
- **本地影响**: 超时在链上逐级放大，行为不可预测
- **传播方向**: 沿调用链向上游逐级传播
- **放大系数**: 5

**CAN-FM4: 双通道耦合** (高)

- **匹配规则**: R_FR1
- **涉及风险**: 出边 ts-cancel-service→ts-order-other-service: 无超时; 两服务同节点(tcse-v100-03)共置
- **触发条件**: ts-order-other-service高负载或资源争抢
- **本地影响**: 调用链阻塞 + 同节点资源争抢双重影响
- **传播方向**: 调用链传播 + 物理层传播
- **放大系数**: 2


### 4.9 ts-admin-user-service 的故障模式 (RR=13.18)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| ADM-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| ADM-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |

**ADM-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**ADM-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-03
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1


### 4.10 ts-order-other-service 的故障模式 (RR=11.21)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| ORD-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| ORD-FM2 | 重试风暴阻止恢复 | R_CF1 | 配置×容错 | 严重 | 5 |
| ORD-FM3 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| ORD-FM4 | 汇聚放大 | R_TF1 | 拓扑×容错 | 严重 | 75.0 |
| ORD-FM5 | 不可预测的超时传播 | R_TF2 | 拓扑×容错 | 高 | 7 |
| ORD-FM6 | 多路径峰值叠加 | R_TR1 | 拓扑×资源 | 高 | 7 |
| ORD-FM7 | 双通道耦合 | R_FR1 | 容错×资源 | 高 | 2 |

**ORD-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**ORD-FM2: 重试风暴阻止恢复** (严重)

- **匹配规则**: R_CF1
- **涉及风险**: 单副本(replicas=1); 入边 ts-rebook-service→ts-order-other-service: retry=5/backoff=none/no CB
- **触发条件**: 容器实例崩溃或进程异常退出
- **本地影响**: 服务完全不可用且无法恢复，重试流量持续涌入
- **传播方向**: 自我恶化 + 向上游传播错误
- **放大系数**: 5

**ORD-FM3: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-03
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**ORD-FM4: 汇聚放大** (严重)

- **匹配规则**: R_TF1
- **涉及风险**: 高扇入度(in_degree=8); 有风险入边8条(flawed_retry=1, none=7)
- **触发条件**: 服务响应变慢或间歇性失败
- **本地影响**: 多个上游同时重试/阻塞，流量激增
- **传播方向**: 多个上游同时受影响
- **放大系数**: 75.0

**ORD-FM5: 不可预测的超时传播** (高)

- **匹配规则**: R_TF2
- **涉及风险**: 深调用链(路径'购票流程（其他）'深度=7); 链上超时配置不一致
- **触发条件**: 链末端服务响应变慢
- **本地影响**: 超时在链上逐级放大，行为不可预测
- **传播方向**: 沿调用链向上游逐级传播
- **放大系数**: 7

**ORD-FM6: 多路径峰值叠加** (高)

- **匹配规则**: R_TR1
- **涉及风险**: 路径交叉度=7; 同节点共置业务服务: ts-cancel-service, ts-config-service, ts-order-service, ts-preserve-other-service, ts-rebook-service
- **触发条件**: 多条业务路径同时高负载
- **本地影响**: 多路径流量叠加，节点资源饱和
- **传播方向**: 影响同节点所有服务 + 向多条业务路径传播
- **放大系数**: 7

**ORD-FM7: 双通道耦合** (高)

- **匹配规则**: R_FR1
- **涉及风险**: 出边 ts-order-other-service→ts-station-service: 无超时; 两服务同节点(tcse-v100-03)共置
- **触发条件**: ts-station-service高负载或资源争抢
- **本地影响**: 调用链阻塞 + 同节点资源争抢双重影响
- **传播方向**: 调用链传播 + 物理层传播
- **放大系数**: 2


### 4.11 ts-consign-service 的故障模式 (RR=10.21)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| CON-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| CON-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| CON-FM3 | 双通道耦合 | R_FR1 | 容错×资源 | 高 | 2 |

**CON-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**CON-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-02
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**CON-FM3: 双通道耦合** (高)

- **匹配规则**: R_FR1
- **涉及风险**: 出边 ts-consign-service→ts-consign-price-service: 无超时; 两服务同节点(tcse-v100-02)共置
- **触发条件**: ts-consign-price-service高负载或资源争抢
- **本地影响**: 调用链阻塞 + 同节点资源争抢双重影响
- **传播方向**: 调用链传播 + 物理层传播
- **放大系数**: 2


### 4.12 ts-basic-service 的故障模式 (RR=9.53)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| BAS-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| BAS-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| BAS-FM3 | 功能完全不可用 | R_TF3 | 拓扑×容错 | 高 | 1 |
| BAS-FM4 | 双通道耦合 | R_FR1 | 容错×资源 | 高 | 2 |

**BAS-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**BAS-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-02
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**BAS-FM3: 功能完全不可用** (高)

- **匹配规则**: R_TF3
- **涉及风险**: 单副本(replicas=1); 入边 ts-travel-service→ts-basic-service: 仅超时保护; 无降级方案
- **触发条件**: 服务实例不可用
- **本地影响**: 调用方ts-travel-service的相关功能完全不可用
- **传播方向**: 向上游传播功能缺失
- **放大系数**: 1

**BAS-FM4: 双通道耦合** (高)

- **匹配规则**: R_FR1
- **涉及风险**: 出边 ts-basic-service→ts-price-service: 无超时; 两服务同节点(tcse-v100-02)共置
- **触发条件**: ts-price-service高负载或资源争抢
- **本地影响**: 调用链阻塞 + 同节点资源争抢双重影响
- **传播方向**: 调用链传播 + 物理层传播
- **放大系数**: 2


### 4.13 ts-order-service 的故障模式 (RR=9.47)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| ORD-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| ORD-FM2 | 重试风暴阻止恢复 | R_CF1 | 配置×容错 | 严重 | 10 |
| ORD-FM3 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| ORD-FM4 | 汇聚放大 | R_TF1 | 拓扑×容错 | 严重 | 68.6 |
| ORD-FM5 | 不可预测的超时传播 | R_TF2 | 拓扑×容错 | 高 | 7 |
| ORD-FM6 | 多路径峰值叠加 | R_TR1 | 拓扑×资源 | 高 | 7 |

**ORD-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**ORD-FM2: 重试风暴阻止恢复** (严重)

- **匹配规则**: R_CF1
- **涉及风险**: 单副本(replicas=1); 入边 ts-rebook-service→ts-order-service: retry=5/backoff=none/no CB; 入边 ts-preserve-service→ts-order-service: retry=5/backoff=none/no CB
- **触发条件**: 容器实例崩溃或进程异常退出
- **本地影响**: 服务完全不可用且无法恢复，重试流量持续涌入
- **传播方向**: 自我恶化 + 向上游传播错误
- **放大系数**: 10

**ORD-FM3: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-03
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**ORD-FM4: 汇聚放大** (严重)

- **匹配规则**: R_TF1
- **涉及风险**: 高扇入度(in_degree=8); 有风险入边7条(flawed_retry=2, none=5)
- **触发条件**: 服务响应变慢或间歇性失败
- **本地影响**: 多个上游同时重试/阻塞，流量激增
- **传播方向**: 多个上游同时受影响
- **放大系数**: 68.6

**ORD-FM5: 不可预测的超时传播** (高)

- **匹配规则**: R_TF2
- **涉及风险**: 深调用链(路径'购票流程'深度=7); 链上超时配置不一致
- **触发条件**: 链末端服务响应变慢
- **本地影响**: 超时在链上逐级放大，行为不可预测
- **传播方向**: 沿调用链向上游逐级传播
- **放大系数**: 7

**ORD-FM6: 多路径峰值叠加** (高)

- **匹配规则**: R_TR1
- **涉及风险**: 路径交叉度=7; 同节点共置业务服务: ts-cancel-service, ts-config-service, ts-order-other-service, ts-preserve-other-service, ts-rebook-service
- **触发条件**: 多条业务路径同时高负载
- **本地影响**: 多路径流量叠加，节点资源饱和
- **传播方向**: 影响同节点所有服务 + 向多条业务路径传播
- **放大系数**: 7


### 4.14 ts-food-service 的故障模式 (RR=8.37)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| FOO-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| FOO-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |

**FOO-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**FOO-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-03
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1


### 4.15 ts-security-service 的故障模式 (RR=7.30)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| SEC-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| SEC-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| SEC-FM3 | 不可预测的超时传播 | R_TF2 | 拓扑×容错 | 高 | 7 |
| SEC-FM4 | 多路径峰值叠加 | R_TR1 | 拓扑×资源 | 高 | 2 |
| SEC-FM5 | 双通道耦合 | R_FR1 | 容错×资源 | 高 | 2 |

**SEC-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**SEC-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-03
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**SEC-FM3: 不可预测的超时传播** (高)

- **匹配规则**: R_TF2
- **涉及风险**: 深调用链(路径'购票流程'深度=7); 链上超时配置不一致
- **触发条件**: 链末端服务响应变慢
- **本地影响**: 超时在链上逐级放大，行为不可预测
- **传播方向**: 沿调用链向上游逐级传播
- **放大系数**: 7

**SEC-FM4: 多路径峰值叠加** (高)

- **匹配规则**: R_TR1
- **涉及风险**: 路径交叉度=2; 同节点共置业务服务: ts-cancel-service, ts-config-service, ts-order-other-service, ts-order-service, ts-preserve-other-service
- **触发条件**: 多条业务路径同时高负载
- **本地影响**: 多路径流量叠加，节点资源饱和
- **传播方向**: 影响同节点所有服务 + 向多条业务路径传播
- **放大系数**: 2

**SEC-FM5: 双通道耦合** (高)

- **匹配规则**: R_FR1
- **涉及风险**: 出边 ts-security-service→ts-order-other-service: 无超时; 两服务同节点(tcse-v100-03)共置
- **触发条件**: ts-order-other-service高负载或资源争抢
- **本地影响**: 调用链阻塞 + 同节点资源争抢双重影响
- **传播方向**: 调用链传播 + 物理层传播
- **放大系数**: 2


### 4.16 ts-seat-service 的故障模式 (RR=6.40)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| SEA-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| SEA-FM2 | 重试风暴阻止恢复 | R_CF1 | 配置×容错 | 严重 | 1.8 |
| SEA-FM3 | 延迟恢复 | R_CF3 | 配置×容错 | 中 | 1.8 |
| SEA-FM4 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| SEA-FM5 | 汇聚放大 | R_TF1 | 拓扑×容错 | 高 | 47.7 |
| SEA-FM6 | 不可预测的超时传播 | R_TF2 | 拓扑×容错 | 高 | 7 |
| SEA-FM7 | 功能完全不可用 | R_TF3 | 拓扑×容错 | 高 | 1 |
| SEA-FM8 | 多路径峰值叠加 | R_TR1 | 拓扑×资源 | 高 | 6 |
| SEA-FM9 | 双通道耦合 | R_FR1 | 容错×资源 | 高 | 2 |

**SEA-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**SEA-FM2: 重试风暴阻止恢复** (严重)

- **匹配规则**: R_CF1
- **涉及风险**: 单副本(replicas=1); 入边 ts-preserve-service→ts-seat-service: retry=3/backoff=fixed 500ms/no CB
- **触发条件**: 容器实例崩溃或进程异常退出
- **本地影响**: 服务完全不可用且无法恢复，重试流量持续涌入
- **传播方向**: 自我恶化 + 向上游传播错误
- **放大系数**: 1.8

**SEA-FM3: 延迟恢复** (中)

- **匹配规则**: R_CF3
- **涉及风险**: 单副本(replicas=1); 入边 ts-preserve-service→ts-seat-service: retry+backoff/no CB
- **触发条件**: 服务短暂不可用后恢复
- **本地影响**: 退避重试减缓恢复速度但不阻止恢复
- **传播方向**: 向上游传播延迟
- **放大系数**: 1.8

**SEA-FM4: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-03
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**SEA-FM5: 汇聚放大** (高)

- **匹配规则**: R_TF1
- **涉及风险**: 高扇入度(in_degree=6); 有风险入边4条(flawed_retry=1, none=3)
- **触发条件**: 服务响应变慢或间歇性失败
- **本地影响**: 多个上游同时重试/阻塞，流量激增
- **传播方向**: 多个上游同时受影响
- **放大系数**: 47.7

**SEA-FM6: 不可预测的超时传播** (高)

- **匹配规则**: R_TF2
- **涉及风险**: 深调用链(路径'购票流程'深度=7); 链上超时配置不一致
- **触发条件**: 链末端服务响应变慢
- **本地影响**: 超时在链上逐级放大，行为不可预测
- **传播方向**: 沿调用链向上游逐级传播
- **放大系数**: 7

**SEA-FM7: 功能完全不可用** (高)

- **匹配规则**: R_TF3
- **涉及风险**: 单副本(replicas=1); 入边 ts-travel-service→ts-seat-service: 仅超时保护; 无降级方案
- **触发条件**: 服务实例不可用
- **本地影响**: 调用方ts-travel-service的相关功能完全不可用
- **传播方向**: 向上游传播功能缺失
- **放大系数**: 1

**SEA-FM8: 多路径峰值叠加** (高)

- **匹配规则**: R_TR1
- **涉及风险**: 路径交叉度=6; 同节点共置业务服务: ts-cancel-service, ts-config-service, ts-order-other-service, ts-order-service, ts-preserve-other-service
- **触发条件**: 多条业务路径同时高负载
- **本地影响**: 多路径流量叠加，节点资源饱和
- **传播方向**: 影响同节点所有服务 + 向多条业务路径传播
- **放大系数**: 6

**SEA-FM9: 双通道耦合** (高)

- **匹配规则**: R_FR1
- **涉及风险**: 出边 ts-seat-service→ts-order-other-service: 无超时; 两服务同节点(tcse-v100-03)共置
- **触发条件**: ts-order-other-service高负载或资源争抢
- **本地影响**: 调用链阻塞 + 同节点资源争抢双重影响
- **传播方向**: 调用链传播 + 物理层传播
- **放大系数**: 2


### 4.17 ts-travel-service 的故障模式 (RR=6.31)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| TRA-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| TRA-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| TRA-FM3 | 汇聚放大 | R_TF1 | 拓扑×容错 | 严重 | 60.0 |
| TRA-FM4 | 不可预测的超时传播 | R_TF2 | 拓扑×容错 | 高 | 7 |
| TRA-FM5 | 功能完全不可用 | R_TF3 | 拓扑×容错 | 高 | 1 |
| TRA-FM6 | 多路径峰值叠加 | R_TR1 | 拓扑×资源 | 高 | 5 |

**TRA-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**TRA-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-02
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**TRA-FM3: 汇聚放大** (严重)

- **匹配规则**: R_TF1
- **涉及风险**: 高扇入度(in_degree=6); 有风险入边4条(flawed_retry=0, none=4)
- **触发条件**: 服务响应变慢或间歇性失败
- **本地影响**: 多个上游同时重试/阻塞，流量激增
- **传播方向**: 多个上游同时受影响
- **放大系数**: 60.0

**TRA-FM4: 不可预测的超时传播** (高)

- **匹配规则**: R_TF2
- **涉及风险**: 深调用链(路径'购票流程'深度=7); 链上超时配置不一致
- **触发条件**: 链末端服务响应变慢
- **本地影响**: 超时在链上逐级放大，行为不可预测
- **传播方向**: 沿调用链向上游逐级传播
- **放大系数**: 7

**TRA-FM5: 功能完全不可用** (高)

- **匹配规则**: R_TF3
- **涉及风险**: 单副本(replicas=1); 入边 ts-travel-plan-service→ts-travel-service: 仅超时保护; 无降级方案
- **触发条件**: 服务实例不可用
- **本地影响**: 调用方ts-travel-plan-service的相关功能完全不可用
- **传播方向**: 向上游传播功能缺失
- **放大系数**: 1

**TRA-FM6: 多路径峰值叠加** (高)

- **匹配规则**: R_TR1
- **涉及风险**: 路径交叉度=5; 同节点共置业务服务: ts-admin-basic-info-service, ts-admin-order-service, ts-admin-travel-service, ts-execute-service, ts-inside-payment-service
- **触发条件**: 多条业务路径同时高负载
- **本地影响**: 多路径流量叠加，节点资源饱和
- **传播方向**: 影响同节点所有服务 + 向多条业务路径传播
- **放大系数**: 5


### 4.18 ts-contacts-service 的故障模式 (RR=6.26)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| CON-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| CON-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| CON-FM3 | 不可预测的超时传播 | R_TF2 | 拓扑×容错 | 高 | 7 |
| CON-FM4 | 多路径峰值叠加 | R_TR1 | 拓扑×资源 | 高 | 3 |

**CON-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**CON-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-flexusx-01
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**CON-FM3: 不可预测的超时传播** (高)

- **匹配规则**: R_TF2
- **涉及风险**: 深调用链(路径'购票流程'深度=7); 链上超时配置不一致
- **触发条件**: 链末端服务响应变慢
- **本地影响**: 超时在链上逐级放大，行为不可预测
- **传播方向**: 沿调用链向上游逐级传播
- **放大系数**: 7

**CON-FM4: 多路径峰值叠加** (高)

- **匹配规则**: R_TR1
- **涉及风险**: 路径交叉度=3; 同节点共置业务服务: ts-payment-service, ts-preserve-service, ts-route-plan-service, ts-train-service, ts-user-service
- **触发条件**: 多条业务路径同时高负载
- **本地影响**: 多路径流量叠加，节点资源饱和
- **传播方向**: 影响同节点所有服务 + 向多条业务路径传播
- **放大系数**: 3


### 4.19 ts-travel2-service 的故障模式 (RR=5.78)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| TRA-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| TRA-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| TRA-FM3 | 汇聚放大 | R_TF1 | 拓扑×容错 | 高 | 50.0 |
| TRA-FM4 | 不可预测的超时传播 | R_TF2 | 拓扑×容错 | 高 | 7 |
| TRA-FM5 | 功能完全不可用 | R_TF3 | 拓扑×容错 | 高 | 1 |
| TRA-FM6 | 多路径峰值叠加 | R_TR1 | 拓扑×资源 | 高 | 5 |
| TRA-FM7 | 双通道耦合 | R_FR1 | 容错×资源 | 高 | 2 |

**TRA-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**TRA-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-03
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**TRA-FM3: 汇聚放大** (高)

- **匹配规则**: R_TF1
- **涉及风险**: 高扇入度(in_degree=5); 有风险入边3条(flawed_retry=0, none=3)
- **触发条件**: 服务响应变慢或间歇性失败
- **本地影响**: 多个上游同时重试/阻塞，流量激增
- **传播方向**: 多个上游同时受影响
- **放大系数**: 50.0

**TRA-FM4: 不可预测的超时传播** (高)

- **匹配规则**: R_TF2
- **涉及风险**: 深调用链(路径'购票流程（其他）'深度=7); 链上超时配置不一致
- **触发条件**: 链末端服务响应变慢
- **本地影响**: 超时在链上逐级放大，行为不可预测
- **传播方向**: 沿调用链向上游逐级传播
- **放大系数**: 7

**TRA-FM5: 功能完全不可用** (高)

- **匹配规则**: R_TF3
- **涉及风险**: 单副本(replicas=1); 入边 ts-travel-plan-service→ts-travel2-service: 仅超时保护; 无降级方案
- **触发条件**: 服务实例不可用
- **本地影响**: 调用方ts-travel-plan-service的相关功能完全不可用
- **传播方向**: 向上游传播功能缺失
- **放大系数**: 1

**TRA-FM6: 多路径峰值叠加** (高)

- **匹配规则**: R_TR1
- **涉及风险**: 路径交叉度=5; 同节点共置业务服务: ts-cancel-service, ts-config-service, ts-order-other-service, ts-order-service, ts-preserve-other-service
- **触发条件**: 多条业务路径同时高负载
- **本地影响**: 多路径流量叠加，节点资源饱和
- **传播方向**: 影响同节点所有服务 + 向多条业务路径传播
- **放大系数**: 5

**TRA-FM7: 双通道耦合** (高)

- **匹配规则**: R_FR1
- **涉及风险**: 出边 ts-travel2-service→ts-seat-service: 无超时; 两服务同节点(tcse-v100-03)共置
- **触发条件**: ts-seat-service高负载或资源争抢
- **本地影响**: 调用链阻塞 + 同节点资源争抢双重影响
- **传播方向**: 调用链传播 + 物理层传播
- **放大系数**: 2


### 4.20 ts-train-service 的故障模式 (RR=3.89)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| TRA-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| TRA-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| TRA-FM3 | 汇聚放大 | R_TF1 | 拓扑×容错 | 严重 | 70.0 |
| TRA-FM4 | 不可预测的超时传播 | R_TF2 | 拓扑×容错 | 高 | 7 |
| TRA-FM5 | 功能完全不可用 | R_TF3 | 拓扑×容错 | 高 | 1 |
| TRA-FM6 | 多路径峰值叠加 | R_TR1 | 拓扑×资源 | 高 | 3 |

**TRA-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**TRA-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-flexusx-01
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**TRA-FM3: 汇聚放大** (严重)

- **匹配规则**: R_TF1
- **涉及风险**: 高扇入度(in_degree=7); 有风险入边5条(flawed_retry=0, none=5)
- **触发条件**: 服务响应变慢或间歇性失败
- **本地影响**: 多个上游同时重试/阻塞，流量激增
- **传播方向**: 多个上游同时受影响
- **放大系数**: 70.0

**TRA-FM4: 不可预测的超时传播** (高)

- **匹配规则**: R_TF2
- **涉及风险**: 深调用链(路径'行程查询（其他）'深度=7); 链上超时配置不一致
- **触发条件**: 链末端服务响应变慢
- **本地影响**: 超时在链上逐级放大，行为不可预测
- **传播方向**: 沿调用链向上游逐级传播
- **放大系数**: 7

**TRA-FM5: 功能完全不可用** (高)

- **匹配规则**: R_TF3
- **涉及风险**: 单副本(replicas=1); 入边 ts-travel-plan-service→ts-train-service: 仅超时保护; 无降级方案
- **触发条件**: 服务实例不可用
- **本地影响**: 调用方ts-travel-plan-service的相关功能完全不可用
- **传播方向**: 向上游传播功能缺失
- **放大系数**: 1

**TRA-FM6: 多路径峰值叠加** (高)

- **匹配规则**: R_TR1
- **涉及风险**: 路径交叉度=3; 同节点共置业务服务: ts-contacts-service, ts-payment-service, ts-preserve-service, ts-route-plan-service, ts-user-service
- **触发条件**: 多条业务路径同时高负载
- **本地影响**: 多路径流量叠加，节点资源饱和
- **传播方向**: 影响同节点所有服务 + 向多条业务路径传播
- **放大系数**: 3


### 4.21 ts-route-service 的故障模式 (RR=3.88)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| ROU-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| ROU-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| ROU-FM3 | 汇聚放大 | R_TF1 | 拓扑×容错 | 严重 | 70.0 |
| ROU-FM4 | 不可预测的超时传播 | R_TF2 | 拓扑×容错 | 高 | 7 |
| ROU-FM5 | 功能完全不可用 | R_TF3 | 拓扑×容错 | 高 | 1 |
| ROU-FM6 | 多路径峰值叠加 | R_TR1 | 拓扑×资源 | 高 | 2 |

**ROU-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**ROU-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-02
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**ROU-FM3: 汇聚放大** (严重)

- **匹配规则**: R_TF1
- **涉及风险**: 高扇入度(in_degree=7); 有风险入边5条(flawed_retry=0, none=5)
- **触发条件**: 服务响应变慢或间歇性失败
- **本地影响**: 多个上游同时重试/阻塞，流量激增
- **传播方向**: 多个上游同时受影响
- **放大系数**: 70.0

**ROU-FM4: 不可预测的超时传播** (高)

- **匹配规则**: R_TF2
- **涉及风险**: 深调用链(路径'行程查询（其他）'深度=7); 链上超时配置不一致
- **触发条件**: 链末端服务响应变慢
- **本地影响**: 超时在链上逐级放大，行为不可预测
- **传播方向**: 沿调用链向上游逐级传播
- **放大系数**: 7

**ROU-FM5: 功能完全不可用** (高)

- **匹配规则**: R_TF3
- **涉及风险**: 单副本(replicas=1); 入边 ts-travel-service→ts-route-service: 仅超时保护; 无降级方案
- **触发条件**: 服务实例不可用
- **本地影响**: 调用方ts-travel-service的相关功能完全不可用
- **传播方向**: 向上游传播功能缺失
- **放大系数**: 1

**ROU-FM6: 多路径峰值叠加** (高)

- **匹配规则**: R_TR1
- **涉及风险**: 路径交叉度=2; 同节点共置业务服务: ts-admin-basic-info-service, ts-admin-order-service, ts-admin-travel-service, ts-execute-service, ts-inside-payment-service
- **触发条件**: 多条业务路径同时高负载
- **本地影响**: 多路径流量叠加，节点资源饱和
- **传播方向**: 影响同节点所有服务 + 向多条业务路径传播
- **放大系数**: 2


### 4.22 ts-price-service 的故障模式 (RR=2.03)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| PRI-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| PRI-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| PRI-FM3 | 不可预测的超时传播 | R_TF2 | 拓扑×容错 | 高 | 7 |
| PRI-FM4 | 多路径峰值叠加 | R_TR1 | 拓扑×资源 | 高 | 3 |

**PRI-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**PRI-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-02
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**PRI-FM3: 不可预测的超时传播** (高)

- **匹配规则**: R_TF2
- **涉及风险**: 深调用链(路径'行程查询（其他）'深度=7); 链上超时配置不一致
- **触发条件**: 链末端服务响应变慢
- **本地影响**: 超时在链上逐级放大，行为不可预测
- **传播方向**: 沿调用链向上游逐级传播
- **放大系数**: 7

**PRI-FM4: 多路径峰值叠加** (高)

- **匹配规则**: R_TR1
- **涉及风险**: 路径交叉度=3; 同节点共置业务服务: ts-admin-basic-info-service, ts-admin-order-service, ts-admin-travel-service, ts-execute-service, ts-inside-payment-service
- **触发条件**: 多条业务路径同时高负载
- **本地影响**: 多路径流量叠加，节点资源饱和
- **传播方向**: 影响同节点所有服务 + 向多条业务路径传播
- **放大系数**: 3


### 4.23 ts-inside-payment-service 的故障模式 (RR=1.24)

| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |
|--------|---------|---------|------|---------|---------|
| INS-FM1 | 僵死永久不可用 | R_CC1 | 配置×配置 | 严重 | 1 |
| INS-FM2 | 抢占驱逐 | R_CR2 | 配置×资源 | 中 | 1 |
| INS-FM3 | 不可预测的超时传播 | R_TF2 | 拓扑×容错 | 高 | 8 |
| INS-FM4 | 多路径峰值叠加 | R_TR1 | 拓扑×资源 | 高 | 3 |

**INS-FM1: 僵死永久不可用** (严重)

- **匹配规则**: R_CC1
- **涉及风险**: 单副本(replicas=1); 无存活探针(livenessProbe=false)
- **触发条件**: 容器进程死锁或内存泄漏导致进程假死
- **本地影响**: 服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启
- **传播方向**: 向上游传播超时/错误
- **放大系数**: 1

**INS-FM2: 抢占驱逐** (中)

- **匹配规则**: R_CR2
- **涉及风险**: 单副本(replicas=1); QoS=Burstable; 节点=tcse-v100-02
- **触发条件**: 节点资源压力触发驱逐
- **本地影响**: Pod 被驱逐，服务完全不可用直到重新调度
- **传播方向**: 向上游传播不可用
- **放大系数**: 1

**INS-FM3: 不可预测的超时传播** (高)

- **匹配规则**: R_TF2
- **涉及风险**: 深调用链(路径'改签流程'深度=8); 链上超时配置不一致
- **触发条件**: 链末端服务响应变慢
- **本地影响**: 超时在链上逐级放大，行为不可预测
- **传播方向**: 沿调用链向上游逐级传播
- **放大系数**: 8

**INS-FM4: 多路径峰值叠加** (高)

- **匹配规则**: R_TR1
- **涉及风险**: 路径交叉度=3; 同节点共置业务服务: ts-admin-basic-info-service, ts-admin-order-service, ts-admin-travel-service, ts-execute-service, ts-price-service
- **触发条件**: 多条业务路径同时高负载
- **本地影响**: 多路径流量叠加，节点资源饱和
- **传播方向**: 影响同节点所有服务 + 向多条业务路径传播
- **放大系数**: 3



## 5. 传播链分析

共识别 **30** 条传播链和 **60** 个自我恶化环路。

### 传播链 Top-10（按风险排序）

**链1**: 不可预测的超时传播 @ ts-order-other-service
- 路径: ts-order-other-service → ts-cancel-service → ts-order-service → ts-seat-service
- 涉及服务: 4 个
- 累计放大: 70000
- 严重程度: 高

**链2**: 不可预测的超时传播 @ ts-order-other-service
- 路径: ts-order-other-service → ts-cancel-service → ts-order-service → ts-security-service
- 涉及服务: 4 个
- 累计放大: 70000
- 严重程度: 高

**链3**: 多路径峰值叠加 @ ts-order-other-service
- 路径: ts-order-other-service → ts-cancel-service → ts-order-service → ts-seat-service
- 涉及服务: 4 个
- 累计放大: 70000
- 严重程度: 高

**链4**: 多路径峰值叠加 @ ts-order-other-service
- 路径: ts-order-other-service → ts-cancel-service → ts-order-service → ts-security-service
- 涉及服务: 4 个
- 累计放大: 70000
- 严重程度: 高

**链5**: 重试风暴阻止恢复 @ ts-order-service
- 路径: ts-order-service → ts-cancel-service → ts-order-other-service → ts-inside-payment-service
- 涉及服务: 4 个
- 累计放大: 70000
- 严重程度: 严重

**链6**: 重试风暴阻止恢复 @ ts-order-service
- 路径: ts-order-service → ts-cancel-service → ts-order-other-service → ts-preserve-other-service
- 涉及服务: 4 个
- 累计放大: 70000
- 严重程度: 严重

**链7**: 重试风暴阻止恢复 @ ts-order-service
- 路径: ts-order-service → ts-cancel-service → ts-order-other-service → ts-seat-service
- 涉及服务: 4 个
- 累计放大: 70000
- 严重程度: 严重

**链8**: 重试风暴阻止恢复 @ ts-order-service
- 路径: ts-order-service → ts-cancel-service → ts-order-other-service → ts-security-service
- 涉及服务: 4 个
- 累计放大: 70000
- 严重程度: 严重

**链9**: 不可预测的超时传播 @ ts-order-other-service
- 路径: ts-order-other-service → ts-seat-service → ts-order-service → ts-cancel-service
- 涉及服务: 4 个
- 累计放大: 70000
- 严重程度: 高

**链10**: 不可预测的超时传播 @ ts-order-other-service
- 路径: ts-order-other-service → ts-seat-service → ts-order-service → ts-security-service
- 涉及服务: 4 个
- 累计放大: 70000
- 严重程度: 高

### 自我恶化环路

- **ts-station-service故障 → ts-order-other-service重试 → ts-station-service负载加重** (放大系数=50)
  - 下游故障模式: 僵死永久不可用
  - 上游故障模式: 重试风暴阻止恢复
- **ts-station-service故障 → ts-order-other-service重试 → ts-station-service负载加重** (放大系数=750)
  - 下游故障模式: 僵死永久不可用
  - 上游故障模式: 汇聚放大
- **ts-station-service故障 → ts-order-other-service重试 → ts-station-service负载加重** (放大系数=50)
  - 下游故障模式: 抢占驱逐
  - 上游故障模式: 重试风暴阻止恢复
- **ts-station-service故障 → ts-order-other-service重试 → ts-station-service负载加重** (放大系数=750)
  - 下游故障模式: 抢占驱逐
  - 上游故障模式: 汇聚放大
- **ts-station-service故障 → ts-order-other-service重试 → ts-station-service负载加重** (放大系数=50)
  - 下游故障模式: 不可预测的超时传播
  - 上游故障模式: 重试风暴阻止恢复
- **ts-station-service故障 → ts-order-other-service重试 → ts-station-service负载加重** (放大系数=750)
  - 下游故障模式: 不可预测的超时传播
  - 上游故障模式: 汇聚放大
- **ts-station-service故障 → ts-order-other-service重试 → ts-station-service负载加重** (放大系数=50)
  - 下游故障模式: 多路径峰值叠加
  - 上游故障模式: 重试风暴阻止恢复
- **ts-station-service故障 → ts-order-other-service重试 → ts-station-service负载加重** (放大系数=750)
  - 下游故障模式: 多路径峰值叠加
  - 上游故障模式: 汇聚放大
- **ts-station-service故障 → ts-order-service重试 → ts-station-service负载加重** (放大系数=12)
  - 下游故障模式: 僵死永久不可用
  - 上游故障模式: 重试风暴阻止恢复
- **ts-station-service故障 → ts-order-service重试 → ts-station-service负载加重** (放大系数=82)
  - 下游故障模式: 僵死永久不可用
  - 上游故障模式: 汇聚放大
- **ts-station-service故障 → ts-order-service重试 → ts-station-service负载加重** (放大系数=12)
  - 下游故障模式: 抢占驱逐
  - 上游故障模式: 重试风暴阻止恢复
- **ts-station-service故障 → ts-order-service重试 → ts-station-service负载加重** (放大系数=82)
  - 下游故障模式: 抢占驱逐
  - 上游故障模式: 汇聚放大
- **ts-station-service故障 → ts-order-service重试 → ts-station-service负载加重** (放大系数=12)
  - 下游故障模式: 不可预测的超时传播
  - 上游故障模式: 重试风暴阻止恢复
- **ts-station-service故障 → ts-order-service重试 → ts-station-service负载加重** (放大系数=82)
  - 下游故障模式: 不可预测的超时传播
  - 上游故障模式: 汇聚放大
- **ts-station-service故障 → ts-order-service重试 → ts-station-service负载加重** (放大系数=12)
  - 下游故障模式: 多路径峰值叠加
  - 上游故障模式: 重试风暴阻止恢复
- **ts-station-service故障 → ts-order-service重试 → ts-station-service负载加重** (放大系数=82)
  - 下游故障模式: 多路径峰值叠加
  - 上游故障模式: 汇聚放大
- **ts-order-other-service故障 → ts-seat-service重试 → ts-order-other-service负载加重** (放大系数=18)
  - 下游故障模式: 僵死永久不可用
  - 上游故障模式: 重试风暴阻止恢复
- **ts-order-other-service故障 → ts-seat-service重试 → ts-order-other-service负载加重** (放大系数=477)
  - 下游故障模式: 僵死永久不可用
  - 上游故障模式: 汇聚放大
- **ts-order-other-service故障 → ts-seat-service重试 → ts-order-other-service负载加重** (放大系数=18)
  - 下游故障模式: 重试风暴阻止恢复
  - 上游故障模式: 重试风暴阻止恢复
- **ts-order-other-service故障 → ts-seat-service重试 → ts-order-other-service负载加重** (放大系数=477)
  - 下游故障模式: 重试风暴阻止恢复
  - 上游故障模式: 汇聚放大
- **ts-order-other-service故障 → ts-seat-service重试 → ts-order-other-service负载加重** (放大系数=18)
  - 下游故障模式: 抢占驱逐
  - 上游故障模式: 重试风暴阻止恢复
- **ts-order-other-service故障 → ts-seat-service重试 → ts-order-other-service负载加重** (放大系数=477)
  - 下游故障模式: 抢占驱逐
  - 上游故障模式: 汇聚放大
- **ts-order-other-service故障 → ts-seat-service重试 → ts-order-other-service负载加重** (放大系数=18)
  - 下游故障模式: 不可预测的超时传播
  - 上游故障模式: 重试风暴阻止恢复
- **ts-order-other-service故障 → ts-seat-service重试 → ts-order-other-service负载加重** (放大系数=477)
  - 下游故障模式: 不可预测的超时传播
  - 上游故障模式: 汇聚放大
- **ts-order-other-service故障 → ts-seat-service重试 → ts-order-other-service负载加重** (放大系数=18)
  - 下游故障模式: 多路径峰值叠加
  - 上游故障模式: 重试风暴阻止恢复
- **ts-order-other-service故障 → ts-seat-service重试 → ts-order-other-service负载加重** (放大系数=477)
  - 下游故障模式: 多路径峰值叠加
  - 上游故障模式: 汇聚放大
- **ts-order-other-service故障 → ts-seat-service重试 → ts-order-other-service负载加重** (放大系数=18)
  - 下游故障模式: 双通道耦合
  - 上游故障模式: 重试风暴阻止恢复
- **ts-order-other-service故障 → ts-seat-service重试 → ts-order-other-service负载加重** (放大系数=477)
  - 下游故障模式: 双通道耦合
  - 上游故障模式: 汇聚放大
- **ts-order-service故障 → ts-seat-service重试 → ts-order-service负载加重** (放大系数=18)
  - 下游故障模式: 僵死永久不可用
  - 上游故障模式: 重试风暴阻止恢复
- **ts-order-service故障 → ts-seat-service重试 → ts-order-service负载加重** (放大系数=477)
  - 下游故障模式: 僵死永久不可用
  - 上游故障模式: 汇聚放大
- **ts-order-service故障 → ts-seat-service重试 → ts-order-service负载加重** (放大系数=18)
  - 下游故障模式: 重试风暴阻止恢复
  - 上游故障模式: 重试风暴阻止恢复
- **ts-order-service故障 → ts-seat-service重试 → ts-order-service负载加重** (放大系数=477)
  - 下游故障模式: 重试风暴阻止恢复
  - 上游故障模式: 汇聚放大
- **ts-order-service故障 → ts-seat-service重试 → ts-order-service负载加重** (放大系数=18)
  - 下游故障模式: 抢占驱逐
  - 上游故障模式: 重试风暴阻止恢复
- **ts-order-service故障 → ts-seat-service重试 → ts-order-service负载加重** (放大系数=477)
  - 下游故障模式: 抢占驱逐
  - 上游故障模式: 汇聚放大
- **ts-order-service故障 → ts-seat-service重试 → ts-order-service负载加重** (放大系数=18)
  - 下游故障模式: 不可预测的超时传播
  - 上游故障模式: 重试风暴阻止恢复
- **ts-order-service故障 → ts-seat-service重试 → ts-order-service负载加重** (放大系数=477)
  - 下游故障模式: 不可预测的超时传播
  - 上游故障模式: 汇聚放大
- **ts-order-service故障 → ts-seat-service重试 → ts-order-service负载加重** (放大系数=18)
  - 下游故障模式: 多路径峰值叠加
  - 上游故障模式: 重试风暴阻止恢复
- **ts-order-service故障 → ts-seat-service重试 → ts-order-service负载加重** (放大系数=477)
  - 下游故障模式: 多路径峰值叠加
  - 上游故障模式: 汇聚放大
- **ts-basic-service故障 → ts-travel2-service重试 → ts-basic-service负载加重** (放大系数=500)
  - 下游故障模式: 僵死永久不可用
  - 上游故障模式: 汇聚放大
- **ts-basic-service故障 → ts-travel2-service重试 → ts-basic-service负载加重** (放大系数=500)
  - 下游故障模式: 抢占驱逐
  - 上游故障模式: 汇聚放大
- **ts-basic-service故障 → ts-travel2-service重试 → ts-basic-service负载加重** (放大系数=500)
  - 下游故障模式: 功能完全不可用
  - 上游故障模式: 汇聚放大
- **ts-basic-service故障 → ts-travel2-service重试 → ts-basic-service负载加重** (放大系数=500)
  - 下游故障模式: 双通道耦合
  - 上游故障模式: 汇聚放大
- **ts-route-service故障 → ts-travel2-service重试 → ts-route-service负载加重** (放大系数=500)
  - 下游故障模式: 僵死永久不可用
  - 上游故障模式: 汇聚放大
- **ts-route-service故障 → ts-travel2-service重试 → ts-route-service负载加重** (放大系数=500)
  - 下游故障模式: 抢占驱逐
  - 上游故障模式: 汇聚放大
- **ts-route-service故障 → ts-travel2-service重试 → ts-route-service负载加重** (放大系数=500)
  - 下游故障模式: 不可预测的超时传播
  - 上游故障模式: 汇聚放大
- **ts-route-service故障 → ts-travel2-service重试 → ts-route-service负载加重** (放大系数=500)
  - 下游故障模式: 功能完全不可用
  - 上游故障模式: 汇聚放大
- **ts-route-service故障 → ts-travel2-service重试 → ts-route-service负载加重** (放大系数=500)
  - 下游故障模式: 多路径峰值叠加
  - 上游故障模式: 汇聚放大
- **ts-seat-service故障 → ts-travel2-service重试 → ts-seat-service负载加重** (放大系数=500)
  - 下游故障模式: 僵死永久不可用
  - 上游故障模式: 汇聚放大
- **ts-seat-service故障 → ts-travel2-service重试 → ts-seat-service负载加重** (放大系数=500)
  - 下游故障模式: 重试风暴阻止恢复
  - 上游故障模式: 汇聚放大
- **ts-seat-service故障 → ts-travel2-service重试 → ts-seat-service负载加重** (放大系数=500)
  - 下游故障模式: 延迟恢复
  - 上游故障模式: 汇聚放大
- **ts-seat-service故障 → ts-travel2-service重试 → ts-seat-service负载加重** (放大系数=500)
  - 下游故障模式: 抢占驱逐
  - 上游故障模式: 汇聚放大
- **ts-seat-service故障 → ts-travel2-service重试 → ts-seat-service负载加重** (放大系数=500)
  - 下游故障模式: 不可预测的超时传播
  - 上游故障模式: 汇聚放大
- **ts-seat-service故障 → ts-travel2-service重试 → ts-seat-service负载加重** (放大系数=500)
  - 下游故障模式: 功能完全不可用
  - 上游故障模式: 汇聚放大
- **ts-seat-service故障 → ts-travel2-service重试 → ts-seat-service负载加重** (放大系数=500)
  - 下游故障模式: 多路径峰值叠加
  - 上游故障模式: 汇聚放大
- **ts-seat-service故障 → ts-travel2-service重试 → ts-seat-service负载加重** (放大系数=500)
  - 下游故障模式: 双通道耦合
  - 上游故障模式: 汇聚放大
- **ts-train-service故障 → ts-travel2-service重试 → ts-train-service负载加重** (放大系数=500)
  - 下游故障模式: 僵死永久不可用
  - 上游故障模式: 汇聚放大
- **ts-train-service故障 → ts-travel2-service重试 → ts-train-service负载加重** (放大系数=500)
  - 下游故障模式: 抢占驱逐
  - 上游故障模式: 汇聚放大
- **ts-train-service故障 → ts-travel2-service重试 → ts-train-service负载加重** (放大系数=500)
  - 下游故障模式: 不可预测的超时传播
  - 上游故障模式: 汇聚放大
- **ts-train-service故障 → ts-travel2-service重试 → ts-train-service负载加重** (放大系数=500)
  - 下游故障模式: 功能完全不可用
  - 上游故障模式: 汇聚放大
- **ts-train-service故障 → ts-travel2-service重试 → ts-train-service负载加重** (放大系数=500)
  - 下游故障模式: 多路径峰值叠加
  - 上游故障模式: 汇聚放大


## 6. 故障场景设计（核心产出）

### 场景 SCN-001: 基于不可预测超时传播的级联故障场景

- **注入目标**: ts-order-other-service
- **注入方式**: network-delay
- **注入参数**: {"delay": "8s", "jitter": "2s", "target_port": 80, "protocol": "tcp"}
- **触发条件**: 退票流程高负载期间
- **持续时间**: 180s
- **选择理由**: 选择网络延迟而非pod-kill是因为ORD-FM5模式的核心是'超时在链上逐级放大'。延迟注入能够精确触发超时传播机制，而且8s延迟超过了大多数服务的默认超时阈值，能够激活整个传播链的超时级联效应。这比直接杀死pod更能体现深调用链中超时配置不一致的风险。

**预测级联路径**:

  **Step 1**: ts-order-other-service响应时间从正常的100ms激增至8-10秒，触发ORD-FM5模式
  - 机制: 网络延迟直接影响服务响应时间，激活了'不可预测的超时传播'故障模式
  - 受影响服务: ts-order-other-service
  - 证据: ORD-FM5: 深调用链(路径'购票流程（其他）'深度=7), 链上超时配置不一致, 放大系数=7

  **Step 2**: ts-cancel-service调用ts-order-other-service时发生超时，由于无超时保护配置，默认超时被触发，调用阻塞
  - 机制: 调用边ts-cancel-service→ts-order-other-service无任何容错保护，超时开始向上游传播
  - 受影响服务: ts-cancel-service
  - 证据: 调用边容错配置: retry=false, circuit_breaker=false, timeout=false, 保护级别=none, beta=10

  **Step 3**: ts-cancel-service因下游阻塞而自身响应变慢，触发CAN-FM3模式，超时逐级放大效应开始显现
  - 机制: ts-cancel-service作为退票流程链上的中间节点，超时从下游传播至此并被放大
  - 受影响服务: ts-cancel-service
  - 证据: CAN-FM3: 深调用链(路径'退票流程'深度=5), 链上超时配置不一致, 放大系数=5

  **Step 4**: ts-cancel-service调用ts-order-service时超时传播继续，ts-order-service开始出现响应延迟
  - 机制: 调用边ts-cancel-service→ts-order-service同样无容错保护，超时继续沿链传播
  - 受影响服务: ts-order-service
  - 证据: 调用边容错配置: retry=false, circuit_breaker=false, timeout=false, 保护级别=none, beta=10

  **Step 5**: ts-seat-service调用ts-order-service时遭遇超时，由于ts-seat-service具有高扇入度(6个上游)，开始触发SEA-FM5汇聚放大效应
  - 机制: ts-seat-service的多个上游服务同时遭遇下游响应慢，汇聚点流量激增
  - 受影响服务: ts-seat-service
  - 证据: SEA-FM5: 高扇入度(in_degree=6), 有风险入边4条, 汇聚放大系数=47.7

  **Step 6**: 由于所有涉及服务都部署在同一节点tcse-v100-03上，阻塞的请求开始消耗节点资源，加剧了资源争抢
  - 机制: 物理层耦合放大了逻辑层故障，16个共置服务开始相互影响
  - 受影响服务: tcse-v100-03节点上的所有服务
  - 证据: 共置服务数量=16, QoS=Burstable允许资源争抢, 无反亲和性配置

  **Step 7**: 级联故障完全展开：退票流程不可用，购票流程（其他）严重受损，多条业务路径同时故障
  - 机制: 累积放大效应=70000，多维度耦合导致局部延迟演变为系统性故障
  - 受影响服务: 整个服务网格
  - 证据: 传播链累积放大系数=70000, 影响4个核心服务, 7条业务路径受损

- **影响范围**: 退票流程, 购票流程（其他）, 改签流程, 支付流程, 行程查询（其他）, 执行/检票流程, 管理后台-订单管理
- **严重程度**: 严重
- **风险评分**: 95/100
- **核心洞察**: 这个场景揭示了微服务架构中的三重耦合陷阱：1)调用链维度-深度调用链缺乏超时配置导致故障逐级放大；2)拓扑维度-高扇入度服务成为汇聚放大点；3)物理维度-密集共置放大了逻辑故障的影响半径。单一8秒网络延迟通过这种三维耦合效应被放大70000倍，证明了在缺乏适当隔离机制的情况下，看似轻微的性能问题如何演变为系统性灾难。

**修复分析**：如果修复某个风险会怎样？

- 若为 ts-order-other-service 添加存活探针 → 进程假死可被自动检测并重启，阻断级联传播起点
- 若为 ts-order-other-service 增加副本数到2+ → 单实例故障不会导致服务完全不可用

### 场景 SCN-002: 多路径峰值叠加引发的级联故障

- **注入目标**: ts-order-other-service
- **注入方式**: cpu-stress
- **注入参数**: {"cpu_percent": 95, "workers": 4, "target_pods": "all"}
- **触发条件**: 购票流程（其他）、改签流程、退票流程等多条业务路径同时高负载期间
- **持续时间**: 120s
- **选择理由**: 选择CPU压力而非Pod Kill是因为：1）能触发ORD-FM6多路径峰值叠加模式，模拟真实的多业务并发场景；2）CPU饱和会导致响应变慢，触发上游重试风暴；3）持续时间足够长以观察完整的级联传播过程

**预测级联路径**:

  **Step 1**: ts-order-other-service因CPU饱和导致响应时间急剧上升，从正常50ms增加到5-10秒
  - 机制: 基于ORD-FM6多路径峰值叠加：CPU压力模拟7条业务路径（购票流程（其他）、改签流程、退票流程、支付流程、行程查询（其他）、执行/检票流程、管理后台-订单管理）的并发高负载
  - 受影响服务: ts-order-other-service
  - 证据: 路径交叉度=7，同节点共置业务服务包括ts-cancel-service等，CPU limit=1500m但request仅100m，QoS=Burstable易受资源争抢影响

  **Step 2**: ts-cancel-service因调用ts-order-other-service超时（无超时配置导致长时间阻塞）且受同节点资源争抢影响，自身也开始响应变慢
  - 机制: 基于CAN-FM4双通道耦合：调用链阻塞+物理层传播双重影响。ts-cancel-service→ts-order-other-service无超时保护，同时两服务共置在tcse-v100-03节点
  - 受影响服务: ts-cancel-service
  - 证据: 出边ts-cancel-service→ts-order-other-service无超时配置，同节点共置，amplification_factor=2

  **Step 3**: ts-order-service因ts-cancel-service调用变慢触发汇聚放大效应，8个上游服务（包括ts-rebook-service等）同时重试，流量激增68.6倍
  - 机制: 基于ORD-FM4汇聚放大：ts-order-service的高扇入度(in_degree=8)和有缺陷的重试配置导致多个上游同时重试
  - 受影响服务: ts-order-service
  - 证据: in_degree=8，有风险入边7条(flawed_retry=2包括ts-rebook-service和ts-preserve-service，none=5)，amplification_factor=68.6

  **Step 4**: ts-seat-service因ts-order-service完全不可用且无法恢复，重试流量持续涌入，自身也进入不可用状态
  - 机制: 基于传播路径step 3机制：服务完全不可用且无法恢复，重试流量持续涌入。ts-seat-service作为ts-order-service的上游调用方受到直接冲击
  - 受影响服务: ts-seat-service
  - 证据: ts-seat-service→ts-order-service调用链，无容错保护，单副本配置使其容易受到下游故障影响

- **影响范围**: 购票流程（其他）, 改签流程, 退票流程, 支付流程, 行程查询（其他）, 执行/检票流程, 管理后台-订单管理, 购票流程, 行程查询, 路线规划
- **严重程度**: 严重
- **风险评分**: 92/100
- **核心洞察**: 该场景揭示了拓扑-资源-容错三维耦合问题：多条业务路径在同一节点的资源争抢（拓扑-资源耦合），无超时保护导致故障在调用链中无限传播（容错缺陷），以及高扇入度服务的汇聚放大效应（拓扑-容错耦合）。累积放大系数达70000，表明系统存在严重的韧性设计缺陷。

**修复分析**：如果修复某个风险会怎样？

- 若为 ts-order-other-service 添加存活探针 → 进程假死可被自动检测并重启，阻断级联传播起点
- 若为 ts-order-other-service 增加副本数到2+ → 单实例故障不会导致服务完全不可用

### 场景 SCN-003: ts-order-service重试风暴引发的跨节点级联故障

- **注入目标**: ts-order-service
- **注入方式**: pod-kill
- **注入参数**: {"signal": "SIGKILL", "grace_period": "0s"}
- **触发条件**: 高负载期间
- **持续时间**: 持续性故障（直到手动干预）
- **选择理由**: 选择pod-kill是因为ts-order-service具有'重试风暴阻止恢复'故障模式(ORD-FM2)：单副本+无liveness探针+多条重试边，pod被kill后无法自动恢复，重试流量持续涌入形成自我恶化循环

**预测级联路径**:

  **Step 1**: ts-order-service Pod被强制终止，由于无liveness探针，K8s不会自动重启，服务进入完全不可用状态
  - 机制: 基于故障模式ORD-FM2：单副本(replicas=1)+无liveness探针+重试边ts-rebook-service和ts-preserve-service
  - 受影响服务: ts-order-service
  - 证据: K8s配置：replicas=1, liveness_probe=false，重试边amplification_factor=10

  **Step 2**: ts-cancel-service调用ts-order-service失败，由于无容错保护，直接向上游传播失败
  - 机制: 基于传播链步骤1：调用边ts-cancel-service→ts-order-service无任何容错保护(protection_level=none, beta=10)
  - 受影响服务: ts-cancel-service
  - 证据: 调用边配置：retry=false, circuit_breaker=false, timeout=false，来源ts-cancel-service/CancelServiceImpl.java:335

  **Step 3**: ts-cancel-service进一步调用ts-order-other-service，由于同样无容错保护，故障继续传播
  - 机制: 基于传播链步骤2：调用边ts-cancel-service→ts-order-other-service无容错保护(protection_level=none, beta=10)
  - 受影响服务: ts-order-other-service
  - 证据: 调用边配置：所有容错机制均为false，来源ts-cancel-service/CancelServiceImpl.java:349

  **Step 4**: ts-order-other-service受到冲击后，其高扇入度(in_degree=8)特征被激活，8个上游服务同时重试，形成汇聚放大效应
  - 机制: 基于故障模式ORD-FM4：高扇入度+多条有风险入边，amplification_factor=75.0
  - 受影响服务: ts-order-other-service及其8个上游
  - 证据: 拓扑配置：in_degree=8, 有风险入边8条(flawed_retry=1, none=7)

  **Step 5**: ts-inside-payment-service通过调用ts-order-other-service受到影响，超时在支付流程链上逐级放大
  - 机制: 基于传播链步骤3和故障模式INS-FM3：深调用链+超时配置不一致，amplification_factor=8
  - 受影响服务: ts-inside-payment-service
  - 证据: 拓扑风险：深调用链(路径'支付流程'深度=8)，链上超时配置不一致

  **Step 6**: 由于ts-order-service、ts-order-other-service、ts-cancel-service都部署在同一节点tcse-v100-03上，节点资源争抢加剧故障影响
  - 机制: 基于资源配置：三个核心服务共置在同一节点，QoS均为Burstable，资源竞争激化
  - 受影响服务: tcse-v100-03节点上所有服务
  - 证据: 资源配置：node=tcse-v100-03, qos_class=Burstable，共置15个服务包括核心业务服务

- **影响范围**: 购票流程, 退票流程, 改签流程, 支付流程, 购票流程（其他）, 行程查询, 执行/检票流程, 管理后台-订单管理
- **严重程度**: 严重
- **风险评分**: 95/100
- **核心洞察**: 这个场景揭示了配置-容错-拓扑-资源四个维度的深度耦合问题：单副本配置缺陷与重试机制设计不当相结合，在高扇入拓扑结构中被放大，最终通过物理节点共置形成跨层级的系统性风险，展现了微服务系统中看似独立的设计决策如何相互作用产生意外的级联效应

**修复分析**：如果修复某个风险会怎样？

- 若为 ts-order-service 添加存活探针 → 进程假死可被自动检测并重启，阻断级联传播起点
- 若为 ts-order-service 增加副本数到2+ → 单实例故障不会导致服务完全不可用
- 若上游添加熔断器 → 快速失败而非持续重试，防止重试风暴

### 场景 SCN-004: ts-order-other-service重试风暴引发连锁崩溃

- **注入目标**: ts-order-other-service
- **注入方式**: pod-kill
- **注入参数**: {"kill_signal": "SIGKILL", "force": true}
- **触发条件**: 退票流程高负载期间
- **持续时间**: 持续注入，每10秒kill一次Pod
- **选择理由**: ts-order-other-service具有ORD-FM2故障模式（重试风暴阻止恢复），单副本+无存活探针+上游重试无熔断的组合，pod-kill可完美复现容器崩溃后的重试风暴自我恶化循环

**预测级联路径**:

  **Step 1**: ts-order-other-service Pod被kill后，由于无存活探针，K8s无法及时检测到进程异常，服务处于假死状态
  - 机制: 基于ORD-FM2故障模式：单副本(replicas=1)+无存活探针(livenessProbe=false)+重试无熔断
  - 受影响服务: ts-order-other-service
  - 证据: replicas=1, liveness_probe=false, 入边ts-rebook-service重试配置retry=5/backoff=none/no CB

  **Step 2**: ts-cancel-service调用ts-order-other-service失败，由于无超时和熔断保护，开始持续重试，重试流量放大10倍
  - 机制: 基于边保护配置：ts-cancel-service→ts-order-other-service无任何容错保护(beta=10)
  - 受影响服务: ts-cancel-service
  - 证据: 调用边protection_level=none, beta=10, 无retry/circuit_breaker/timeout/bulkhead/fallback

  **Step 3**: ts-cancel-service被阻塞在对ts-order-other-service的调用上，自身开始响应变慢，同时由于同节点部署，开始争抢CPU/内存资源
  - 机制: 基于CAN-FM4双通道耦合故障模式：调用链阻塞+同节点资源争抢双重影响
  - 受影响服务: ts-cancel-service
  - 证据: 两服务同节点tcse-v100-03共置，QoS=Burstable，CPU limit=1500m但request只有100m

  **Step 4**: ts-order-service收到来自ts-cancel-service的慢请求/错误，由于无容错保护开始重试，同时ts-seat-service也向ts-order-service发送重试请求
  - 机制: 基于ORD-FM4汇聚放大故障模式：多个上游(8个)同时重试，流量放大68.6倍
  - 受影响服务: ts-order-service
  - 证据: in_degree=8, 有风险入边7条(flawed_retry=2, none=5), amplification_factor=68.6

  **Step 5**: ts-seat-service在调用ts-order-service失败后，由于高扇入度(6个上游)，触发汇聚放大效应，多个上游同时重试造成流量激增47.7倍
  - 机制: 基于SEA-FM5汇聚放大故障模式：高扇入度+多重试路径叠加
  - 受影响服务: ts-seat-service
  - 证据: in_degree=6, 有风险入边4条(flawed_retry=1, none=3), amplification_factor=47.7

  **Step 6**: 整个节点tcse-v100-03由于4个服务(ts-order-other-service/ts-cancel-service/ts-order-service/ts-seat-service)同时高负载，CPU/内存资源耗尽，引发节点级故障
  - 机制: 基于多路径峰值叠加故障模式：多个业务路径流量在同节点叠加造成资源饱和
  - 受影响服务: 节点tcse-v100-03上所有16个服务
  - 证据: 4个核心服务同节点共置，累计amplification_factor达50000，所有服务QoS=Burstable面临驱逐风险

- **影响范围**: 退票流程, 购票流程, 购票流程（其他）, 改签流程, 行程查询, 行程查询（其他）, 路线规划
- **严重程度**: 严重
- **风险评分**: 95/100
- **核心洞察**: 这个场景揭示了配置脆弱性、容错缺失、拓扑放大和资源共置四个维度的深度耦合问题：单点故障通过重试风暴自我恶化，然后经由无保护的调用链快速传播，在高扇入节点形成流量放大，最终导致物理资源层面的节点级崩溃，体现了微服务系统中'故障放大-传播-聚合-溢出'的完整链条

**修复分析**：如果修复某个风险会怎样？

- 若为 ts-order-other-service 添加存活探针 → 进程假死可被自动检测并重启，阻断级联传播起点
- 若为 ts-order-other-service 增加副本数到2+ → 单实例故障不会导致服务完全不可用
- 若上游添加熔断器 → 快速失败而非持续重试，防止重试风暴

### 场景 SCN-005: ts-user-service超时传播引发退票流程全链路故障

- **注入目标**: ts-user-service
- **注入方式**: network-delay
- **注入参数**: {"delay": "3000ms", "variance": "500ms", "correlation": "25%"}
- **触发条件**: 退票业务高峰期
- **持续时间**: 300s
- **选择理由**: 选择网络延迟而非直接pod-kill是因为USE-FM3故障模式特征是'不可预测的超时传播'，需要模拟链末端服务响应变慢的真实场景。持续300秒能充分观察超时在深调用链上的逐级放大效应和累积放大系数达到50000的过程

**预测级联路径**:

  **Step 1**: ts-user-service响应时间从正常100ms增加到3-3.5秒，触发USE-FM3不可预测的超时传播模式
  - 机制: 基于USE-FM3故障模式：深调用链(路径'退票流程'深度=5) + 链上超时配置不一致
  - 受影响服务: ts-user-service
  - 证据: single replica=1, no livenessProbe=false, 深调用链路径'退票流程'深度=5

  **Step 2**: ts-cancel-service调用ts-user-service超时，由于无任何容错保护(timeout/retry/CB全部absent)，请求直接失败并向上游传播
  - 机制: 基于调用边ts-cancel-service→ts-user-service无保护(protection_level=none, beta=10)和CAN-FM3超时传播模式
  - 受影响服务: ts-cancel-service
  - 证据: 调用边无timeout/retry/circuit_breaker保护，CAN-FM3放大系数=5

  **Step 3**: ts-cancel-service向ts-order-service传播故障，ts-order-service触发ORD-FM2重试风暴阻止恢复模式，8个上游服务开始疯狂重试
  - 机制: 基于ORD-FM2重试风暴模式：单副本+入边retry=5/backoff=none/no CB，高扇入度in_degree=8放大重试流量
  - 受影响服务: ts-order-service
  - 证据: single replica=1, 入边ts-rebook-service/ts-preserve-service retry=5无退避，in_degree=8，ORD-FM2放大系数=10

  **Step 4**: ts-order-service完全不可用且无法恢复，向ts-seat-service传播故障，ts-seat-service因SEA-FM2重试风暴同样无法恢复，6个上游同时受影响
  - 机制: 基于SEA-FM2重试风暴模式和SEA-FM5汇聚放大：单副本+重试流量+高扇入度in_degree=6
  - 受影响服务: ts-seat-service
  - 证据: single replica=1, 入边ts-preserve-service retry=3/backoff=fixed 500ms/no CB，in_degree=6，SEA-FM5放大系数=47.7

  **Step 5**: 整个退票流程完全瘫痪，同时由于所有服务都在同一节点tcse-v100-03上，触发节点级资源饱和，影响同节点的15个其他服务
  - 机制: 基于多路径峰值叠加模式和同节点共置风险：ts-cancel-service, ts-order-service, ts-seat-service都在tcse-v100-03节点
  - 受影响服务: 整个节点tcse-v100-03
  - 证据: 同节点共置15个服务，QoS=Burstable易被驱逐，cumulative_amplification=50000

- **影响范围**: 退票流程, 购票流程, 改签流程, 支付流程, 行程查询
- **严重程度**: 严重
- **风险评分**: 95/100
- **核心洞察**: 这个场景揭示了超时传播在深调用链中与重试风暴、节点共置的三重耦合问题：1)超时配置不一致导致故障在链上不可预测传播，2)单副本+无容错保护使重试风暴阻止服务恢复，3)关键服务全部共置在同一节点放大了故障影响范围，最终一个3秒的网络延迟演变成整个节点的服务群体性故障

**修复分析**：如果修复某个风险会怎样？

- 若为 ts-user-service 添加存活探针 → 进程假死可被自动检测并重启，阻断级联传播起点
- 若为 ts-user-service 增加副本数到2+ → 单实例故障不会导致服务完全不可用

### 场景 SCN-006: 车站服务单点僵死引发重试风暴自循环

- **注入目标**: ts-station-service
- **注入方式**: memory-stress
- **注入参数**: {"workers": 2, "memory_size": "1200Mi", "duration": "120s"}
- **触发条件**: 高负载期间
- **持续时间**: 120s
- **选择理由**: 内存压力导致进程假死但Pod状态仍为Running，结合无存活探针配置，K8s无法检测并重启，形成僵死状态。选择内存压力而非CPU压力是因为内存泄漏更容易导致进程假死而非完全崩溃

**预测级联路径**:

  **Step 1**: ts-station-service进程因内存压力陷入假死状态，不响应请求但Pod状态为Running
  - 机制: 基于故障模式STA-FM1：僵死永久不可用
  - 受影响服务: ts-station-service
  - 证据: 单副本(replicas=1) + 无存活探针(livenessProbe=false)，K8s无法检测进程假死

  **Step 2**: 8个上游服务(包括ts-order-other-service)向ts-station-service发起调用全部超时
  - 机制: 基于拓扑数据：高扇入度(in_degree=8)
  - 受影响服务: ts-order-other-service等8个上游服务
  - 证据: upstream_callers包含ts-order-other-service, ts-order-service, ts-preserve-service等8个服务

  **Step 3**: ts-order-other-service等上游服务开始重试，向已僵死的ts-station-service发送更多请求
  - 机制: 传播链中的重试风暴机制
  - 受影响服务: ts-order-other-service
  - 证据: 传播链显示caller_mode为'重试风暴阻止恢复'，放大系数50倍

  **Step 4**: 重试请求堆积在ts-station-service的连接队列中，消耗更多内存资源
  - 机制: 自循环加重：重试流量 → 资源压力加重 → 恢复更困难
  - 受影响服务: ts-station-service
  - 证据: 累积放大系数50倍，重试流量使原本就内存压力的服务雪上加霜

  **Step 5**: 同节点其他服务受到内存和连接数的间接影响，性能下降
  - 机制: 基于资源共享风险
  - 受影响服务: tcse-v100-03节点上的15个共置服务
  - 证据: co_located_services包含ts-order-other-service等15个服务，Burstable QoS类别在节点资源紧张时相互影响

  **Step 6**: 7条核心业务路径全部受阻，包括购票流程、改签流程等
  - 机制: 基于业务路径依赖
  - 受影响服务: 涉及车站查询的所有业务服务
  - 证据: business_paths包含'购票流程'、'购票流程（其他）'、'改签流程'等7条路径

- **影响范围**: 购票流程, 购票流程（其他）, 改签流程, 行程查询, 行程查询（其他）, 路线规划, 管理后台-基础信息
- **严重程度**: 严重
- **风险评分**: 95/100
- **核心洞察**: 此场景揭示了配置维度(单副本+无存活探针)与拓扑维度(高扇入+重试链路)的致命耦合：配置缺陷导致故障无法自愈，而拓扑特征使重试流量形成正反馈循环，阻止服务恢复，最终演变成永久性系统瘫痪

**修复分析**：如果修复某个风险会怎样？

- 若为 ts-station-service 添加存活探针 → 进程假死可被自动检测并重启，阻断级联传播起点
- 若为 ts-station-service 增加副本数到2+ → 单实例故障不会导致服务完全不可用

### 场景 SCN-007: 车站服务僵死引发的重试风暴自循环放大

- **注入目标**: ts-station-service
- **注入方式**: memory-stress
- **注入参数**: {"workers": 2, "percent": 90, "timeout": "600s"}
- **触发条件**: 高负载期间
- **持续时间**: 600s
- **选择理由**: 通过内存压力模拟内存泄漏导致的进程假死状态，由于无存活探针，K8s不会重启容器，形成僵死状态。选择高负载期间注入，可最大化重试风暴效应

**预测级联路径**:

  **Step 1**: ts-station-service进程因内存压力陷入假死状态，停止响应请求但Pod状态仍为Running
  - 机制: 基于故障模式STA-FM1：僵死永久不可用
  - 受影响服务: ts-station-service
  - 证据: 单副本(replicas=1) + 无存活探针(livenessProbe=false)，K8s无法检测到进程假死并重启

  **Step 2**: ts-order-service调用ts-station-service时遇到超时，开始重试机制
  - 机制: 基于传播链描述：ts-order-service重试
  - 受影响服务: ts-order-service
  - 证据: ts-order-service在上游调用者列表中，无有效的熔断机制防止重试风暴

  **Step 3**: 重试请求进一步加重ts-station-service负载，阻止其从假死状态恢复
  - 机制: 基于传播链放大效应：重试风暴阻止恢复
  - 受影响服务: ts-station-service
  - 证据: 累积放大因子=12.0，重试流量是原始流量的12倍

  **Step 4**: 其他7个上游服务(ts-admin-basic-info-service等)也开始重试，进一步放大流量
  - 机制: 基于故障模式STA-FM3：汇聚放大
  - 受影响服务: 多个上游服务
  - 证据: 高扇入度(in_degree=8) + 有风险入边7条，放大因子80.0

  **Step 5**: 节点tcse-v100-03资源饱和，影响同节点的14个其他服务
  - 机制: 基于故障模式STA-FM5：多路径峰值叠加
  - 受影响服务: 同节点14个服务
  - 证据: QoS=Burstable + 同节点共置服务包括ts-order-service等关键服务

  **Step 6**: 7条业务路径完全不可用，包括核心的购票和改签流程
  - 机制: 基于故障模式STA-FM4：不可预测的超时传播
  - 受影响服务: 整个业务系统
  - 证据: 业务路径包括购票流程、改签流程等7条关键路径，调用链深度=7

- **影响范围**: 购票流程, 购票流程（其他）, 改签流程, 行程查询, 行程查询（其他）, 路线规划, 管理后台-基础信息
- **严重程度**: 严重
- **风险评分**: 95/100
- **核心洞察**: 这个场景揭示了配置维度(单副本+无探针)与拓扑维度(高扇入+深链路)的耦合风险：微小的配置缺陷在特定拓扑结构下会引发自强化的级联故障循环，传统的重试机制反而成为故障放大器，最终导致整个系统雪崩

**修复分析**：如果修复某个风险会怎样？

- 若为 ts-station-service 添加存活探针 → 进程假死可被自动检测并重启，阻断级联传播起点
- 若为 ts-station-service 增加副本数到2+ → 单实例故障不会导致服务完全不可用

### 场景 SCN-008: 自循环重试风暴场景：订单服务僵死引发座位服务重试死循环

- **注入目标**: ts-order-other-service
- **注入方式**: process-hang
- **注入参数**: {"target_process": "java", "hang_duration": "300s", "hang_method": "cpu_infinite_loop"}
- **触发条件**: 座位分配高峰期间
- **持续时间**: 300s
- **选择理由**: 选择进程挂起而非pod-kill，因为单副本+无liveness探针的配置会让Pod状态保持Running但进程不响应，完美触发僵死永久不可用故障模式，同时引发ts-seat-service的重试风暴

**预测级联路径**:

  **Step 1**: ts-order-other-service进程进入死锁状态，无法处理任何请求
  - 机制: 基于故障模式ORD-FM1：僵死永久不可用
  - 受影响服务: ts-order-other-service
  - 证据: replicas=1且liveness_probe=false，K8s无法检测进程假死并重启

  **Step 2**: ts-seat-service调用ts-order-other-service时收到超时，开始重试
  - 机制: 基于传播链loop_info，ts-seat-service作为调用方会重试
  - 受影响服务: ts-seat-service
  - 证据: 传播链显示ts-seat-service → ts-order-other-service的调用关系

  **Step 3**: 重试流量持续涌入已僵死的ts-order-other-service，阻止其恢复
  - 机制: 基于故障模式ORD-FM2：重试风暴阻止恢复
  - 受影响服务: ts-order-other-service
  - 证据: amplification_factor=5的重试配置，重试流量持续涌入单副本服务

  **Step 4**: 形成自循环：僵死服务 → 重试请求 → 加重负载 → 阻止恢复 → 继续僵死
  - 机制: 基于传播链cumulative_amplification=18.0的放大效应
  - 受影响服务: ts-order-other-service和ts-seat-service
  - 证据: self_loop类型传播链，caller_mode=重试风暴阻止恢复，callee_mode=僵死永久不可用

  **Step 5**: ts-seat-service资源耗尽，开始影响其他调用方
  - 机制: 基于故障模式ORD-FM4：汇聚放大
  - 受影响服务: ts-seat-service的上游服务
  - 证据: ts-order-other-service的in_degree=8，多个上游会同时受影响

  **Step 6**: 节点tcse-v100-03上的15个共置服务开始出现资源争抢
  - 机制: 基于故障模式ORD-FM6：多路径峰值叠加
  - 受影响服务: tcse-v100-03节点上所有15个服务
  - 证据: co_located_services包含15个业务服务，QoS=Burstable存在驱逐风险

- **影响范围**: 购票流程（其他）, 改签流程, 退票流程, 支付流程, 行程查询（其他）, 执行/检票流程, 管理后台-订单管理
- **严重程度**: 严重
- **风险评分**: 95/100
- **核心洞察**: 这个场景揭示了配置缺陷与容错机制的恶性耦合：单副本+无liveness探针的配置缺陷，结合不当的重试机制，形成了自我强化的故障循环。18倍的放大效应表明，看似局部的配置问题可以通过调用关系形成系统性的韧性黑洞，这种自循环故障特别危险，因为它具有自我维持特性，即使外部压力消失也难以自动恢复。

**修复分析**：如果修复某个风险会怎样？

- 若为 ts-order-other-service 添加存活探针 → 进程假死可被自动检测并重启，阻断级联传播起点
- 若为 ts-order-other-service 增加副本数到2+ → 单实例故障不会导致服务完全不可用

### 场景 SCN-009: N/A

- **注入目标**: N/A
- **注入方式**: N/A
- **注入参数**: {}
- **触发条件**: N/A
- **持续时间**: N/A
- **选择理由**: N/A

- **影响范围**: N/A
- **严重程度**: N/A
- **风险评分**: N/A/100
- **核心洞察**: N/A

**修复分析**：如果修复某个风险会怎样？


### 场景 SCN-010: N/A

- **注入目标**: N/A
- **注入方式**: N/A
- **注入参数**: {}
- **触发条件**: N/A
- **持续时间**: N/A
- **选择理由**: N/A

- **影响范围**: N/A
- **严重程度**: N/A
- **风险评分**: N/A/100
- **核心洞察**: N/A

**修复分析**：如果修复某个风险会怎样？



## 7. 覆盖率分析

| 严重程度 | 总数 | 已覆盖 | 覆盖率 |
|----------|------|--------|--------|
| 严重 | 32 | 13 | 41% |
| 高 | 46 | 17 | 37% |
| 合计 | 78 | 30 | 38% |

### 未覆盖的故障模式

- ts-auth-service: 僵死永久不可用 (AUT-FM1)
- ts-verification-code-service: 僵死永久不可用 (VER-FM1)
- ts-preserve-service: 僵死永久不可用 (PRE-FM1)
- ts-preserve-service: 不可预测的超时传播 (PRE-FM3)
- ts-preserve-service: 双通道耦合 (PRE-FM4)
- ts-wait-order-service: 僵死永久不可用 (WAI-FM1)
- ts-wait-order-service: 双通道耦合 (WAI-FM3)
- ts-preserve-other-service: 僵死永久不可用 (PRE-FM1)
- ts-preserve-other-service: 不可预测的超时传播 (PRE-FM3)
- ts-preserve-other-service: 双通道耦合 (PRE-FM4)
- ts-admin-user-service: 僵死永久不可用 (ADM-FM1)
- ts-consign-service: 僵死永久不可用 (CON-FM1)
- ts-consign-service: 双通道耦合 (CON-FM3)
- ts-basic-service: 僵死永久不可用 (BAS-FM1)
- ts-basic-service: 功能完全不可用 (BAS-FM3)
- ts-basic-service: 双通道耦合 (BAS-FM4)
- ts-food-service: 僵死永久不可用 (FOO-FM1)
- ts-security-service: 僵死永久不可用 (SEC-FM1)
- ts-security-service: 不可预测的超时传播 (SEC-FM3)
- ts-security-service: 多路径峰值叠加 (SEC-FM4)
- ts-security-service: 双通道耦合 (SEC-FM5)
- ts-travel-service: 僵死永久不可用 (TRA-FM1)
- ts-travel-service: 汇聚放大 (TRA-FM3)
- ts-travel-service: 不可预测的超时传播 (TRA-FM4)
- ts-travel-service: 功能完全不可用 (TRA-FM5)
- ts-travel-service: 多路径峰值叠加 (TRA-FM6)
- ts-contacts-service: 僵死永久不可用 (CON-FM1)
- ts-contacts-service: 不可预测的超时传播 (CON-FM3)
- ts-contacts-service: 多路径峰值叠加 (CON-FM4)
- ts-travel2-service: 僵死永久不可用 (TRA-FM1)
- ts-travel2-service: 汇聚放大 (TRA-FM3)
- ts-travel2-service: 不可预测的超时传播 (TRA-FM4)
- ts-travel2-service: 功能完全不可用 (TRA-FM5)
- ts-travel2-service: 多路径峰值叠加 (TRA-FM6)
- ts-travel2-service: 双通道耦合 (TRA-FM7)
- ts-train-service: 僵死永久不可用 (TRA-FM1)
- ts-train-service: 汇聚放大 (TRA-FM3)
- ts-train-service: 不可预测的超时传播 (TRA-FM4)
- ts-train-service: 功能完全不可用 (TRA-FM5)
- ts-train-service: 多路径峰值叠加 (TRA-FM6)
- ts-route-service: 僵死永久不可用 (ROU-FM1)
- ts-route-service: 汇聚放大 (ROU-FM3)
- ts-route-service: 不可预测的超时传播 (ROU-FM4)
- ts-route-service: 功能完全不可用 (ROU-FM5)
- ts-route-service: 多路径峰值叠加 (ROU-FM6)
- ts-price-service: 僵死永久不可用 (PRI-FM1)
- ts-price-service: 不可预测的超时传播 (PRI-FM3)
- ts-price-service: 多路径峰值叠加 (PRI-FM4)

**未覆盖原因分析**：这些服务（如 ts-auth-service、ts-verification-code-service）在调用图中处于边缘位置，传播链较短，不容易被多跳传播链覆盖。但它们的「僵死永久不可用」风险仍需关注，建议单独进行 pod-kill 测试。


## 8. 发现与建议

### 最危险的跨维度耦合模式

1. **配置×容错：重试风暴阻止恢复**
   - 全系统单副本 + 无存活探针 + 有缺陷的重试配置（无熔断器）
   - ts-preserve-service → ts-order-service 的调用边配置了 5 次重试、0ms 退避、无熔断器
   - 一旦 ts-order-service 崩溃，5 倍流量冲击会阻止其恢复

2. **拓扑×配置：汇聚放大效应**
   - ts-station-service（扇入度 8）和 ts-order-service（扇入度 8）是核心汇聚点
   - 多个上游无保护调用，故障时所有上游同时阻塞等待，放大系数极高

3. **容错×资源：双通道耦合**
   - 同节点共置服务间既有调用关系又共享物理资源
   - 调用链阻塞（无超时）+ 物理层资源争抢形成双重故障通道

4. **全维度：系统性单点故障**
   - 100% 单副本 + 100% 无存活探针 = 任何服务假死都是永久故障
   - 这是所有其他风险的放大器：将任何瞬时故障变成持久故障

### 优先修复建议（收益排序）

| 优先级 | 修复项 | 受益服务数 | 预期收益 | 实施难度 |
|--------|--------|-----------|----------|----------|
| P0 | 为所有服务添加存活探针 | 47 | 消除「僵死永久不可用」风险，使K8s能自动恢复假死服务 | 低 |
| P0 | 为关键服务增加副本数≥2 | ~15 | 消除单点故障，特别是 ts-order-service, ts-station-service 等高扇入服务 | 中 |
| P1 | 为 ts-preserve→ts-order 等有缺陷重试添加熔断器 | 4 | 阻断重试风暴传播链，β 从 5 降至 ≈0 | 低 |
| P1 | 为所有无超时调用边添加超时配置 | ~70 | 防止线程无限阻塞等待，限制故障传播时间 | 低 |
| P2 | 为关键服务设置资源限制 | ~15 | 防止噪声邻居效应和 OOM 影响同节点服务 | 低 |
| P2 | 为高扇入服务配置 Pod 反亲和性 | ~5 | 避免关键服务的多副本调度到同一节点 | 低 |
| P3 | 修复 ts-order-service 的熔断器阈值（90%→50%） | 1 | 使熔断器能在故障早期触发，而非几乎永不触发 | 低 |

### 推荐的混沌工程实验优先级排序

| 优先级 | 实验 | 对应场景 | 预期验证点 |
|--------|------|---------|-----------|
| 1 | 基于不可预测超时传播的级联故障场景 | SCN-001 | 这个场景揭示了微服务架构中的三重耦合陷阱：1)调用链维度-深度调用链缺乏超时配置导致故障逐级放大；2 |
| 2 | 多路径峰值叠加引发的级联故障 | SCN-002 | 该场景揭示了拓扑-资源-容错三维耦合问题：多条业务路径在同一节点的资源争抢（拓扑-资源耦合），无超时 |
| 3 | ts-order-service重试风暴引发的跨节点级联故障 | SCN-003 | 这个场景揭示了配置-容错-拓扑-资源四个维度的深度耦合问题：单副本配置缺陷与重试机制设计不当相结合， |
| 4 | ts-order-other-service重试风暴引发连锁崩溃 | SCN-004 | 这个场景揭示了配置脆弱性、容错缺失、拓扑放大和资源共置四个维度的深度耦合问题：单点故障通过重试风暴自 |
| 5 | ts-user-service超时传播引发退票流程全链路故障 | SCN-005 | 这个场景揭示了超时传播在深调用链中与重试风暴、节点共置的三重耦合问题：1)超时配置不一致导致故障在链 |
| 6 | 车站服务单点僵死引发重试风暴自循环 | SCN-006 | 此场景揭示了配置维度(单副本+无存活探针)与拓扑维度(高扇入+重试链路)的致命耦合：配置缺陷导致故障 |
| 7 | 车站服务僵死引发的重试风暴自循环放大 | SCN-007 | 这个场景揭示了配置维度(单副本+无探针)与拓扑维度(高扇入+深链路)的耦合风险：微小的配置缺陷在特定 |
| 8 | 自循环重试风暴场景：订单服务僵死引发座位服务重试死循环 | SCN-008 | 这个场景揭示了配置缺陷与容错机制的恶性耦合：单副本+无liveness探针的配置缺陷，结合不当的重试 |

---

*本报告由 CrossFault 分析框架自动生成，基于源码静态分析、K8s 集群实时状态和 Claude AI 推理。*
*所有结论均引用具体的配置值和拓扑数据，可直接追溯验证。*
