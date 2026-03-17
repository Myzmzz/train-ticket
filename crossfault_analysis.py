#!/usr/bin/env python3
"""
CrossFault Analysis: TrainTicket System Cross-Dimension Coupled Fault Scenario Generation
Phase 1.4: Data Integration
Phase 2.1: RiskRank Computation
Phase 2.2: Fault Mode Derivation
Phase 3.1: Propagation Chain Identification
"""

import json
import copy
from collections import defaultdict, Counter

# ========================
# Phase 1.4: Data Integration
# ========================

def load_data():
    """Load all data sources."""
    with open('call_graph.json') as f:
        call_graph = json.load(f)
    with open('fault_tolerance_config.json') as f:
        ft_config = json.load(f)
    with open('k8s_service_summary.json') as f:
        k8s_summary = json.load(f)
    return call_graph, ft_config, k8s_summary


def deduplicate_call_graph(call_graph):
    """Deduplicate call graph edges (keep unique from->to pairs)."""
    seen = {}
    for edge in call_graph:
        key = (edge['from'], edge['to'])
        if key not in seen:
            seen[key] = edge
    return list(seen.values())


def build_ft_lookup(ft_config):
    """Build lookup for fault tolerance by (from, to) edge."""
    lookup = {}
    for entry in ft_config.get('edge_fault_tolerance', []):
        key = (entry['from'], entry['to'])
        lookup[key] = entry
    return lookup


def identify_business_paths(call_graph_dedup):
    """Identify business paths from call graph using BFS from entry points."""
    # Build adjacency list
    adj = defaultdict(set)
    for edge in call_graph_dedup:
        adj[edge['from']].add(edge['to'])

    # All services
    all_services = set()
    for edge in call_graph_dedup:
        all_services.add(edge['from'])
        all_services.add(edge['to'])

    # Core business paths based on TrainTicket architecture
    # Entry points are typically through gateway or preserve/rebook/cancel services
    business_paths = []

    # Define known business path starting points and names
    path_definitions = [
        {
            "name": "购票流程",
            "entry": "ts-preserve-service",
            "key_services": ["ts-order-service", "ts-seat-service", "ts-travel-service",
                           "ts-contacts-service", "ts-station-service", "ts-security-service",
                           "ts-inside-payment-service"]
        },
        {
            "name": "购票流程（其他）",
            "entry": "ts-preserve-other-service",
            "key_services": ["ts-order-other-service", "ts-seat-service", "ts-travel2-service",
                           "ts-contacts-service", "ts-station-service", "ts-security-service",
                           "ts-inside-payment-service"]
        },
        {
            "name": "改签流程",
            "entry": "ts-rebook-service",
            "key_services": ["ts-order-service", "ts-order-other-service", "ts-travel-service",
                           "ts-travel2-service", "ts-seat-service", "ts-inside-payment-service",
                           "ts-station-service"]
        },
        {
            "name": "退票流程",
            "entry": "ts-cancel-service",
            "key_services": ["ts-order-service", "ts-order-other-service",
                           "ts-inside-payment-service", "ts-user-service"]
        },
        {
            "name": "支付流程",
            "entry": "ts-inside-payment-service",
            "key_services": ["ts-order-service", "ts-order-other-service", "ts-payment-service"]
        },
        {
            "name": "行程查询",
            "entry": "ts-travel-service",
            "key_services": ["ts-route-service", "ts-train-service", "ts-station-service",
                           "ts-price-service", "ts-order-service", "ts-seat-service"]
        },
        {
            "name": "行程查询（其他）",
            "entry": "ts-travel2-service",
            "key_services": ["ts-route-service", "ts-train-service", "ts-station-service",
                           "ts-price-service", "ts-order-other-service", "ts-seat-service"]
        },
        {
            "name": "路线规划",
            "entry": "ts-travel-plan-service",
            "key_services": ["ts-travel-service", "ts-travel2-service", "ts-route-plan-service",
                           "ts-seat-service", "ts-station-service"]
        },
        {
            "name": "执行/检票流程",
            "entry": "ts-execute-service",
            "key_services": ["ts-order-service", "ts-order-other-service"]
        },
        {
            "name": "管理后台-基础信息",
            "entry": "ts-admin-basic-info-service",
            "key_services": ["ts-station-service", "ts-train-service", "ts-route-service",
                           "ts-price-service", "ts-config-service", "ts-contacts-service"]
        },
        {
            "name": "管理后台-旅行管理",
            "entry": "ts-admin-travel-service",
            "key_services": ["ts-travel-service", "ts-travel2-service"]
        },
        {
            "name": "管理后台-订单管理",
            "entry": "ts-admin-order-service",
            "key_services": ["ts-order-service", "ts-order-other-service"]
        },
    ]

    for pdef in path_definitions:
        entry = pdef["entry"]
        if entry not in all_services:
            continue
        # BFS to find reachable key services
        path_services = [entry]
        visited = {entry}
        queue = [entry]
        while queue:
            current = queue.pop(0)
            for neighbor in adj.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    if neighbor in pdef["key_services"] or neighbor in adj:
                        path_services.append(neighbor)
                        queue.append(neighbor)

        # Filter to only include services that are in the key_services or entry
        relevant = [s for s in path_services if s == entry or s in pdef["key_services"]]
        business_paths.append({
            "name": pdef["name"],
            "entry": entry,
            "path": relevant,
            "depth": len(relevant)
        })

    return business_paths


