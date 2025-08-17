#

import os
import sys
import json
import time
from pathlib import Path

# Add the parent directory to the path so we can import from ck_pro
sys.path.append(str(Path(__file__).parent.parent.parent))

from ..promtool.agent import Prom_ToolAgent
from ..base.session import AgentSession


def run_complete_prometheus_workflow():
    """运行完整的Prometheus工作流程，便于debug测试"""
    
    print("🚀 === 开始完整的Prometheus Agent工作流程测试 ===\n")
    
    try:
        # 步骤1: 创建agent实例
        print("📋 步骤1: 创建Prometheus Agent实例")
        agent = Prom_ToolAgent()
        print(f"   ✅ Agent创建成功")
        print(f"   📝 名称: {agent.name}")
        print(f"   📝 描述: {agent.description}")
        print(f"   📝 最大步骤数: {agent.max_steps}")
        print(f"   📝 可用函数: {list(agent.ACTIVE_FUNCTIONS.keys())}")
        
        # 步骤2: 创建测试会话
        print("\n📋 步骤2: 创建测试会话")
        session = AgentSession(
            id="debug_session_001",
            task="抓取过去1小时的CPU使用率指标，分析趋势，并返回分析结果",
            info={
                "target_prometheus_metrics": "cpu_usage_percent",
                "time_range": "1小时",
                "analysis_type": "趋势分析"
            }
        )
        print(f"   ✅ 会话创建成功")
        print(f"   📝 会话ID: {session.id}")
        print(f"   📝 任务: {session.task}")
        
        # 步骤3: 初始化运行
        print("\n📋 步骤3: 初始化agent运行")
        agent.init_run(session)
        print(f"   ✅ Agent运行初始化成功")
        print(f"   📝 Prometheus环境已创建")
        
        # 步骤4: 模拟完整的工作流程
        print("\n📋 步骤4: 执行完整工作流程")
        
        # 4.1 抓取数据步骤
        print("   🔍 4.1 抓取Prometheus数据")
        fetch_result = agent._fetch_prometheus_data(
            query="cpu_usage_percent",
            start_time="2024-01-01T00:00:00Z",
            end_time="2024-01-01T01:00:00Z",
            step="1m",
            output_path="./debug_cpu_data.json"
        )
        print(f"      ✅ 抓取完成")
        print(f"      📊 动作: {fetch_result.action}")
        print(f"      📊 结果: {fetch_result.result}")
        
        # 4.2 分析数据步骤
        print("   📈 4.2 分析Prometheus数据")
        analyze_result = agent._analyze_prometheus_data(
            data=fetch_result.data,  # 直接使用抓取的数据
            analysis_type="trend_analysis"
        )
        print(f"      ✅ 分析完成")
        print(f"      📊 动作: {analyze_result.action}")
        print(f"      📊 结果: {analyze_result.result}")
        if hasattr(analyze_result, 'natural_language_result'):
            print(f"      📊 自然语言解读: {analyze_result.natural_language_result[:100]}...")
        
        # 4.3 完成任务步骤
        print("   ✅ 4.3 完成任务")
        stop_result = agent._my_stop(
            answer="CPU使用率在过去1小时内平均为45%，呈上升趋势，峰值出现在第45分钟",
            summary="成功抓取并分析了CPU使用率指标，发现系统负载呈上升趋势"
        )
        print(f"      ✅ 任务完成")
        print(f"      📊 动作: {stop_result.action}")
        print(f"      📊 结果: {stop_result.result}")
        
        # 步骤5: 测试步骤准备和调用
        print("\n📋 步骤5: 测试步骤准备和调用")
        
        # 5.1 准备步骤
        print("   🔧 5.1 准备步骤")
        state = {
            "completed_list": ["抓取CPU指标", "分析趋势"],
            "todo_list": ["生成报告"],
            "experience": ["数据抓取成功", "分析完成"],
            "information": ["CPU使用率平均45%", "呈上升趋势", "峰值在第45分钟"]
        }
        
        input_kwargs, extra_kwargs = agent.step_prepare(session, state)
        print(f"      ✅ 步骤准备成功")
        print(f"      📊 输入参数数量: {len(input_kwargs)}")
        print(f"      📊 额外参数数量: {len(extra_kwargs)}")
        
        # 5.2 步骤调用
        print("   🔧 5.2 步骤调用")
        messages = [
            {"role": "user", "content": "请总结CPU使用率的分析结果"}
        ]
        response = agent.step_call(messages, session)
        print(f"      ✅ 步骤调用成功")
        print(f"      📊 响应长度: {len(response) if response else 0}")
        if response:
            print(f"      📊 响应内容: {response[:200]}...")
        
        # 步骤6: 测试动作执行
        print("\n📋 步骤6: 测试动作执行")
        
        # 6.1 准备动作输入
        print("   🔧 6.1 准备动作输入")
        action_res = {
            "thought": "需要生成CPU使用率分析报告",
            "code": "print('生成CPU使用率分析报告')"
        }
        action_input_kwargs = {
            "task": session.task,
            "state": json.dumps(state),
            "recent_steps_str": "抓取数据 -> 分析数据 -> 生成报告"
        }
        
        # 6.2 执行动作
        print("   🔧 6.2 执行动作")
        prom_env = agent.prom_envs[session.id]
        action_result = agent.step_action(action_res, action_input_kwargs, prom_env=prom_env)
        print(f"      ✅ 动作执行成功")
        print(f"      📊 结果: {action_result}")
        
        # 步骤7: 获取最终结果
        print("\n📋 步骤7: 获取最终结果")
        final_result = agent.get_final_result()
        if final_result:
            print(f"   ✅ 最终结果: {final_result}")
        else:
            print("   ℹ️  无最终结果（这是正常的，因为我们只是测试）")
        
        # 步骤8: 结束运行
        print("\n📋 步骤8: 结束agent运行")
        agent.end_run(session)
        print(f"   ✅ Agent运行结束成功")
        print(f"   📝 Prometheus环境已清理")
        
        # 步骤9: 验证结果
        print("\n📋 步骤9: 验证测试结果")
        
        # 检查生成的文件
        if os.path.exists("./debug_cpu_data.json"):
            print("   ✅ 数据文件生成成功")
            file_size = os.path.getsize("./debug_cpu_data.json")
            print(f"      📊 文件大小: {file_size} bytes")
        else:
            print("   ⚠️  数据文件未生成")
        
        # 检查会话状态
        print(f"   📊 会话状态: {session.to_dict()}")
        
        print("\n🎉 === 完整工作流程测试完成！===")
        print("💡 提示：所有步骤都已成功执行，可以进行详细的debug分析")
        
        return True
        
    except Exception as e:
        print(f"\n❌ === 工作流程测试失败 ===")
        print(f"错误信息: {e}")
        import traceback
        print("详细错误堆栈:")
        traceback.print_exc()
        return False


