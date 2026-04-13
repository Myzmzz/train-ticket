#!/bin/bash
#
# Train-Ticket 一键卸载 + 部署脚本
# 用法: bash hack/deploy/deploy-all.sh [namespace]
# 默认命名空间: train-ticket
# 必须在项目根目录下执行
#

set -euo pipefail

# ======================== 配置 ========================
NS="${1:-train-ticket}"

# 项目根目录（脚本所在位置向上两级）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Helm Chart 路径
MYSQL_CHART="deployment/kubernetes-manifests/quickstart-k8s/charts/mysql"
NACOS_CHART="deployment/kubernetes-manifests/quickstart-k8s/charts/nacos"
RABBITMQ_CHART="deployment/kubernetes-manifests/quickstart-k8s/charts/rabbitmq"

# YAML 路径
DEPLOY_YAML="deployment/kubernetes-manifests/quickstart-k8s/yamls/deploy-otel.yaml"
SVC_YAML="deployment/kubernetes-manifests/quickstart-k8s/yamls/svc.yaml"
SECRET_YAML="deployment/kubernetes-manifests/quickstart-k8s/yamls/secret.yaml"

# 数据库凭证
NACOS_DB_USER="nacos"
NACOS_DB_PASS="Abcd1234#"
NACOS_DB_NAME="nacos"

TS_DB_USER="ts"
TS_DB_PASS="Ts_123456"
TS_DB_NAME="ts"

# MySQL Pod 列表
MYSQL_PODS="nacosdb-mysql-0 nacosdb-mysql-1 nacosdb-mysql-2 tsdb-mysql-0 tsdb-mysql-1 tsdb-mysql-2"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "\n${GREEN}========== $* ==========${NC}"; }

# ======================== 卸载 ========================
uninstall() {
    log_step "开始卸载 (namespace: $NS)"

    # 检查命名空间是否存在
    if ! kubectl get namespace "$NS" &>/dev/null; then
        log_warn "命名空间 $NS 不存在，跳过卸载"
        return 0
    fi

    # 1. 删除微服务 Deployment
    log_info "删除微服务 Deployment..."
    kubectl delete -f "$DEPLOY_YAML" -n "$NS" --ignore-not-found --timeout=60s 2>/dev/null || true

    # 2. 删除 Secrets
    log_info "删除 Secrets..."
    kubectl delete -f "$SECRET_YAML" -n "$NS" --ignore-not-found 2>/dev/null || true

    # 3. 删除 Services
    log_info "删除 Services..."
    kubectl delete -f "$SVC_YAML" -n "$NS" --ignore-not-found 2>/dev/null || true

    # 4. 卸载 Helm releases（逆序）
    log_info "卸载 Helm releases..."
    for release in rabbitmq nacos tsdb nacosdb; do
        if helm status "$release" -n "$NS" &>/dev/null; then
            log_info "  卸载 $release..."
            helm uninstall "$release" -n "$NS" --wait --timeout=120s
        else
            log_warn "  $release 不存在，跳过"
        fi
    done

    # 5. 等待 Pod 全部终止
    log_info "等待所有 Pod 终止..."
    local timeout=120
    local elapsed=0
    while [ $elapsed -lt $timeout ]; do
        local count
        count=$(kubectl get pods -n "$NS" --no-headers 2>/dev/null | wc -l | tr -d ' ')
        if [ "$count" -eq 0 ]; then
            break
        fi
        log_info "  还有 $count 个 Pod 正在终止..."
        sleep 5
        elapsed=$((elapsed + 5))
    done

    # 6. 清理 PVC
    log_info "清理 PVC..."
    kubectl delete pvc --all -n "$NS" --timeout=60s 2>/dev/null || true

    # 7. 删除命名空间
    log_info "删除命名空间 $NS..."
    kubectl delete namespace "$NS" --timeout=120s 2>/dev/null || true

    # 等待命名空间完全删除
    local elapsed=0
    while [ $elapsed -lt 120 ]; do
        if ! kubectl get namespace "$NS" &>/dev/null; then
            break
        fi
        sleep 3
        elapsed=$((elapsed + 3))
    done

    log_ok "卸载完成"
}