def integrate_data(call_graph, ft_config, k8s_summary):
    """Integrate all data into risk_atlas.json."""
    call_graph_dedup = deduplicate_call_graph(call_graph)
    ft_lookup = build_ft_lookup(ft_config)
    business_paths = identify_business_paths(call_graph_dedup)

    # Build adjacency info
    upstream = defaultdict(set)
    downstream = defaultdict(set)
    for edge in call_graph_dedup:
        upstream[edge['to']].add(edge['from'])
        downstream[edge['from']].add(edge['to'])

    # All service names from K8s
    all_services = set(k8s_summary['services'].keys())
    # Also add services from call graph
    for edge in call_graph_dedup:
        all_services.add(edge['from'])
        all_services.add(edge['to'])

    # Determine which business paths each service is in
    service_paths = defaultdict(list)
    for bp in business_paths:
        for svc in bp['path']:
            if bp['name'] not in service_paths[svc]:
                service_paths[svc].append(bp['name'])

    # Build co-located services map
    node_services = defaultdict(list)
    for svc_name, svc_data in k8s_summary['services'].items():
        node = svc_data.get('node', 'unknown')
        node_services[node].append(svc_name)

    # Build services list
    services = []
    for svc_name in sorted(all_services):
        if 'tracetest' in svc_name:
            continue

        k8s = k8s_summary['services'].get(svc_name, {})
        node = k8s.get('node', 'unknown')
        co_located = [s for s in node_services.get(node, []) if s != svc_name]

        # Incoming edges with fault tolerance
        incoming_ft = []
        for caller in upstream.get(svc_name, set()):
            key = (caller, svc_name)
            if key in ft_lookup:
                incoming_ft.append(ft_lookup[key])
            else:
                incoming_ft.append({
                    "from": caller,
                    "to": svc_name,
                    "fault_tolerance": {
                        "retry": {"present": False},
                        "circuit_breaker": {"present": False},
                        "timeout": {"present": False},
                        "bulkhead": {"present": False},
                        "fallback": {"present": False}
                    },
                    "protection_level": "none",
                    "beta": 10
                })

        # Outgoing edges with fault tolerance
        outgoing_ft = []
        for callee in downstream.get(svc_name, set()):
            key = (svc_name, callee)
            if key in ft_lookup:
                outgoing_ft.append(ft_lookup[key])
            else:
                outgoing_ft.append({
                    "from": svc_name,
                    "to": callee,
                    "fault_tolerance": {
                        "retry": {"present": False},
                        "circuit_breaker": {"present": False},
                        "timeout": {"present": False},
                        "bulkhead": {"present": False},
                        "fallback": {"present": False}
                    },
                    "protection_level": "none",
                    "beta": 10
                })

        svc_entry = {
            "name": svc_name,
            "k8s_config": {
                "replicas": k8s.get('replicas', 1),
                "liveness_probe": k8s.get('liveness_probe', False),
                "readiness_probe": k8s.get('readiness_probe', False),
                "resource_limits": k8s.get('resource_limits', {"cpu": None, "memory": None}),
                "resource_requests": k8s.get('resource_requests', {"cpu": None, "memory": None}),
                "strategy": k8s.get('strategy', {"type": "RollingUpdate", "max_unavailable": "N/A"}),
                "anti_affinity": k8s.get('anti_affinity', False)
            },
            "topology": {
                "upstream_callers": sorted(list(upstream.get(svc_name, set()))),
                "downstream_callees": sorted(list(downstream.get(svc_name, set()))),
                "in_degree": len(upstream.get(svc_name, set())),
                "out_degree": len(downstream.get(svc_name, set())),
                "business_paths": service_paths.get(svc_name, [])
            },
            "resource": {
                "node": node,
                "qos_class": k8s.get('qos_class', 'unknown'),
                "co_located_services": co_located
            },
            "incoming_edges_ft": incoming_ft,
            "outgoing_edges_ft": outgoing_ft
        }
        services.append(svc_entry)

    risk_atlas = {
        "services": services,
        "call_graph": call_graph_dedup,
        "business_paths": business_paths,
        "nodes": k8s_summary.get('nodes', {})
    }
    return risk_atlas


# ========================
# Phase 2.1: RiskRank Computation
# ========================

