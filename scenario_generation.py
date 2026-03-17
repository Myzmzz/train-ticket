#!/usr/bin/env python3
"""
CrossFault Phase 3.2 & 3.3: Scenario Generation via Claude API
"""

import json
import os
import anthropic

# API Configuration
os.environ["ANTHROPIC_BASE_URL"] = "https://hkapi.huakai123.com"
os.environ["ANTHROPIC_AUTH_TOKEN"] = "sk-6da485a705f09a294a4eca0c13cdb7fb1d95c57d2272126fcbff5ed79f5a269b"


def load_analysis_data():
    with open('risk_atlas.json') as f:
        risk_atlas = json.load(f)
    with open('fault_modes.json') as f:
        fault_modes = json.load(f)
    with open('propagation_chains.json') as f:
        chains_data = json.load(f)
    with open('riskrank_results.json') as f:
        riskrank = json.load(f)
    return risk_atlas, fault_modes, chains_data, riskrank


def select_diverse_chains(chains_data, fault_modes, n=8):
    """Select diverse propagation chains for scenario generation."""
    chains = chains_data['chains']
    self_loops = chains_data['self_loops']

    # Prioritize chains that cover different origin services and fault modes
    selected = []
    seen_origins = set()
    seen_modes = set()

    for chain in chains:
        origin = chain['origin_service']
        mode = chain['origin_mode']
        key = (origin, mode)
        if key not in seen_modes:
            selected.append(chain)
            seen_origins.add(origin)
            seen_modes.add(key)
            if len(selected) >= n:
                break

    # If we have room, add some self-worsening loops
    if len(selected) < n and self_loops:
        # Deduplicate loops
        seen_loop = set()
        for loop in self_loops:
            key = tuple(loop['services'])
            if key not in seen_loop and len(selected) < n:
                seen_loop.add(key)
                # Convert loop to chain-like format for the API
                selected.append({
                    "type": "self_loop",
                    "origin_service": loop['services'][0],
                    "origin_mode": loop['callee_mode'],
                    "loop_info": loop,
                    "total_services": len(loop['services']),
                    "cumulative_amplification": loop['amplification']
                })

    return selected[:n]


def get_service_risk_data(risk_atlas, service_name):
    """Get complete risk data for a service."""
    for svc in risk_atlas['services']:
        if svc['name'] == service_name:
            return svc
    return None