# ======================== 部署 ========================
deploy() {
    log_step "开始部署 (namespace: $NS)"

    # --- 创建命名空间 ---
    log_step "第 1 步：创建命名空间"
    kubectl create namespace "$NS"
    log_ok "命名空间 $NS 已创建"

    # --- 部署 nacosdb ---
    log_step "第 2 步：部署 nacosdb（Nacos MySQL，3 副本 HA）"
    helm install nacosdb \
        --set mysql.mysqlUser="$NACOS_DB_USER" \
        --set mysql.mysqlPassword="$NACOS_DB_PASS" \
        --set mysql.mysqlDatabase="$NACOS_DB_NAME" \
        "$MYSQL_CHART" \
        -n "$NS"
    log_info "等待 nacosdb 就绪..."
    kubectl rollout status statefulset/nacosdb-mysql -n "$NS" --timeout=300s
    log_ok "nacosdb 就绪"

    # --- 部署 tsdb ---
    log_step "第 3 步：部署 tsdb（应用 MySQL，3 副本 HA）"
    helm install tsdb \
        --set mysql.mysqlUser="$TS_DB_USER" \
        --set mysql.mysqlPassword="$TS_DB_PASS" \
        --set mysql.mysqlDatabase="$TS_DB_NAME" \
        "$MYSQL_CHART" \
        -n "$NS"
    log_info "等待 tsdb 就绪..."
    kubectl rollout status statefulset/tsdb-mysql -n "$NS" --timeout=300s
    log_ok "tsdb 就绪"

    # --- 修复 MySQL IPv6 ---
    log_step "第 4 步：修复 MySQL Xenon IPv6 Leader 选举问题"
    kubectl wait --for=condition=ready pod -l app=nacosdb-mysql -n "$NS" --timeout=300s
    kubectl wait --for=condition=ready pod -l app=tsdb-mysql -n "$NS" --timeout=300s

    local fix_failed=0
    for pod in $MYSQL_PODS; do
        log_info "修复 $pod..."
        if ! kubectl exec -n "$NS" "$pod" -c mysql -- \
            mysql -uroot -e "
                CREATE USER IF NOT EXISTS 'root'@'::1' IDENTIFIED BY '';
                GRANT ALL PRIVILEGES ON *.* TO 'root'@'::1' WITH GRANT OPTION;
                FLUSH PRIVILEGES;
            " 2>/dev/null; then
            log_warn "$pod 修复失败，可能尚未完全就绪，重试..."
            sleep 5
            kubectl exec -n "$NS" "$pod" -c mysql -- \
                mysql -uroot -e "
                    CREATE USER IF NOT EXISTS 'root'@'::1' IDENTIFIED BY '';
                    GRANT ALL PRIVILEGES ON *.* TO 'root'@'::1' WITH GRANT OPTION;
                    FLUSH PRIVILEGES;
                " || { log_error "$pod IPv6 修复失败"; fix_failed=1; }
        fi
    done

    if [ $fix_failed -eq 1 ]; then
        log_error "部分 MySQL Pod IPv6 修复失败，请手动检查"
        exit 1
    fi
    log_ok "MySQL IPv6 修复完成"

    # --- 部署 Nacos ---
    log_step "第 5 步：部署 Nacos（3 副本集群）"
    helm install nacos \
        --set nacos.db.host=nacosdb-mysql-leader \
        --set nacos.db.username="$NACOS_DB_USER" \
        --set nacos.db.name="$NACOS_DB_NAME" \
        --set nacos.db.password="$NACOS_DB_PASS" \
        "$NACOS_CHART" \
        -n "$NS"
    log_info "等待 Nacos 就绪..."
    kubectl rollout status statefulset/nacos -n "$NS" --timeout=300s
    log_ok "Nacos 就绪"

    # --- 部署 RabbitMQ ---
    log_step "第 6 步：部署 RabbitMQ"
    helm install rabbitmq \
        "$RABBITMQ_CHART" \
        -n "$NS"
    log_info "等待 RabbitMQ 就绪..."
    kubectl rollout status deployment/rabbitmq -n "$NS" --timeout=120s
    log_ok "RabbitMQ 就绪"

    # --- 创建 Service ---
    log_step "第 7 步：创建 Service 资源"
    kubectl apply -f "$SVC_YAML" -n "$NS"
    log_ok "Service 资源已创建"

    # --- 生成并应用 Secrets ---
    log_step "第 8 步：生成并应用 MySQL Secrets"
    source hack/deploy/gen-mysql-secret.sh
    gen_secret_for_services "$TS_DB_USER" "$TS_DB_PASS" "$TS_DB_NAME" "tsdb-mysql-leader"
    kubectl apply -f "$SECRET_YAML" -n "$NS"
    log_ok "Secrets 已应用"

    # --- 部署微服务 ---
    log_step "第 9 步：部署 46 个微服务（含 OTel Agent）"
    kubectl apply -f "$DEPLOY_YAML" -n "$NS"
    log_ok "微服务 Deployment 已提交"

    # --- 等待就绪 ---
    log_step "第 10 步：等待所有 Pod 就绪（约 3-5 分钟）"
    log_info "Java 微服务启动较慢（Spring Boot + Hibernate + Nacos 注册），请耐心等待..."

    local timeout=600
    local elapsed=0
    local interval=10
    while [ $elapsed -lt $timeout ]; do
        local total ready not_ready
        total=$(kubectl get pods -n "$NS" --no-headers 2>/dev/null | wc -l | tr -d ' ')
        not_ready=$(kubectl get pods -n "$NS" --no-headers 2>/dev/null | grep -v -E "Running|Completed" | wc -l | tr -d ' ')
        ready=$((total - not_ready))

        if [ "$not_ready" -eq 0 ] && [ "$total" -gt 0 ]; then
            break
        fi
        log_info "  Pod 就绪: $ready / $total （还有 $not_ready 个未就绪）"
        sleep $interval
        elapsed=$((elapsed + interval))
    done

    if [ $elapsed -ge $timeout ]; then
        log_warn "部分 Pod 在 ${timeout}s 内未就绪，请手动检查："
        kubectl get pods -n "$NS" --no-headers | grep -v "Running"
    fi
}