def compute_riskrank(risk_atlas, damping=0.85, max_iter=100, tol=1e-6):
    """Compute RiskRank scores for all services."""
    services = risk_atlas['services']
    svc_map = {s['name']: s for s in services}

    # Step 1: Compute local risk
    for svc in services:
        local_risk = 0
        k8s = svc['k8s_config']

        # K8s config risks
        if k8s['replicas'] == 1:
            local_risk += 4  # Critical: single replica
        if not k8s['liveness_probe']:
            local_risk += 3  # High: no liveness probe
        if not k8s['readiness_probe']:
            local_risk += 2  # Medium: no readiness probe
        if k8s['resource_limits']['cpu'] is None and k8s['resource_limits']['memory'] is None:
            local_risk += 3  # High: no resource limits
        if not k8s['anti_affinity']:
            local_risk += 1  # Low: no anti-affinity

        # Incoming edge fault tolerance risks
        for edge in svc['incoming_edges_ft']:
            pl = edge.get('protection_level', 'none')
            if pl == 'flawed_retry':
                local_risk += 4
            elif pl == 'none':
                local_risk += 3
            elif pl == 'timeout_only':
                local_risk += 2
            elif pl == 'flawed_cb':
                local_risk += 3

        # Resource risks
        if svc['resource']['qos_class'] == 'BestEffort':
            local_risk += 3
        co_located_no_limits = 0
        for co_svc in svc['resource']['co_located_services']:
            if co_svc in svc_map:
                co_k8s = svc_map[co_svc]['k8s_config']
                if co_k8s['resource_limits']['cpu'] is None and co_k8s['resource_limits']['memory'] is None:
                    co_located_no_limits += 1
        if co_located_no_limits >= 2 and k8s['resource_limits']['cpu'] is None:
            local_risk += 2

        svc['local_risk'] = local_risk

    # Build edge beta lookup
    edge_beta = {}
    for svc in services:
        for edge in svc['outgoing_edges_ft']:
            edge_beta[(edge['from'], edge['to'])] = edge.get('beta', 10)
        for edge in svc['incoming_edges_ft']:
            edge_beta[(edge['from'], edge['to'])] = edge.get('beta', 10)

    # Step 2: Iterative propagation
    riskrank = {s['name']: float(s['local_risk']) for s in services}

    for iteration in range(max_iter):
        new_scores = {}
        for svc in services:
            name = svc['name']
            propagated = 0.0

            # From upstream callers
            for caller in svc['topology']['upstream_callers']:
                if caller in riskrank:
                    beta = edge_beta.get((caller, name), 10)
                    caller_out_degree = svc_map[caller]['topology']['out_degree'] if caller in svc_map else 1
                    if caller_out_degree > 0:
                        propagated += riskrank[caller] * beta / caller_out_degree

            # From downstream callees
            for callee in svc['topology']['downstream_callees']:
                if callee in riskrank:
                    beta = edge_beta.get((name, callee), 10)
                    callee_in_degree = svc_map[callee]['topology']['in_degree'] if callee in svc_map else 1
                    if callee_in_degree > 0:
                        propagated += riskrank[callee] * beta / callee_in_degree

            new_scores[name] = (1 - damping) * svc['local_risk'] + damping * propagated

        # Check convergence
        max_change = max(abs(new_scores[s['name']] - riskrank[s['name']]) for s in services)
        riskrank = new_scores

        if max_change < tol:
            print(f"RiskRank converged after {iteration + 1} iterations (max_change={max_change:.8f})")
            break
    else:
        print(f"RiskRank did not converge after {max_iter} iterations (max_change={max_change:.4f})")

    # Normalize: scale so max = 100
    max_rr = max(riskrank.values()) if riskrank else 1
    if max_rr > 0:
        for k in riskrank:
            riskrank[k] = riskrank[k] / max_rr * 100

    # Store back
    for svc in services:
        svc['riskrank'] = round(riskrank[svc['name']], 2)

    return riskrank


def compute_path_risk(risk_atlas, riskrank):
    """Compute PathRisk for each business path."""
    svc_map = {s['name']: s for s in risk_atlas['services']}
    path_risks = []

    for bp in risk_atlas['business_paths']:
        path_score = 0
        for svc_name in bp['path']:
            if svc_name in riskrank:
                path_score += riskrank[svc_name]
        path_risks.append({
            "name": bp['name'],
            "path": bp['path'],
            "depth": bp['depth'],
            "path_risk": round(path_score, 2)
        })

    path_risks.sort(key=lambda x: x['path_risk'], reverse=True)
    return path_risks


def identify_focus_services(risk_atlas, riskrank, top_n=15):
    """Identify focus services: top RiskRank + path crossroads."""
    # Top N by RiskRank
    sorted_rr = sorted(riskrank.items(), key=lambda x: x[1], reverse=True)
    top_services = set(s[0] for s in sorted_rr[:top_n])

    # Services with path crossing degree > 1
    svc_map = {s['name']: s for s in risk_atlas['services']}
    for svc in risk_atlas['services']:
        if len(svc['topology']['business_paths']) > 1:
            top_services.add(svc['name'])

    return sorted(top_services, key=lambda x: riskrank.get(x, 0), reverse=True)


# ========================
# Phase 2.2: Fault Mode Derivation
# ========================