def call_claude_for_scenario(client, chain, risk_atlas, fault_modes, scenario_id):
    """Call Claude API to generate a fault scenario for a propagation chain."""
    # Gather involved services
    involved_services = set()
    if 'propagation_path' in chain:
        for step in chain['propagation_path']:
            involved_services.add(step['from'])
            involved_services.add(step['to'])
    involved_services.add(chain['origin_service'])

    # Get risk data for involved services
    services_data = {}
    for svc_name in involved_services:
        data = get_service_risk_data(risk_atlas, svc_name)
        if data:
            # Slim down for API
            services_data[svc_name] = {
                "k8s_config": data['k8s_config'],
                "topology": {
                    "in_degree": data['topology']['in_degree'],
                    "out_degree": data['topology']['out_degree'],
                    "upstream_callers": data['topology']['upstream_callers'],
                    "downstream_callees": data['topology']['downstream_callees'],
                    "business_paths": data['topology']['business_paths']
                },
                "resource": data['resource'],
                "riskrank": data.get('riskrank', 0),
                "local_risk": data.get('local_risk', 0)
            }

    # Get fault modes for involved services
    involved_modes = {}
    for fm in fault_modes:
        if fm['service'] in involved_services:
            involved_modes[fm['service']] = fm['fault_modes']

    # Get call graph edges between involved services
    call_edges = []
    for svc in risk_atlas['services']:
        if svc['name'] in involved_services:
            for edge in svc['outgoing_edges_ft']:
                if edge['to'] in involved_services:
                    call_edges.append({
                        "from": edge['from'],
                        "to": edge['to'],
                        "protection_level": edge.get('protection_level', 'none'),
                        "beta": edge.get('beta', 10),
                        "fault_tolerance": edge.get('fault_tolerance', {}),
                        "source_evidence": edge.get('source_evidence', '')
                    })

    chain_json = json.dumps(chain, ensure_ascii=False, indent=2)
    services_json = json.dumps(services_data, ensure_ascii=False, indent=2)
    modes_json = json.dumps(involved_modes, ensure_ascii=False, indent=2)
    edges_json = json.dumps(call_edges, ensure_ascii=False, indent=2)

    prompt = f"""请基于以下信息设计故障注入场景：

## 传播链信息
{chain_json}

## 涉及服务的完整风险数据
{services_json}

## 涉及服务的故障模式
{modes_json}

## 调用边详情（含容错配置）
{edges_json}

请输出以下格式的JSON（直接输出JSON，不要markdown代码块）：
{{
  "scenario_id": "{scenario_id}",
  "title": "场景标题",
  "target_service": "注入目标服务",
  "injection_plan": {{
    "fault_type": "pod-kill / network-delay / cpu-stress / memory-stress / ...",
    "parameters": {{}},
    "trigger_condition": "高负载期间 / 滚动更新期间 / 随时",
    "duration": "30s",
    "rationale": "为什么选择这种注入方式而非其他"
  }},
  "predicted_cascade": [
    {{
      "step": 1,
      "description": "具体发生什么",
      "mechanism": "基于什么风险数据推导的",
      "affected_service": "哪个服务受影响",
      "evidence": "引用具体的配置值/拓扑数据"
    }}
  ],
  "affected_business_paths": ["购票流程"],
  "severity": "严重/高/中/低",
  "risk_score": 85,
  "key_insight": "这个场景揭示了什么跨维度耦合问题"
}}"""

    system_prompt = """你是一个微服务系统韧性分析专家。你的任务是基于提供的服务风险数据和传播链信息，
设计具体的故障注入场景。你需要：
1. 分析传播链中每一步的具体机制
2. 判断最有效的注入方式（什么类型的故障、什么参数、什么条件下注入）
3. 预测完整的级联路径（每一步引用具体的风险数据）
4. 评估场景的严重程度和影响范围
请用中文回答，输出JSON格式。"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.content[0].text
        # Try to parse JSON
        # Remove markdown code blocks if present
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0]
        elif '```' in content:
            content = content.split('```')[1].split('```')[0]
        return json.loads(content.strip())
    except json.JSONDecodeError as e:
        print(f"  Warning: Failed to parse JSON for {scenario_id}: {e}")
        print(f"  Raw content: {content[:500]}")
        return {"scenario_id": scenario_id, "raw_response": content, "parse_error": str(e)}
    except Exception as e:
        print(f"  Error calling API for {scenario_id}: {e}")
        return {"scenario_id": scenario_id, "error": str(e)}


def check_coverage(fault_modes, scenarios):
    """Check which severe/high fault modes are covered by scenarios."""
    # Collect all service+mode combos from scenarios
    covered_services = set()
    for s in scenarios:
        if 'target_service' in s:
            covered_services.add(s['target_service'])
        if 'predicted_cascade' in s:
            for step in s['predicted_cascade']:
                if 'affected_service' in step:
                    covered_services.add(step['affected_service'])

    uncovered = []
    for fm_group in fault_modes:
        for mode in fm_group['fault_modes']:
            if mode['severity'] in ('严重', '高'):
                if fm_group['service'] not in covered_services:
                    uncovered.append({
                        "service": fm_group['service'],
                        "mode": mode['name'],
                        "mode_id": mode['mode_id'],
                        "severity": mode['severity'],
                        "rule": mode['matched_rule']
                    })
    return uncovered


def main():
    print("=" * 60)
    print("Phase 3.2: Scenario Generation via Claude API")
    print("=" * 60)

    risk_atlas, fault_modes, chains_data, riskrank = load_analysis_data()

    # Initialize client
    client = anthropic.Anthropic(
        base_url="https://hkapi.huakai123.com",
        api_key="sk-6da485a705f09a294a4eca0c13cdb7fb1d95c57d2272126fcbff5ed79f5a269b"
    )

    # Select diverse chains
    selected_chains = select_diverse_chains(chains_data, fault_modes, n=8)
    print(f"\nSelected {len(selected_chains)} chains for scenario generation:")
    for i, chain in enumerate(selected_chains):
        print(f"  {i+1}. {chain['origin_service']}: {chain['origin_mode']} (amp={chain.get('cumulative_amplification', 0):.0f})")

    # Generate scenarios
    scenarios = []
    for i, chain in enumerate(selected_chains):
        scenario_id = f"SCN-{i+1:03d}"
        print(f"\n[{scenario_id}] Generating scenario for {chain['origin_service']}: {chain['origin_mode']}...")
        scenario = call_claude_for_scenario(client, chain, risk_atlas, fault_modes, scenario_id)
        scenarios.append(scenario)
        print(f"  → {scenario.get('title', 'N/A')} (severity={scenario.get('severity', 'N/A')})")

    # Phase 3.3: Coverage check
    print("\n" + "=" * 60)
    print("Phase 3.3: Coverage Analysis")
    print("=" * 60)
    uncovered = check_coverage(fault_modes, scenarios)
    print(f"Uncovered severe/high fault modes: {len(uncovered)}")
    for u in uncovered[:10]:
        print(f"  {u['service']}: {u['mode']} ({u['severity']}, {u['rule']})")

    # Generate supplementary scenarios for uncovered modes
    if uncovered:
        print(f"\nGenerating supplementary scenario for uncovered modes...")
        uncovered_summary = json.dumps(uncovered[:10], ensure_ascii=False, indent=2)

        # Group uncovered by service to find interesting combinations
        uncovered_services = set(u['service'] for u in uncovered[:10])
        extra_services_data = {}
        for svc_name in uncovered_services:
            data = get_service_risk_data(risk_atlas, svc_name)
            if data:
                extra_services_data[svc_name] = {
                    "k8s_config": data['k8s_config'],
                    "topology": {
                        "in_degree": data['topology']['in_degree'],
                        "out_degree": data['topology']['out_degree'],
                        "business_paths": data['topology']['business_paths']
                    },
                    "resource": data['resource'],
                    "riskrank": data.get('riskrank', 0)
                }

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                temperature=0,
                system="""你是一个微服务系统韧性分析专家。以下故障模式尚未被现有场景覆盖，请设计1-2个场景覆盖它们。用中文回答，输出JSON数组。""",
                messages=[{
                    "role": "user",
                    "content": f"""以下严重/高级别故障模式尚未被现有场景覆盖：

{uncovered_summary}

涉及服务的风险数据：
{json.dumps(extra_services_data, ensure_ascii=False, indent=2)}

请输出JSON数组，每个元素格式同之前的场景格式，scenario_id从SCN-{len(scenarios)+1:03d}开始。直接输出JSON，不要markdown代码块。"""
                }]
            )
            content = response.content[0].text
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            extra_scenarios = json.loads(content.strip())
            if isinstance(extra_scenarios, dict):
                extra_scenarios = [extra_scenarios]
            scenarios.extend(extra_scenarios)
            print(f"  Generated {len(extra_scenarios)} supplementary scenarios")
        except Exception as e:
            print(f"  Error generating supplementary scenarios: {e}")

    # Save all scenarios
    with open('scenarios.json', 'w') as f:
        json.dump(scenarios, f, indent=2, ensure_ascii=False)
    print(f"\nTotal scenarios: {len(scenarios)}")
    print("Saved to scenarios.json")


if __name__ == '__main__':
    main()
