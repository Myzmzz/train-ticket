# Train-Ticket 微服务系统完整部署实践与问题分析

## 一、部署背景与目标

本周的主要工作是完成 Train-Ticket 微服务系统的**完整版部署**。与简单版本不同，完整版保留了 Nacos（服务注册与发现）、RabbitMQ（消息队列）、RadonDB MySQL（高可用数据库集群）等中间件组件，目的是尽可能还原一个贴近真实生产环境的微服务架构。

之所以选择完整版部署，核心考虑在于：**简化后的环境会掩盖大量真实场景中的故障模式**。只有当服务注册、消息异步通信、数据库高可用选举等机制真正运转起来，才可能暴露出那些更经典、更具代表性的故障——而这些恰恰是我们研究微服务韧性所关注的。

## 二、部署过程中遇到的问题

在完整部署过程中，先后遇到了以下四个典型问题：

### 1. MySQL Xenon Leader 选举 IPv6 问题

RadonDB MySQL 采用 Xenon 组件实现高可用 Leader 选举。部署后发现 follower 节点持续报 `PostStartHookError`，集群无法正常完成选主。排查后发现，Xenon 内部的 Go MySQL 驱动默认通过 IPv6 回环地址（`::1`）连接本地 MySQL 实例，但 Percona 5.7 默认只创建了 IPv4 的 root 用户，导致 Xenon 的健康检查始终失败。

这是一个**基础设施组件自身的缺陷**——RadonDB Helm Chart 并未在初始化流程中处理 IPv6 用户创建，需要在每个 MySQL 节点手动执行 `CREATE USER 'root'@'::1'` 才能解决。

### 2. Resilience4j 依赖版本冲突

ts-preserve-service 等引入了 Resilience4j 熔断器的服务在启动时抛出 `NoSuchMethodError: SpelResolverConfiguration.spelResolver()`。根因在于 `resilience4j-spring-boot2:1.7.1` 的传递依赖会拉入 `resilience4j-spring:1.7.0`，而 1.7.0 与 1.7.1 之间存在方法签名变更，导致运行时方法找不到。

这是一个典型的 **Maven 传递依赖版本漂移问题**——即使应用代码本身没有问题，依赖树中的版本不一致也会在运行时引发不可预期的异常。最终通过在父 POM 的 `<dependencyManagement>` 中显式固定 `resilience4j-spring:1.7.1` 来解决。

### 3. K8s 镜像缓存导致更新无效

修复上述依赖冲突后重新构建并推送了 Docker 镜像，但重新部署后问题依旧。排查发现 K8s 节点上仍然运行的是旧镜像——因为 Deployment 中配置了 `imagePullPolicy: IfNotPresent`，而新镜像使用了相同的 tag，节点本地已缓存旧版本，不会重新拉取。

这是 K8s 环境下一个**容易被忽视的运维陷阱**：同 tag 镜像更新在 `IfNotPresent` 策略下不会生效。解决方式是更换镜像 tag（如 `1.0.0` 改为 `1.0.0-fix2`），或临时将 `imagePullPolicy` 设为 `Always`。

### 4. Helm Chart 跨命名空间 DNS 解析失败

在第二套测试环境部署时，Nacos 无法连接其后端 MySQL。原因是 Helm Chart 模板中使用了短域名（如 `nacosdb-mysql-leader`），该域名仅在同一 namespace 内可解析。当基础设施和应用部署在不同 namespace 时，短域名解析失败。

这是 **Kubernetes DNS 作用域机制**带来的问题——需要将服务地址改为 FQDN 格式（如 `nacosdb-mysql-leader.train-ticket.svc.cluster.local`）才能跨命名空间访问。

## 三、产出

经过对上述问题的逐一排查与解决，本周形成了两方面的产出：

### 产出一：自动化 Train-Ticket 部署工作流

将整个部署流程沉淀为一套可复用的自动化部署方案，涵盖：
- 基础设施层（MySQL HA 集群、Nacos、RabbitMQ）的 Helm 编排与顺序控制
- MySQL IPv6 用户创建等已知问题的自动修复步骤
- Secret 生成、Service/Deployment 资源的批量应用
- 部署后健康检查与就绪等待机制
- 完整清理与重建流程

该工作流将后续部署的人工操作降到最低，也避免了因遗漏某个修复步骤而反复踩坑。

### 产出二：关于基础设施固有缺陷与韧性风险的思考

在解决这些部署问题的过程中，一个明显的体会是：**许多故障并非源于应用代码本身，而是来自关键基础设施组件的固有缺陷**。

MySQL 的 Xenon 选举组件未处理 IPv6 兼容性、Resilience4j 的传递依赖存在版本断裂、Helm Chart 模板未考虑跨命名空间场景——这些问题本质上都属于组件供应商层面的不完善，并且往往不在其修复优先级之内。然而，这些看似微小的底层缺陷，在微服务架构中会被层层放大：一个数据库选举的短暂中断，可能引发上游服务的连接超时；一个依赖版本的不一致，可能导致熔断器本身失效；一次 DNS 解析失败，可能触发整条调用链的级联故障。

这恰恰说明了**微服务韧性研究的现实意义**：在真实环境中，风险往往不是来自某个预设的故障注入场景，而是来自基础设施层那些难以预见、连厂商都无法彻底解决的固有问题。它们会以功能异常或性能抖动的形式传导到应用层，成为系统韧性的真正威胁。