def derive_fault_modes(risk_atlas, focus_services):
    """Apply interaction rules to derive fault modes for focus services."""
    svc_map = {s['name']: s for s in risk_atlas['services']}
    all_fault_modes = []
    mode_counter = defaultdict(int)

    for svc_name in focus_services:
        if svc_name not in svc_map:
            continue
        svc = svc_map[svc_name]
        k8s = svc['k8s_config']
        modes = []
        prefix = svc_name.replace('ts-', '').replace('-service', '').upper()[:3]

        # Helpers
        is_single_replica = k8s['replicas'] == 1
        no_liveness = not k8s['liveness_probe']
        no_readiness = not k8s['readiness_probe']
        no_limits = k8s['resource_limits']['cpu'] is None and k8s['resource_limits']['memory'] is None
        no_anti_affinity = not k8s['anti_affinity']
        in_degree = svc['topology']['in_degree']
        out_degree = svc['topology']['out_degree']

        # Incoming edge analysis
        incoming_flawed_retry = [e for e in svc['incoming_edges_ft'] if e.get('protection_level') == 'flawed_retry']
        incoming_no_protection = [e for e in svc['incoming_edges_ft'] if e.get('protection_level') == 'none']
        incoming_timeout_only = [e for e in svc['incoming_edges_ft'] if e.get('protection_level') == 'timeout_only']
        incoming_flawed_cb = [e for e in svc['incoming_edges_ft'] if e.get('protection_level') == 'flawed_cb']

        # Outgoing edge analysis
        outgoing_no_timeout = [e for e in svc['outgoing_edges_ft']
                              if not e.get('fault_tolerance', {}).get('timeout', {}).get('present', False)]
        outgoing_no_protection = [e for e in svc['outgoing_edges_ft'] if e.get('protection_level') == 'none']

        # Co-location analysis
        co_located = svc['resource']['co_located_services']
        co_located_no_limits = []
        for co_svc in co_located:
            if co_svc in svc_map:
                co_k8s = svc_map[co_svc]['k8s_config']
                if co_k8s['resource_limits']['cpu'] is None and co_k8s['resource_limits']['memory'] is None:
                    co_located_no_limits.append(co_svc)

        mode_counter[svc_name] = 0

        # R_CC1: Single replica + no liveness probe → "僵死永久不可用"
        if is_single_replica and no_liveness:
            mode_counter[svc_name] += 1
            modes.append({
                "mode_id": f"{prefix}-FM{mode_counter[svc_name]}",
                "service": svc_name,
                "name": "僵死永久不可用",
                "matched_rule": "R_CC1",
                "involved_risks": [f"单副本(replicas={k8s['replicas']})", "无存活探针(livenessProbe=false)"],
                "dimensions": ["配置", "配置"],
                "trigger_condition": "容器进程死锁或内存泄漏导致进程假死",
                "local_effect": "服务进程不响应但 Pod 状态仍为 Running，K8s 不会重启",
                "propagation_direction": "向上游传播超时/错误",
                "amplification_factor": 1,
                "severity": "严重"
            })

        # R_CC2: No resource limits + no liveness probe → "内存泄漏渐进性退化"
        if no_limits and no_liveness:
            mode_counter[svc_name] += 1
            modes.append({
                "mode_id": f"{prefix}-FM{mode_counter[svc_name]}",
                "service": svc_name,
                "name": "内存泄漏渐进性退化",
                "matched_rule": "R_CC2",
                "involved_risks": ["无资源限制(limits=null)", "无存活探针(livenessProbe=false)"],
                "dimensions": ["配置", "配置"],
                "trigger_condition": "长时间运行后内存逐渐增长",
                "local_effect": "服务响应时间逐渐增加，最终 OOM 或影响同节点服务",
                "propagation_direction": "向上游传播慢响应 + 同节点资源争抢",
                "amplification_factor": 1,
                "severity": "高"
            })

        # R_CC3: No readiness probe + rolling update → "更新期间隐形中断"
        if no_readiness and k8s['strategy'].get('type') == 'RollingUpdate':
            mode_counter[svc_name] += 1
            modes.append({
                "mode_id": f"{prefix}-FM{mode_counter[svc_name]}",
                "service": svc_name,
                "name": "更新期间隐形中断",
                "matched_rule": "R_CC3",
                "involved_risks": ["无就绪探针(readinessProbe=false)", f"滚动更新(strategy={k8s['strategy']['type']})"],
                "dimensions": ["配置", "配置"],
                "trigger_condition": "Deployment 滚动更新期间",
                "local_effect": "新 Pod 在未就绪时即接收流量，返回错误",
                "propagation_direction": "向上游传播错误响应",
                "amplification_factor": 1,
                "severity": "中"
            })

        # R_CF1: Single replica + incoming flawed retry (no CB) → "重试风暴阻止恢复"
        if is_single_replica and incoming_flawed_retry:
            total_beta = sum(e.get('beta', 0) for e in incoming_flawed_retry)
            involved = [f"单副本(replicas=1)"]
            for e in incoming_flawed_retry:
                retry_info = e.get('fault_tolerance', {}).get('retry', {})
                involved.append(
                    f"入边 {e['from']}→{svc_name}: retry={retry_info.get('max_attempts', '?')}"
                    f"/backoff={retry_info.get('backoff', 'none')}/no CB"
                )
            mode_counter[svc_name] += 1
            modes.append({
                "mode_id": f"{prefix}-FM{mode_counter[svc_name]}",
                "service": svc_name,
                "name": "重试风暴阻止恢复",
                "matched_rule": "R_CF1",
                "involved_risks": involved,
                "dimensions": ["配置", "容错"],
                "trigger_condition": "容器实例崩溃或进程异常退出",
                "local_effect": "服务完全不可用且无法恢复，重试流量持续涌入",
                "propagation_direction": "自我恶化 + 向上游传播错误",
                "amplification_factor": total_beta,
                "severity": "严重"
            })

        # R_CF2: No resource limits + outgoing no timeout → "双重资源耗尽"
        if no_limits and outgoing_no_timeout:
            targets = [e['to'] for e in outgoing_no_timeout]
            mode_counter[svc_name] += 1
            modes.append({
                "mode_id": f"{prefix}-FM{mode_counter[svc_name]}",
                "service": svc_name,
                "name": "双重资源耗尽",
                "matched_rule": "R_CF2",
                "involved_risks": ["无资源限制(limits=null)"] +
                                  [f"出边 {svc_name}→{t}: 无超时" for t in targets[:5]],
                "dimensions": ["配置", "容错"],
                "trigger_condition": "下游服务响应变慢",
                "local_effect": "线程池耗尽等待下游响应，内存持续增长无限制",
                "propagation_direction": "向上游传播不可用 + 本地资源耗尽影响同节点",
                "amplification_factor": len(outgoing_no_timeout),
                "severity": "高"
            })

        # R_CF3: Single replica + incoming retry with backoff, no CB → "延迟恢复"
        incoming_retry_backoff = [e for e in svc['incoming_edges_ft']
                                  if e.get('fault_tolerance', {}).get('retry', {}).get('present', False)
                                  and e.get('fault_tolerance', {}).get('retry', {}).get('backoff', 'none') != 'none'
                                  and not e.get('fault_tolerance', {}).get('circuit_breaker', {}).get('present', False)]
        if is_single_replica and incoming_retry_backoff:
            mode_counter[svc_name] += 1
            modes.append({
                "mode_id": f"{prefix}-FM{mode_counter[svc_name]}",
                "service": svc_name,
                "name": "延迟恢复",
                "matched_rule": "R_CF3",
                "involved_risks": ["单副本(replicas=1)"] +
                                  [f"入边 {e['from']}→{svc_name}: retry+backoff/no CB" for e in incoming_retry_backoff[:3]],
                "dimensions": ["配置", "容错"],
                "trigger_condition": "服务短暂不可用后恢复",
                "local_effect": "退避重试减缓恢复速度但不阻止恢复",
                "propagation_direction": "向上游传播延迟",
                "amplification_factor": sum(e.get('beta', 0) for e in incoming_retry_backoff),
                "severity": "中"
            })

        # R_CR1: No resource limits + co-located with >=2 no-limit services → "噪声邻居"
        if no_limits and len(co_located_no_limits) >= 2:
            mode_counter[svc_name] += 1
            modes.append({
                "mode_id": f"{prefix}-FM{mode_counter[svc_name]}",
                "service": svc_name,
                "name": "噪声邻居",
                "matched_rule": "R_CR1",
                "involved_risks": [f"无资源限制(limits=null)",
                                   f"同节点{svc['resource']['node']}共置{len(co_located_no_limits)}个无限制服务: {', '.join(co_located_no_limits[:5])}"],
                "dimensions": ["配置", "资源"],
                "trigger_condition": "同节点服务突发高负载",
                "local_effect": "CPU/内存被邻居服务挤占，响应延迟大幅上升",
                "propagation_direction": "向上游传播慢响应",
                "amplification_factor": len(co_located_no_limits),
                "severity": "高"
            })

        # R_CR2: Single replica + low QoS + node resource pressure → "抢占驱逐"
        if is_single_replica and svc['resource']['qos_class'] in ('BestEffort', 'Burstable'):
            mode_counter[svc_name] += 1
            modes.append({
                "mode_id": f"{prefix}-FM{mode_counter[svc_name]}",
                "service": svc_name,
                "name": "抢占驱逐",
                "matched_rule": "R_CR2",
                "involved_risks": [f"单副本(replicas=1)",
                                   f"QoS={svc['resource']['qos_class']}",
                                   f"节点={svc['resource']['node']}"],
                "dimensions": ["配置", "资源"],
                "trigger_condition": "节点资源压力触发驱逐",
                "local_effect": "Pod 被驱逐，服务完全不可用直到重新调度",
                "propagation_direction": "向上游传播不可用",
                "amplification_factor": 1,
                "severity": "中"
            })

        # R_TF1: High fan-in (>=5) + incoming flawed retry → "汇聚放大"
        all_incoming_risky = incoming_flawed_retry + incoming_no_protection
        if in_degree >= 5 and (incoming_flawed_retry or incoming_no_protection):
            avg_beta = sum(e.get('beta', 10) for e in all_incoming_risky) / max(len(all_incoming_risky), 1)
            amp = in_degree * avg_beta
            mode_counter[svc_name] += 1
            modes.append({
                "mode_id": f"{prefix}-FM{mode_counter[svc_name]}",
                "service": svc_name,
                "name": "汇聚放大",
                "matched_rule": "R_TF1",
                "involved_risks": [f"高扇入度(in_degree={in_degree})",
                                   f"有风险入边{len(all_incoming_risky)}条(flawed_retry={len(incoming_flawed_retry)}, none={len(incoming_no_protection)})"],
                "dimensions": ["拓扑", "容错"],
                "trigger_condition": "服务响应变慢或间歇性失败",
                "local_effect": "多个上游同时重试/阻塞，流量激增",
                "propagation_direction": "多个上游同时受影响",
                "amplification_factor": round(amp, 1),
                "severity": "严重" if amp > 50 else "高"
            })

        # R_TF2: Deep call chain (>=4 hops) + inconsistent timeouts
        # Check if this service is in any deep path
        for bp in risk_atlas['business_paths']:
            if svc_name in bp['path'] and bp['depth'] >= 4:
                # Check timeout consistency along the path
                has_timeout_inconsistency = False
                path_svcs = bp['path']
                for i in range(len(path_svcs) - 1):
                    caller = path_svcs[i]
                    callee = path_svcs[i + 1]
                    for edge in svc_map.get(caller, {}).get('outgoing_edges_ft', []):
                        if edge.get('to') == callee:
                            timeout = edge.get('fault_tolerance', {}).get('timeout', {})
                            if not timeout.get('present', False):
                                has_timeout_inconsistency = True
                                break

                if has_timeout_inconsistency:
                    mode_counter[svc_name] += 1
                    modes.append({
                        "mode_id": f"{prefix}-FM{mode_counter[svc_name]}",
                        "service": svc_name,
                        "name": "不可预测的超时传播",
                        "matched_rule": "R_TF2",
                        "involved_risks": [f"深调用链(路径'{bp['name']}'深度={bp['depth']})",
                                           "链上超时配置不一致"],
                        "dimensions": ["拓扑", "容错"],
                        "trigger_condition": "链末端服务响应变慢",
                        "local_effect": "超时在链上逐级放大，行为不可预测",
                        "propagation_direction": "沿调用链向上游逐级传播",
                        "amplification_factor": bp['depth'],
                        "severity": "高"
                    })
                    break  # One mode per service for this rule

        # R_TF3: Single path dependency + timeout only + single replica → "功能完全不可用"
        if is_single_replica:
            for edge in svc['incoming_edges_ft']:
                if edge.get('protection_level') == 'timeout_only':
                    # Check if the caller has only this one path to the functionality
                    caller = edge['from']
                    if caller in svc_map:
                        caller_downstream = svc_map[caller]['topology']['downstream_callees']
                        mode_counter[svc_name] += 1
                        modes.append({
                            "mode_id": f"{prefix}-FM{mode_counter[svc_name]}",
                            "service": svc_name,
                            "name": "功能完全不可用",
                            "matched_rule": "R_TF3",
                            "involved_risks": [f"单副本(replicas=1)",
                                               f"入边 {caller}→{svc_name}: 仅超时保护",
                                               "无降级方案"],
                            "dimensions": ["拓扑", "容错"],
                            "trigger_condition": "服务实例不可用",
                            "local_effect": f"调用方{caller}的相关功能完全不可用",
                            "propagation_direction": "向上游传播功能缺失",
                            "amplification_factor": 1,
                            "severity": "高"
                        })
                        break  # One per service

        # R_TR1: Path crossing >=2 + co-located → "多路径峰值叠加"
        if len(svc['topology']['business_paths']) >= 2:
            co_in_paths = [c for c in co_located if c in svc_map and
                          len(svc_map[c]['topology']['business_paths']) >= 1]
            if co_in_paths:
                mode_counter[svc_name] += 1
                modes.append({
                    "mode_id": f"{prefix}-FM{mode_counter[svc_name]}",
                    "service": svc_name,
                    "name": "多路径峰值叠加",
                    "matched_rule": "R_TR1",
                    "involved_risks": [f"路径交叉度={len(svc['topology']['business_paths'])}",
                                       f"同节点共置业务服务: {', '.join(co_in_paths[:5])}"],
                    "dimensions": ["拓扑", "资源"],
                    "trigger_condition": "多条业务路径同时高负载",
                    "local_effect": "多路径流量叠加，节点资源饱和",
                    "propagation_direction": "影响同节点所有服务 + 向多条业务路径传播",
                    "amplification_factor": len(svc['topology']['business_paths']),
                    "severity": "高"
                })

        # R_FR1: Outgoing no timeout + downstream co-located → "双通道耦合"
        for edge in outgoing_no_timeout:
            target = edge['to']
            if target in svc_map and svc_map[target]['resource']['node'] == svc['resource']['node']:
                mode_counter[svc_name] += 1
                modes.append({
                    "mode_id": f"{prefix}-FM{mode_counter[svc_name]}",
                    "service": svc_name,
                    "name": "双通道耦合",
                    "matched_rule": "R_FR1",
                    "involved_risks": [f"出边 {svc_name}→{target}: 无超时",
                                       f"两服务同节点({svc['resource']['node']})共置"],
                    "dimensions": ["容错", "资源"],
                    "trigger_condition": f"{target}高负载或资源争抢",
                    "local_effect": f"调用链阻塞 + 同节点资源争抢双重影响",
                    "propagation_direction": "调用链传播 + 物理层传播",
                    "amplification_factor": 2,
                    "severity": "高"
                })
                break  # One per service

        if modes:
            all_fault_modes.append({
                "service": svc_name,
                "riskrank": svc_map[svc_name].get('riskrank', 0),
                "fault_modes": modes
            })

    return all_fault_modes


