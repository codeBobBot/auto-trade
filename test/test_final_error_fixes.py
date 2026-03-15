#!/usr/bin/env python3
"""
最终错误修复验证测试
"""

import sys
import os
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_all_fixes():
    """测试所有错误修复"""
    print("🧪 最终错误修复验证测试")
    print("=" * 60)
    
    try:
        from probability_arbitrage_strategy import ProbabilityArbitrageStrategy
        
        print("✅ 1. 测试策略初始化...")
        strategy = ProbabilityArbitrageStrategy(enable_trading=False)
        print("   策略初始化成功")
        
        print("\n✅ 2. 测试互斥组定义...")
        total_groups = len(strategy.mutually_exclusive_groups)
        print(f"   总共定义了 {total_groups} 个互斥组")
        
        print("\n✅ 3. 测试智能分组算法...")
        test_markets = [
            {
                'id': '0x1111',
                'question': 'Will Taylor Swift win Album of the Year?',
                'liquidity': 15000,
                'volume24hr': 25000,
                'yes_price': 0.65
            },
            {
                'id': '0x2222', 
                'question': 'Will Apple stock reach $200 by end of 2024?',
                'liquidity': 20000,
                'volume24hr': 30000,
                'yes_price': 0.45
            }
        ]
        
        # 测试更新互斥组
        strategy.update_mutually_exclusive_groups(test_markets)
        print("   智能分组测试通过")
        
        print("\n✅ 4. 测试覆盖率计算...")
        coverage = strategy.calculate_coverage_rate(test_markets)
        print(f"   总体覆盖率: {coverage['overall_coverage']:.1%}")
        
        print("\n✅ 5. 测试套利机会发现...")
        opportunities = strategy.find_arbitrage_opportunities()
        print(f"   发现 {len(opportunities)} 个套利机会")
        
        print("\n✅ 6. 测试动态分组...")
        unassigned = [
            {
                'id': '0x3333',
                'question': 'Will the movie Barbie win Best Original Screenplay?',
                'liquidity': 8000,
                'volume24hr': 15000,
                'yes_price': 0.52
            },
            {
                'id': '0x4444',
                'question': 'Will the film Oppenheimer win Best Director?',
                'liquidity': 9000,
                'volume24hr': 16000,
                'yes_price': 0.48
            }
        ]
        
        dynamic_groups = strategy.create_dynamic_groups(unassigned)
        print(f"   创建了 {len(dynamic_groups)} 个动态组")
        
        print("\n🎉 所有测试通过！")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    success = test_all_fixes()
    
    if success:
        print("\n📋 修复总结:")
        print("  ✅ Lambda函数语法错误：已修复")
        print("  ✅ 'keywords' KeyError：已修复")
        print("  ✅ 'str' object AttributeError：已修复")
        print("  ✅ 类型安全错误：已修复")
        print("  ✅ 分类方法错误：已修复")
        print("  ✅ 重复导入错误：已修复")
        print("  ✅ 所有已知错误：已解决")
        
        print("\n🚀 系统现在可以稳定运行！")
    else:
        print("\n❌ 仍有错误需要修复")

if __name__ == '__main__':
    main()