# ======================== 验证 ========================
verify() {
    log_step "部署验证"

    # Pod 统计
    local total running crash
    total=$(kubectl get pods -n "$NS" --no-headers | wc -l | tr -d ' ')
    running=$(kubectl get pods -n "$NS" --no-headers | grep "Running" | wc -l | tr -d ' ')
    crash=$(kubectl get pods -n "$NS" --no-headers | grep "CrashLoopBackOff" | wc -l | tr -d ' ')

    echo ""
    log_info "Pod 总数:           $total （预期 56）"
    log_info "Running:            $running"
    if [ "$crash" -gt 0 ]; then
        log_error "CrashLoopBackOff:   $crash"
    fi

    # Helm releases
    echo ""
    log_info "Helm releases:"
    helm list -n "$NS" --short | while read -r name; do
        log_info "  - $name"
    done

    # NodePort
    echo ""
    log_info "NodePort 服务:"
    kubectl get svc -n "$NS" -o wide | grep NodePort | while read -r line; do
        log_info "  $line"
    done

    # 最终状态
    echo ""
    if [ "$running" -ge 56 ]; then
        log_ok "部署成功！共 $running 个 Pod 运行中"
        log_info "UI Dashboard:  http://<node-ip>:32677"
        log_info "Gateway API:   http://<node-ip>:30467"
    elif [ "$running" -ge 50 ]; then
        log_warn "大部分 Pod 已就绪（$running/56），部分仍在启动中"
    else
        log_error "仅 $running/56 个 Pod Running，请检查问题 Pod："
        kubectl get pods -n "$NS" | grep -v -E "Running|Completed|NAME"
    fi
}

# ======================== 主流程 ========================
main() {
    echo ""
    echo "============================================"
    echo "  Train-Ticket 一键卸载 + 部署"
    echo "  命名空间: $NS"
    echo "  项目目录: $PROJECT_ROOT"
    echo "============================================"
    echo ""

    # 检查工具
    for cmd in kubectl helm; do
        if ! command -v "$cmd" &>/dev/null; then
            log_error "$cmd 未安装"
            exit 1
        fi
    done

    # 检查集群连接
    if ! kubectl cluster-info &>/dev/null; then
        log_error "无法连接 K8s 集群，请检查 KUBECONFIG"
        exit 1
    fi

    # 检查关键文件
    for f in "$DEPLOY_YAML" "$SVC_YAML" "$MYSQL_CHART/values.yaml" "$NACOS_CHART/values.yaml" "$RABBITMQ_CHART/values.yaml"; do
        if [ ! -f "$f" ]; then
            log_error "缺少关键文件: $f"
            exit 1
        fi
    done

    log_ok "前置检查通过"

    # 执行
    uninstall
    deploy
    verify
}

main