# ========================
# Phase 3.1: Propagation Chain Identification
# ========================

def identify_propagation_chains(risk_atlas, all_fault_modes, focus_services):
    """Identify cross-service propagation chains."""
    svc_map = {s['name']: s for s in risk_atlas['services']}
    fm_map = {fm['service']: fm for fm in all_fault_modes}

    chains = []
    self_loops = []

    # Build edge beta lookup
    edge_beta = {}
    for svc in risk_atlas['services']:
        for edge in svc['outgoing_edges_ft']:
            edge_beta[(edge['from'], edge['to'])] = edge

    # For each pair of focus services with a call relationship
    for svc in risk_atlas['services']:
        if svc['name'] not in focus_services:
            continue

        for callee_name in svc['topology']['downstream_callees']:
            if callee_name not in focus_services:
                continue
            if callee_name not in fm_map:
                continue

            caller_name = svc['name']
            edge_key = (caller_name, callee_name)
            edge_info = edge_beta.get(edge_key, {})
            beta = edge_info.get('beta', 10)

            # Check if callee has fault modes that propagate upstream
            callee_modes = fm_map[callee_name]['fault_modes']
            upstream_propagating = [m for m in callee_modes
                                    if '向上游' in m.get('propagation_direction', '') or
                                    '传播' in m.get('propagation_direction', '')]

            if upstream_propagating and beta > 1:
                for mode in upstream_propagating:
                    chain = {
                        "origin_service": callee_name,
                        "origin_mode": mode['name'],
                        "origin_mode_id": mode['mode_id'],
                        "propagation_path": [
                            {
                                "step": 1,
                                "from": callee_name,
                                "to": caller_name,
                                "mechanism": mode['local_effect'],
                                "edge_beta": beta,
                                "edge_protection": edge_info.get('protection_level', 'none')
                            }
                        ],
                        "total_services": 2,
                        "cumulative_amplification": beta * mode.get('amplification_factor', 1),
                        "severity": mode['severity']
                    }

                    # Check for self-worsening loop
                    if caller_name in fm_map:
                        caller_modes = fm_map[caller_name]['fault_modes']
                        retry_modes = [m for m in caller_modes
                                       if '重试' in m.get('name', '') or '放大' in m.get('name', '')]
                        if retry_modes:
                            for rm in retry_modes:
                                self_loops.append({
                                    "services": [callee_name, caller_name],
                                    "description": f"{callee_name}故障 → {caller_name}重试 → {callee_name}负载加重",
                                    "callee_mode": mode['name'],
                                    "caller_mode": rm['name'],
                                    "amplification": beta * rm.get('amplification_factor', 1)
                                })

                    chains.append(chain)

    # Multi-hop concatenation
    extended_chains = []
    for chain_a in chains:
        last_svc = chain_a['propagation_path'][-1]['to']
        for chain_b in chains:
            first_svc = chain_b['origin_service']
            # Find chains where chain_a ends at the origin of chain_b
            # Actually, we need chain_a's last "to" to be chain_b's first "from" (which is origin)
            if last_svc == chain_b['propagation_path'][0]['to']:
                continue  # Avoid same chain
            # Check if chain_a's end service calls chain_b's origin
            if last_svc in svc_map and first_svc in svc_map[last_svc]['topology']['downstream_callees']:
                # We can extend: chain_a + link to first_svc + chain_b
                new_chain = copy.deepcopy(chain_a)
                link_edge = edge_beta.get((last_svc, first_svc), {})
                link_beta = link_edge.get('beta', 10)
                step_n = len(new_chain['propagation_path']) + 1
                new_chain['propagation_path'].append({
                    "step": step_n,
                    "from": last_svc,
                    "to": first_svc,
                    "mechanism": f"故障从{last_svc}传播到其下游{first_svc}",
                    "edge_beta": link_beta,
                    "edge_protection": link_edge.get('protection_level', 'none')
                })
                for step in chain_b['propagation_path']:
                    step_n += 1
                    new_step = copy.deepcopy(step)
                    new_step['step'] = step_n
                    new_chain['propagation_path'].append(new_step)

                all_svcs = set()
                for s in new_chain['propagation_path']:
                    all_svcs.add(s['from'])
                    all_svcs.add(s['to'])
                new_chain['total_services'] = len(all_svcs)
                new_chain['cumulative_amplification'] = (
                    chain_a['cumulative_amplification'] * link_beta *
                    chain_b['cumulative_amplification']
                )
                extended_chains.append(new_chain)

    # Combine and sort
    all_chains = chains + extended_chains
    all_chains.sort(key=lambda x: (x['total_services'], x['cumulative_amplification']), reverse=True)

    # Deduplicate: keep unique by origin + path
    seen = set()
    unique_chains = []
    for chain in all_chains:
        path_key = (chain['origin_service'], chain['origin_mode_id'],
                    tuple((s['from'], s['to']) for s in chain['propagation_path']))
        if path_key not in seen:
            seen.add(path_key)
            unique_chains.append(chain)

    return unique_chains[:30], self_loops  # Top 30 chains