def test_agent_functions():
    """测试agent的各个功能函数"""
    
    print("\n🔧 === 测试Agent功能函数 ===")
    
    try:
        agent = Prom_ToolAgent()
        
        # 测试函数定义
        print("\n📋 测试函数定义")
        short_def = agent.get_function_definition(short=True)
        print(f"   ✅ 简短定义: {short_def}")
        
        full_def = agent.get_function_definition(short=False)
        print(f"   ✅ 完整定义: {full_def[:200]}...")
        
        # 测试各个功能函数
        print("\n📋 测试功能函数")
        
        # 测试抓取函数
        fetch_result = agent._fetch_prometheus_data(
            query="memory_usage_bytes",
            start_time="2024-01-01T00:00:00Z",
            end_time="2024-01-01T00:30:00Z",
            step="5m"
        )
        print(f"   ✅ 抓取函数: {fetch_result.result}")
        
        # 测试分析函数
        analyze_result = agent._analyze_prometheus_data(
            data=None,  # 测试无数据情况
            analysis_type="general"
        )
        print(f"   ✅ 分析函数: {analyze_result.result}")
        if hasattr(analyze_result, 'natural_language_result'):
            print(f"      📊 自然语言解读: {analyze_result.natural_language_result[:100]}...")
        
        # 测试停止函数
        stop_result = agent._my_stop(
            answer="内存使用率分析完成",
            summary="成功分析了内存使用情况"
        )
        print(f"   ✅ 停止函数: {stop_result.result}")
        
        print("   🎉 所有功能函数测试通过")
        return True
        
    except Exception as e:
        print(f"   ❌ 功能函数测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_environment_configuration():
    """测试环境配置"""
    
    print("\n⚙️ === 测试环境配置 ===")
    
    try:
        # 测试环境变量
        print("\n📋 环境变量配置")
        prom_ip = os.getenv("PROM_IP", "localhost:9090")
        print(f"   📊 PROM_IP: {prom_ip}")
        
        openai_key = os.getenv("OPENAI_API_KEY", "未设置")
        print(f"   📊 OPENAI_API_KEY: {'已设置' if openai_key != '未设置' else '未设置'}")
        
        # 测试PromEnv创建
        print("\n📋 PromEnv测试")
        from ck_pro.prom_tool.utils import PromEnv
        prom_env = PromEnv(starting=False)
        print(f"   ✅ PromEnv创建成功")
        print(f"   📊 目标URL: {prom_env.get_target_url()}")
        
        # 测试状态获取
        status = prom_env.get_status()
        print(f"   📊 连接状态: {status['status']}")
        print(f"   📊 可用指标数量: {len(status['available_metrics'])}")
        
        print("   🎉 环境配置测试通过")
        return True
        
    except Exception as e:
        print(f"   ❌ 环境配置测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_files():
    """清理测试生成的文件"""
    
    print("\n🧹 === 清理测试文件 ===")
    
    test_files = [
        "./debug_cpu_data.json",
        "./test_memory_data.json",
        "./test_data.json"
    ]
    
    for file_path in test_files:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"   ✅ 已删除: {file_path}")
            except Exception as e:
                print(f"   ⚠️  删除失败: {file_path} - {e}")
        else:
            print(f"   ℹ️  文件不存在: {file_path}")


if __name__ == "__main__":
    print("🚀 Prometheus Agent 完整流程测试开始")
    print("=" * 60)
    
    # 记录开始时间
    start_time = time.time()
    
    # 运行测试
    test_results = []
    
    # 1. 完整工作流程测试
    print("\n" + "="*60)
    workflow_success = run_complete_prometheus_workflow()
    test_results.append(("完整工作流程", workflow_success))
    
    # 2. 功能函数测试
    print("\n" + "="*60)
    functions_success = test_agent_functions()
    test_results.append(("功能函数", functions_success))
    
    # 3. 环境配置测试
    print("\n" + "="*60)
    config_success = test_environment_configuration()
    test_results.append(("环境配置", config_success))
    
    # 4. 清理测试文件
    print("\n" + "="*60)
    cleanup_test_files()
    
    # 5. 测试结果总结
    print("\n" + "="*60)
    print("📊 === 测试结果总结 ===")
    
    total_tests = len(test_results)
    passed_tests = sum(1 for _, success in test_results if success)
    failed_tests = total_tests - passed_tests
    
    for test_name, success in test_results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    print(f"\n📈 总体结果: {passed_tests}/{total_tests} 测试通过")
    
    if failed_tests == 0:
        print("🎉 所有测试都通过了！系统运行正常。")
    else:
        print(f"⚠️  有 {failed_tests} 个测试失败，请检查相关功能。")
    
    # 记录总耗时
    total_time = time.time() - start_time
    print(f"\n⏱️  总耗时: {total_time:.2f} 秒")
    
    print("\n💡 Debug提示:")
    print("   - 如果测试失败，请查看详细的错误信息")
    print("   - 检查环境变量配置是否正确")
    print("   - 确认Prometheus服务是否可访问")
    print("   - 验证API密钥是否有效")
    
    print("\n🎯 测试完成！可以进行详细的debug分析了。")
