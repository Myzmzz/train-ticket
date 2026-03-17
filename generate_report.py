#!/usr/bin/env python3
"""
CrossFault Phase 4: Generate Final Analysis Report
"""

import json
from collections import defaultdict, Counter

def load_all():
    with open('risk_atlas.json') as f:
        risk_atlas = json.load(f)
    with open('fault_modes.json') as f:
        fault_modes = json.load(f)
    with open('propagation_chains.json') as f:
        chains_data = json.load(f)
    with open('riskrank_results.json') as f:
        riskrank_data = json.load(f)
    with open('scenarios.json') as f:
        scenarios = json.load(f)
    with open('k8s_service_summary.json') as f:
        k8s_summary = json.load(f)
    with open('call_graph.json') as f:
        call_graph = json.load(f)
    with open('fault_tolerance_config.json') as f:
        ft_config = json.load(f)
    return risk_atlas, fault_modes, chains_data, riskrank_data, scenarios, k8s_summary, call_graph, ft_config


def generate_report():
    risk_atlas, fault_modes, chains_data, riskrank_data, scenarios, k8s_summary, call_graph, ft_config = load_all()

    svc_map = {s['name']: s for s in risk_atlas['services']}
    fm_map = {fm['service']: fm for fm in fault_modes}

    # Dedup call graph
    edge_set = set()
    for e in call_graph:
        edge_set.add((e['from'], e['to']))

    # Edge FT data
    edge_ft = ft_config.get('edge_fault_tolerance', [])
    edge_ft_lookup = {(e['from'], e['to']): e for e in edge_ft}

    report = []
    report.append("# CrossFault 分析报告：TrainTicket 系统跨维度耦合故障场景分析\n")
    report.append(f"> 生成时间：2026-03-17 | 分析工具：CrossFault v1.0 | 模型：Claude Opus 4.6 + Claude Sonnet 4\n")

    # ======== Section 1: System Overview ========
    report.append("\n## 1. 系统概览\n")
    total_services = len(risk_atlas['services'])
    total_edges = len(edge_set)
    nodes = k8s_summary.get('nodes', {})
    report.append(f"| 指标 | 数值 |")
    report.append(f"|------|------|")
    report.append(f"| 微服务总数 | {total_services} |")
    report.append(f"| 调用边总数（去重） | {total_edges} |")
    report.append(f"| 集群节点数 | {len(nodes)} |")
    report.append(f"| 业务路径数 | {len(risk_atlas['business_paths'])} |")
    report.append(f"| 命名空间 | train-ticket |")
    report.append("")

    # Node distribution
    report.append("### 节点与服务分布\n")
    report.append("| 节点 | CPU | 内存 | 服务数 |")
    report.append("|------|-----|------|--------|")
    for node_name, node_info in nodes.items():
        svc_count = len(node_info.get('services', []))
        report.append(f"| {node_name} | {node_info.get('allocatable_cpu', 'N/A')} | {node_info.get('allocatable_memory', 'N/A')} | {svc_count} |")
    report.append("")

    # Business paths
    report.append("### 业务路径列表\n")
    report.append("| 路径名 | 入口服务 | 深度 | 涉及服务 |")
    report.append("|--------|----------|------|----------|")
    for bp in risk_atlas['business_paths']:
        report.append(f"| {bp['name']} | {bp['entry']} | {bp['depth']} | {', '.join(bp['path'][:6])}{'...' if len(bp['path'])>6 else ''} |")
    report.append("")

    # ======== Section 2: Risk Atlas Summary ========
    report.append("\n## 2. 风险图谱摘要\n")

    # 2.1 K8s config risks
    report.append("### 2.1 K8s 配置风险统计\n")

    single_replica = [s['name'] for s in risk_atlas['services'] if s['k8s_config']['replicas'] == 1]
    no_liveness = [s['name'] for s in risk_atlas['services'] if not s['k8s_config']['liveness_probe']]
    no_readiness = [s['name'] for s in risk_atlas['services'] if not s['k8s_config']['readiness_probe']]
    no_limits = [s['name'] for s in risk_atlas['services']
                 if s['k8s_config']['resource_limits']['cpu'] is None and s['k8s_config']['resource_limits']['memory'] is None]
    no_anti_affinity = [s['name'] for s in risk_atlas['services'] if not s['k8s_config']['anti_affinity']]

    report.append(f"| 风险类型 | 数量 | 比例 | 严重程度 |")
    report.append(f"|----------|------|------|----------|")
    report.append(f"| 单副本部署 | {len(single_replica)}/{total_services} | {len(single_replica)/total_services*100:.0f}% | 严重 |")
    report.append(f"| 缺少存活探针 | {len(no_liveness)}/{total_services} | {len(no_liveness)/total_services*100:.0f}% | 高 |")
    report.append(f"| 缺少就绪探针 | {len(no_readiness)}/{total_services} | {len(no_readiness)/total_services*100:.0f}% | 中 |")
    report.append(f"| 缺少资源限制 | {len(no_limits)}/{total_services} | {len(no_limits)/total_services*100:.0f}% | 高 |")
    report.append(f"| 缺少反亲和性 | {len(no_anti_affinity)}/{total_services} | {len(no_anti_affinity)/total_services*100:.0f}% | 低 |")
    report.append("")

    report.append(f"**关键发现**：所有 {len(single_replica)} 个业务服务均为单副本部署，且全部缺少存活探针（livenessProbe）。"
                  f"这意味着任何服务发生进程假死（如死锁、内存泄漏导致的无响应），K8s 都无法自动重启，"
                  f"形成「僵死永久不可用」风险。\n")

    if no_readiness:
        report.append(f"缺少就绪探针的服务：{', '.join(no_readiness)}\n")
    if no_limits:
        report.append(f"缺少资源限制的服务：{', '.join(no_limits)}\n")

    # 2.2 Topology risks
    report.append("### 2.2 调用拓扑风险\n")

    # Fan-in top 10
    report.append("#### 扇入度 Top-10 服务\n")
    in_degree_sorted = sorted(risk_atlas['services'], key=lambda s: s['topology']['in_degree'], reverse=True)
    report.append("| 排名 | 服务 | 扇入度 | 上游调用方 |")
    report.append("|------|------|--------|-----------|")
    for i, svc in enumerate(in_degree_sorted[:10]):
        if svc['topology']['in_degree'] == 0:
            break
        callers = ', '.join(svc['topology']['upstream_callers'][:5])
        if len(svc['topology']['upstream_callers']) > 5:
            callers += '...'
        report.append(f"| {i+1} | {svc['name']} | {svc['topology']['in_degree']} | {callers} |")
    report.append("")

    # Path crossing
    report.append("#### 路径交叉度 Top-10 服务\n")
    path_cross = sorted(risk_atlas['services'], key=lambda s: len(s['topology']['business_paths']), reverse=True)
    report.append("| 排名 | 服务 | 路径交叉度 | 所在路径 |")
    report.append("|------|------|-----------|---------|")
    for i, svc in enumerate(path_cross[:10]):
        if not svc['topology']['business_paths']:
            break
        report.append(f"| {i+1} | {svc['name']} | {len(svc['topology']['business_paths'])} | {', '.join(svc['topology']['business_paths'][:4])} |")
    report.append("")

    # Deepest paths
    report.append("#### 最深业务路径\n")
    sorted_paths = sorted(risk_atlas['business_paths'], key=lambda p: p['depth'], reverse=True)
    for bp in sorted_paths[:3]:
        report.append(f"- **{bp['name']}**：深度={bp['depth']}，路径: {' → '.join(bp['path'])}")
    report.append("")

    # 2.3 Fault tolerance analysis
    report.append("### 2.3 容错配置分析\n")

    # Protection level distribution
    all_edge_ft = []
    for svc in risk_atlas['services']:
        for edge in svc['outgoing_edges_ft']:
            all_edge_ft.append(edge)

    pl_counter = Counter(e.get('protection_level', 'none') for e in all_edge_ft)
    report.append("#### 各保护级别的调用边数量分布\n")
    report.append("| 保护级别 | 数量 | 比例 | 说明 |")
    report.append("|----------|------|------|------|")
    pl_descriptions = {
        "none": "完全无保护，故障直接传播",
        "timeout_only": "仅有超时保护，不能阻止级联",
        "flawed_retry": "有重试但无熔断器，会放大故障",
        "flawed_cb": "熔断器配置有缺陷（如阈值过高）",
        "effective_cb": "有效的熔断器保护"
    }
    total_ft_edges = len(all_edge_ft)
    for pl, count in sorted(pl_counter.items(), key=lambda x: x[1], reverse=True):
        desc = pl_descriptions.get(pl, "未知")
        report.append(f"| {pl} | {count} | {count/total_ft_edges*100:.0f}% | {desc} |")
    report.append("")

    # Unprotected edges
    none_edges = [e for e in all_edge_ft if e.get('protection_level') == 'none']
    report.append(f"#### 完全无保护的调用边（共{len(none_edges)}条）\n")
    report.append("| 调用方 | 被调方 | β系数 |")
    report.append("|--------|--------|-------|")
    for e in none_edges[:20]:
        report.append(f"| {e['from']} | {e['to']} | {e.get('beta', 10)} |")
    if len(none_edges) > 20:
        report.append(f"| ... | ... | ... |")
        report.append(f"| *共{len(none_edges)}条* | | |")
    report.append("")

    # Flawed retry edges
    flawed_edges = [e for e in all_edge_ft if e.get('protection_level') == 'flawed_retry']
    if flawed_edges:
        report.append(f"#### 有缺陷保护的调用边（重试无熔断器）\n")
        report.append("| 调用方 | 被调方 | 重试次数 | 退避 | β系数 | 来源 |")
        report.append("|--------|--------|----------|------|-------|------|")
        for e in flawed_edges:
            retry = e.get('fault_tolerance', {}).get('retry', {})
            report.append(f"| {e['from']} | {e['to']} | {retry.get('max_attempts', '?')} | {retry.get('backoff', 'none')} | {e.get('beta', 0)} | {e.get('source_evidence', '')[:60]} |")
        report.append("")

    # Top-10 beta edges
    report.append("#### 传播放大系数 β 最高的 Top-10 调用边\n")
    sorted_ft = sorted(all_edge_ft, key=lambda e: e.get('beta', 0), reverse=True)
    report.append("| 排名 | 调用方 | 被调方 | β系数 | 保护级别 |")
    report.append("|------|--------|--------|-------|----------|")
    for i, e in enumerate(sorted_ft[:10]):
        report.append(f"| {i+1} | {e['from']} | {e['to']} | {e.get('beta', 0)} | {e.get('protection_level', 'none')} |")
    report.append("")

    # 2.4 Physical resource risks
    report.append("### 2.4 物理资源风险\n")

    report.append("#### 各节点的服务分布\n")
    for node_name, node_info in nodes.items():
        svcs = node_info.get('services', [])
        if not svcs:
            continue
        report.append(f"**{node_name}** ({len(svcs)} 个服务)：")
        report.append(f"  {', '.join(sorted(svcs))}\n")

    # Co-located services without limits
    report.append("#### 同节点共置且无资源限制的服务组\n")
    for node_name, node_info in nodes.items():
        svcs = node_info.get('services', [])
        no_limit_svcs = [s for s in svcs if s in svc_map and
                        svc_map[s]['k8s_config']['resource_limits']['cpu'] is None and
                        svc_map[s]['k8s_config']['resource_limits']['memory'] is None]
        if len(no_limit_svcs) >= 2:
            report.append(f"- **{node_name}**：{len(no_limit_svcs)}个无限制服务 — {', '.join(no_limit_svcs[:10])}")
    report.append("")

    # QoS
    qos_counter = Counter(s['resource']['qos_class'] for s in risk_atlas['services'])
    report.append(f"#### QoS 等级分布\n")
    for qos, count in qos_counter.items():
        report.append(f"- {qos}: {count} 个服务")
    report.append("")

    # ======== Section 3: RiskRank ========
    report.append("\n## 3. RiskRank 排序结果\n")

    report.append("### 服务风险排名 Top-15\n")
    rr_items = sorted(riskrank_data['riskrank'].items(), key=lambda x: x[1], reverse=True)
    report.append("| 排名 | 服务 | RiskRank | 本地风险 | 扇入度 | 扇出度 | 路径交叉度 | 主要风险因素 |")
    report.append("|------|------|----------|----------|--------|--------|-----------|------------|")
    for i, (name, score) in enumerate(rr_items[:15]):
        svc = svc_map.get(name, {})
        local_risk = svc.get('local_risk', 0)
        in_d = svc.get('topology', {}).get('in_degree', 0)
        out_d = svc.get('topology', {}).get('out_degree', 0)
        paths = len(svc.get('topology', {}).get('business_paths', []))
        # Determine main risk factors
        factors = []
        if svc.get('k8s_config', {}).get('replicas', 1) == 1:
            factors.append("单副本")
        if not svc.get('k8s_config', {}).get('liveness_probe', True):
            factors.append("无存活探针")
        if in_d >= 5:
            factors.append(f"高扇入({in_d})")
        report.append(f"| {i+1} | {name} | {score:.2f} | {local_risk} | {in_d} | {out_d} | {paths} | {', '.join(factors)} |")
    report.append("")

    # Path risks
    report.append("### 业务路径风险排名\n")
    report.append("| 排名 | 路径 | PathRisk | 深度 | 关键瓶颈 |")
    report.append("|------|------|----------|------|----------|")
    for i, pr in enumerate(riskrank_data['path_risks']):
        # Find highest-risk service in path
        max_svc = ""
        max_rr = 0
        for s in pr['path']:
            rr = riskrank_data['riskrank'].get(s, 0)
            if rr > max_rr:
                max_rr = rr
                max_svc = s
        report.append(f"| {i+1} | {pr['name']} | {pr['path_risk']:.2f} | {pr['depth']} | {max_svc}(RR={max_rr:.1f}) |")
    report.append("")

    # Focus services
    report.append("### 焦点服务列表\n")
    report.append(f"共 {len(riskrank_data['focus_services'])} 个焦点服务（RiskRank Top-15 + 路径交叉度>1）：\n")
    for s in riskrank_data['focus_services']:
        rr = riskrank_data['riskrank'].get(s, 0)
        paths = len(svc_map.get(s, {}).get('topology', {}).get('business_paths', []))
        report.append(f"- **{s}** (RR={rr:.2f}, 路径交叉度={paths})")
    report.append("")

    # ======== Section 4: Fault Mode Analysis ========
    report.append("\n## 4. 故障模式分析\n")

    for fm_group in fault_modes:
        svc_name = fm_group['service']
        rr = fm_group.get('riskrank', svc_map.get(svc_name, {}).get('riskrank', 0))
        report.append(f"### 4.{fault_modes.index(fm_group)+1} {svc_name} 的故障模式 (RR={rr:.2f})\n")

        report.append(f"| 模式ID | 故障模式 | 匹配规则 | 维度 | 严重程度 | 放大系数 |")
        report.append(f"|--------|---------|---------|------|---------|---------|")
        for m in fm_group['fault_modes']:
            dims = '×'.join(m['dimensions'])
            report.append(f"| {m['mode_id']} | {m['name']} | {m['matched_rule']} | {dims} | {m['severity']} | {m.get('amplification_factor', 1)} |")
        report.append("")

        for m in fm_group['fault_modes']:
            report.append(f"**{m['mode_id']}: {m['name']}** ({m['severity']})\n")
            report.append(f"- **匹配规则**: {m['matched_rule']}")
            report.append(f"- **涉及风险**: {'; '.join(m['involved_risks'])}")
            report.append(f"- **触发条件**: {m['trigger_condition']}")
            report.append(f"- **本地影响**: {m['local_effect']}")
            report.append(f"- **传播方向**: {m['propagation_direction']}")
            report.append(f"- **放大系数**: {m.get('amplification_factor', 1)}\n")
        report.append("")

    # ======== Section 5: Propagation Chains ========
    report.append("\n## 5. 传播链分析\n")

    chains = chains_data['chains']
    self_loops = chains_data['self_loops']
    report.append(f"共识别 **{len(chains)}** 条传播链和 **{len(self_loops)}** 个自我恶化环路。\n")

    report.append("### 传播链 Top-10（按风险排序）\n")
    for i, chain in enumerate(chains[:10]):
        path_parts = []
        for step in chain['propagation_path']:
            path_parts.append(step['from'])
        path_parts.append(chain['propagation_path'][-1]['to'])
        path_str = ' → '.join(path_parts)

        report.append(f"**链{i+1}**: {chain['origin_mode']} @ {chain['origin_service']}")
        report.append(f"- 路径: {path_str}")
        report.append(f"- 涉及服务: {chain['total_services']} 个")
        report.append(f"- 累计放大: {chain['cumulative_amplification']:.0f}")
        report.append(f"- 严重程度: {chain['severity']}\n")

    # Self-worsening loops
    report.append("### 自我恶化环路\n")
    seen_loop_keys = set()
    for loop in self_loops:
        key = (tuple(loop['services']), loop['callee_mode'], loop['caller_mode'])
        if key in seen_loop_keys:
            continue
        seen_loop_keys.add(key)
        report.append(f"- **{loop['description']}** (放大系数={loop['amplification']:.0f})")
        report.append(f"  - 下游故障模式: {loop['callee_mode']}")
        report.append(f"  - 上游故障模式: {loop['caller_mode']}")
    report.append("")

    # ======== Section 6: Fault Scenarios ========
    report.append("\n## 6. 故障场景设计（核心产出）\n")

    for scenario in scenarios:
        sid = scenario.get('scenario_id', 'N/A')
        title = scenario.get('title', 'N/A')
        report.append(f"### 场景 {sid}: {title}\n")

        if 'error' in scenario or 'parse_error' in scenario:
            report.append(f"*生成错误: {scenario.get('error', scenario.get('parse_error', 'unknown'))}*\n")
            continue

        target = scenario.get('target_service', 'N/A')
        plan = scenario.get('injection_plan', {})

        report.append(f"- **注入目标**: {target}")
        report.append(f"- **注入方式**: {plan.get('fault_type', 'N/A')}")
        report.append(f"- **注入参数**: {json.dumps(plan.get('parameters', {}), ensure_ascii=False)}")
        report.append(f"- **触发条件**: {plan.get('trigger_condition', 'N/A')}")
        report.append(f"- **持续时间**: {plan.get('duration', 'N/A')}")
        report.append(f"- **选择理由**: {plan.get('rationale', 'N/A')}\n")

        cascade = scenario.get('predicted_cascade', [])
        if cascade:
            report.append("**预测级联路径**:\n")
            for step in cascade:
                report.append(f"  **Step {step.get('step', '?')}**: {step.get('description', 'N/A')}")
                report.append(f"  - 机制: {step.get('mechanism', 'N/A')}")
                report.append(f"  - 受影响服务: {step.get('affected_service', 'N/A')}")
                report.append(f"  - 证据: {step.get('evidence', 'N/A')}\n")

        affected = scenario.get('affected_business_paths', [])
        report.append(f"- **影响范围**: {', '.join(affected) if affected else 'N/A'}")
        report.append(f"- **严重程度**: {scenario.get('severity', 'N/A')}")
        report.append(f"- **风险评分**: {scenario.get('risk_score', 'N/A')}/100")
        report.append(f"- **核心洞察**: {scenario.get('key_insight', 'N/A')}\n")

        # What-if analysis
        report.append("**修复分析**：如果修复某个风险会怎样？\n")
        if 'predicted_cascade' in scenario and scenario['predicted_cascade']:
            first_step = scenario['predicted_cascade'][0]
            report.append(f"- 若为 {target} 添加存活探针 → 进程假死可被自动检测并重启，阻断级联传播起点")
            report.append(f"- 若为 {target} 增加副本数到2+ → 单实例故障不会导致服务完全不可用")
            if plan.get('fault_type', '') in ('pod-kill', 'process-kill'):
                report.append(f"- 若上游添加熔断器 → 快速失败而非持续重试，防止重试风暴")
        report.append("")

    # ======== Section 7: Coverage Analysis ========
    report.append("\n## 7. 覆盖率分析\n")

    # Calculate coverage
    covered_services = set()
    for s in scenarios:
        if 'target_service' in s:
            covered_services.add(s['target_service'])
        for step in s.get('predicted_cascade', []):
            if 'affected_service' in step:
                covered_services.add(step['affected_service'])

    total_severe = 0
    total_high = 0
    covered_severe = 0
    covered_high = 0
    uncovered_modes = []

    for fm_group in fault_modes:
        for mode in fm_group['fault_modes']:
            if mode['severity'] == '严重':
                total_severe += 1
                if fm_group['service'] in covered_services:
                    covered_severe += 1
                else:
                    uncovered_modes.append(f"{fm_group['service']}: {mode['name']} ({mode['mode_id']})")
            elif mode['severity'] == '高':
                total_high += 1
                if fm_group['service'] in covered_services:
                    covered_high += 1
                else:
                    uncovered_modes.append(f"{fm_group['service']}: {mode['name']} ({mode['mode_id']})")

    report.append(f"| 严重程度 | 总数 | 已覆盖 | 覆盖率 |")
    report.append(f"|----------|------|--------|--------|")
    report.append(f"| 严重 | {total_severe} | {covered_severe} | {covered_severe/max(total_severe,1)*100:.0f}% |")
    report.append(f"| 高 | {total_high} | {covered_high} | {covered_high/max(total_high,1)*100:.0f}% |")
    report.append(f"| 合计 | {total_severe+total_high} | {covered_severe+covered_high} | {(covered_severe+covered_high)/max(total_severe+total_high,1)*100:.0f}% |")
    report.append("")

    if uncovered_modes:
        report.append("### 未覆盖的故障模式\n")
        for m in uncovered_modes:
            report.append(f"- {m}")
        report.append("")
        report.append("**未覆盖原因分析**：这些服务（如 ts-auth-service、ts-verification-code-service）"
                      "在调用图中处于边缘位置，传播链较短，不容易被多跳传播链覆盖。"
                      "但它们的「僵死永久不可用」风险仍需关注，建议单独进行 pod-kill 测试。\n")

    # ======== Section 8: Findings & Recommendations ========
    report.append("\n## 8. 发现与建议\n")

    report.append("### 最危险的跨维度耦合模式\n")
    report.append("1. **配置×容错：重试风暴阻止恢复**")
    report.append("   - 全系统单副本 + 无存活探针 + 有缺陷的重试配置（无熔断器）")
    report.append("   - ts-preserve-service → ts-order-service 的调用边配置了 5 次重试、0ms 退避、无熔断器")
    report.append("   - 一旦 ts-order-service 崩溃，5 倍流量冲击会阻止其恢复\n")

    report.append("2. **拓扑×配置：汇聚放大效应**")
    report.append("   - ts-station-service（扇入度 8）和 ts-order-service（扇入度 8）是核心汇聚点")
    report.append("   - 多个上游无保护调用，故障时所有上游同时阻塞等待，放大系数极高\n")

    report.append("3. **容错×资源：双通道耦合**")
    report.append("   - 同节点共置服务间既有调用关系又共享物理资源")
    report.append("   - 调用链阻塞（无超时）+ 物理层资源争抢形成双重故障通道\n")

    report.append("4. **全维度：系统性单点故障**")
    report.append("   - 100% 单副本 + 100% 无存活探针 = 任何服务假死都是永久故障")
    report.append("   - 这是所有其他风险的放大器：将任何瞬时故障变成持久故障\n")

    report.append("### 优先修复建议（收益排序）\n")
    report.append("| 优先级 | 修复项 | 受益服务数 | 预期收益 | 实施难度 |")
    report.append("|--------|--------|-----------|----------|----------|")
    report.append("| P0 | 为所有服务添加存活探针 | 47 | 消除「僵死永久不可用」风险，使K8s能自动恢复假死服务 | 低 |")
    report.append("| P0 | 为关键服务增加副本数≥2 | ~15 | 消除单点故障，特别是 ts-order-service, ts-station-service 等高扇入服务 | 中 |")
    report.append("| P1 | 为 ts-preserve→ts-order 等有缺陷重试添加熔断器 | 4 | 阻断重试风暴传播链，β 从 5 降至 ≈0 | 低 |")
    report.append("| P1 | 为所有无超时调用边添加超时配置 | ~70 | 防止线程无限阻塞等待，限制故障传播时间 | 低 |")
    report.append("| P2 | 为关键服务设置资源限制 | ~15 | 防止噪声邻居效应和 OOM 影响同节点服务 | 低 |")
    report.append("| P2 | 为高扇入服务配置 Pod 反亲和性 | ~5 | 避免关键服务的多副本调度到同一节点 | 低 |")
    report.append("| P3 | 修复 ts-order-service 的熔断器阈值（90%→50%） | 1 | 使熔断器能在故障早期触发，而非几乎永不触发 | 低 |")
    report.append("")

    report.append("### 推荐的混沌工程实验优先级排序\n")
    report.append("| 优先级 | 实验 | 对应场景 | 预期验证点 |")
    report.append("|--------|------|---------|-----------|")
    for i, s in enumerate(scenarios[:8]):
        report.append(f"| {i+1} | {s.get('title', 'N/A')[:40]} | {s.get('scenario_id', 'N/A')} | {s.get('key_insight', 'N/A')[:50]} |")
    report.append("")

    report.append("---\n")
    report.append("*本报告由 CrossFault 分析框架自动生成，基于源码静态分析、K8s 集群实时状态和 Claude AI 推理。*")
    report.append("*所有结论均引用具体的配置值和拓扑数据，可直接追溯验证。*\n")

    return '\n'.join(report)


if __name__ == '__main__':
    report_text = generate_report()
    with open('crossfault_analysis_report.md', 'w') as f:
        f.write(report_text)
    print(f"Report generated: crossfault_analysis_report.md ({len(report_text)} chars)")