# ========================
# Main execution
# ========================

def main():
    print("=" * 60)
    print("CrossFault Analysis: TrainTicket System")
    print("=" * 60)

    # Phase 1.4: Data Integration
    print("\n[Phase 1.4] Loading and integrating data...")
    call_graph, ft_config, k8s_summary = load_data()
    risk_atlas = integrate_data(call_graph, ft_config, k8s_summary)

    with open('risk_atlas.json', 'w') as f:
        json.dump(risk_atlas, f, indent=2, ensure_ascii=False)
    print(f"  Services: {len(risk_atlas['services'])}")
    print(f"  Call edges (dedup): {len(risk_atlas['call_graph'])}")
    print(f"  Business paths: {len(risk_atlas['business_paths'])}")

    # Phase 2.1: RiskRank
    print("\n[Phase 2.1] Computing RiskRank...")
    riskrank = compute_riskrank(risk_atlas)

    # Top 15 by RiskRank
    sorted_rr = sorted(riskrank.items(), key=lambda x: x[1], reverse=True)
    print("\nTop-15 RiskRank:")
    for i, (name, score) in enumerate(sorted_rr[:15]):
        svc = next(s for s in risk_atlas['services'] if s['name'] == name)
        print(f"  {i+1:2d}. {name:<40s} RR={score:6.2f}  local={svc['local_risk']:3d}  in={svc['topology']['in_degree']:2d}  out={svc['topology']['out_degree']:2d}")

    # Path risks
    path_risks = compute_path_risk(risk_atlas, riskrank)
    print("\nBusiness Path Risks:")
    for pr in path_risks:
        print(f"  {pr['name']:<25s} PathRisk={pr['path_risk']:8.2f}  depth={pr['depth']}")

    # Focus services
    focus_services = identify_focus_services(risk_atlas, riskrank)
    print(f"\nFocus services: {len(focus_services)}")
    for s in focus_services:
        print(f"  {s} (RR={riskrank.get(s, 0):.2f})")

    # Phase 2.2: Fault modes
    print("\n[Phase 2.2] Deriving fault modes...")
    all_fault_modes = derive_fault_modes(risk_atlas, focus_services)
    total_modes = sum(len(fm['fault_modes']) for fm in all_fault_modes)
    print(f"  Total fault modes: {total_modes}")
    for fm in all_fault_modes:
        print(f"  {fm['service']}: {len(fm['fault_modes'])} modes")
        for m in fm['fault_modes']:
            print(f"    - {m['mode_id']}: {m['name']} ({m['matched_rule']}, {m['severity']})")

    # Phase 3.1: Propagation chains
    print("\n[Phase 3.1] Identifying propagation chains...")
    chains, self_loops = identify_propagation_chains(risk_atlas, all_fault_modes, focus_services)
    print(f"  Propagation chains: {len(chains)}")
    print(f"  Self-worsening loops: {len(self_loops)}")

    for i, chain in enumerate(chains[:10]):
        path_str = " → ".join(f"{s['from']}" for s in chain['propagation_path'])
        path_str += f" → {chain['propagation_path'][-1]['to']}"
        print(f"  Chain {i+1}: {chain['origin_mode']} @ {chain['origin_service']}")
        print(f"    Path: {path_str}")
        print(f"    Services: {chain['total_services']}, Amplification: {chain['cumulative_amplification']:.0f}")

    for loop in self_loops[:5]:
        print(f"  Loop: {loop['description']} (amp={loop['amplification']:.0f})")

    # Save all intermediate results
    with open('riskrank_results.json', 'w') as f:
        json.dump({
            "riskrank": {k: round(v, 2) for k, v in sorted_rr},
            "path_risks": path_risks,
            "focus_services": focus_services
        }, f, indent=2, ensure_ascii=False)

    with open('fault_modes.json', 'w') as f:
        json.dump(all_fault_modes, f, indent=2, ensure_ascii=False)

    with open('propagation_chains.json', 'w') as f:
        json.dump({
            "chains": chains,
            "self_loops": self_loops
        }, f, indent=2, ensure_ascii=False)

    print("\n[Done] All intermediate files saved.")
    print("  - risk_atlas.json")
    print("  - riskrank_results.json")
    print("  - fault_modes.json")
    print("  - propagation_chains.json")


if __name__ == '__main__':
    main()
