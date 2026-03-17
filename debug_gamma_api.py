#!/usr/bin/env python3
"""
调试Gamma API响应结构
"""

def debug_gamma_api_response():
    """调试Gamma API响应结构"""
    print("🔍 调试Gamma API响应结构")
    print("=" * 60)
    
    print("❌ 问题分析:")
    print("  增强的token_id获取方法仍然失败")
    print("  可能的原因:")
    print("  1. Gamma API端点不正确")
    print("  2. API响应结构与预期不符")
    print("  3. token字段名称不同")
    print("  4. 需要认证才能访问")
    print()
    
    print("🔧 调试步骤:")
    print("  1. 测试Gamma API端点")
    print("  2. 检查API响应结构")
    print("  3. 找到正确的token字段")
    print("  4. 修复提取逻辑")
    print()
    
    return True

def create_debug_method():
    """创建调试方法"""
    print("🛠️  创建调试方法")
    print("=" * 60)
    
    debug_code = '''
def debug_market_api(self, market_id: str) -> Dict:
    """调试市场API响应"""
    debug_info = {
        'market_id': market_id,
        'api_endpoints': [],
        'responses': {},
        'token_fields_found': [],
        'final_token_id': None
    }
    
    # 测试多个可能的端点
    endpoints = [
        f"{self.gamma_api_url}/markets/{market_id}",
        f"{self.gamma_api_url}/events/{market_id}",
        f"{self.gamma_api_url}/markets",
        f"{self.gamma_api_url}/events"
    ]
    
    for endpoint in endpoints:
        try:
            self.logger.info(f"测试端点: {endpoint}")
            response = requests.get(endpoint, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            debug_info['api_endpoints'].append(endpoint)
            debug_info['responses'][endpoint] = data
            
            # 查找token相关字段
            token_fields = self.find_token_fields_in_data(data)
            debug_info['token_fields_found'].extend(token_fields)
            
            self.logger.info(f"端点 {endpoint} 成功，找到token字段: {token_fields}")
            
        except Exception as e:
            self.logger.error(f"端点 {endpoint} 失败: {e}")
    
    # 尝试从响应中提取token_id
    for endpoint, data in debug_info['responses'].items():
        if isinstance(data, list) and len(data) > 0:
            # 如果是列表，查找匹配的市场
            for item in data:
                if str(item.get('id')) == market_id:
                    token_id = self.extract_token_id_from_full_data(item)
                    if token_id:
                        debug_info['final_token_id'] = token_id
                        break
        elif isinstance(data, dict):
            # 如果是字典，直接提取
            token_id = self.extract_token_id_from_full_data(data)
            if token_id:
                debug_info['final_token_id'] = token_id
                break
        
        if debug_info['final_token_id']:
            break
    
    return debug_info

def find_token_fields_in_data(self, data: Any) -> List[str]:
    """递归查找数据中的token相关字段"""
    token_fields = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            # 检查字段名是否包含token相关关键词
            if any(keyword in key.lower() for keyword in ['token', 'address', 'contract']):
                token_fields.append(f"{key}: {type(value).__name__}")
            
            # 递归检查嵌套结构
            if isinstance(value, (dict, list)):
                nested_fields = self.find_token_fields_in_data(value)
                token_fields.extend([f"{key}.{field}" for field in nested_fields])
    
    elif isinstance(data, list):
        for i, item in enumerate(data):
            nested_fields = self.find_token_fields_in_data(item)
            token_fields.extend([f"[{i}].{field}" for field in nested_fields])
    
    return token_fields
'''
    
    print("📝 调试方法代码:")
    print(debug_code)
    
    return debug_code

def create_alternative_token_methods():
    """创建备选的token获取方法"""
    print("\n🔄 创建备选的token获取方法")
    print("=" * 60)
    
    alternative_code = '''
def get_token_id_alternative_methods(self, market: Dict) -> Optional[str]:
    """使用备选方法获取token_id"""
    market_id = market.get('id')
    if not market_id:
        return None
    
    # 备选方法1: 使用ClobClient的内置方法
    try:
        if self.client:
            # 尝试获取订单簿来推断token_id
            order_book = self.client.get_order_book(market_id)
            if order_book and hasattr(order_book, 'asset_id'):
                self.logger.info(f"从订单簿获取token_id: {order_book.asset_id}")
                return order_book.asset_id
    except Exception as e:
        self.logger.warning(f"订单簿方法失败: {e}")
    
    # 备选方法2: 使用价格API
    try:
        if self.client:
            # 尝试获取价格来推断token_id
            price_data = self.client.get_price(market_id, "BUY")
            if price_data:
                self.logger.info(f"从价格API推断token_id成功")
                return market_id  # 如果价格API成功，market_id可能就是token_id
    except Exception as e:
        self.logger.warning(f"价格API方法失败: {e}")
    
    # 备选方法3: 直接使用market_id作为token_id
    try:
        self.logger.warning(f"直接使用market_id作为token_id: {market_id}")
        return market_id
    except Exception as e:
        self.logger.error(f"直接使用market_id失败: {e}")
    
    return None

def create_order_with_enhanced_fallback(self, market: Dict, side: str, size: float, price: float) -> Dict:
    """使用增强fallback的订单创建"""
    market_id = market.get('id')
    
    # 方法1: 增强的token_id获取
    token_id = self.get_market_token_id_enhanced(market)
    if token_id:
        return self.create_order(token_id, side, size, price)
    
    # 方法2: 备选方法
    token_id = self.get_token_id_alternative_methods(market)
    if token_id:
        return self.create_order(token_id, side, size, price)
    
    # 方法3: 最后的fallback
    try:
        self.logger.error(f"所有方法失败，尝试直接使用market_id: {market_id}")
        return self.create_order(market_id, side, size, price)
    except Exception as e:
        self.logger.error(f"最终fallback失败: {e}")
        return {
            'success': False,
            'error': f'所有token_id获取方法都失败 for market {market_id}',
            'order_id': None
        }
'''
    
    print("📝 备选方法代码:")
    print(alternative_code)
    
    return alternative_code

if __name__ == '__main__':
    print("Gamma API响应调试")
    print("=" * 60)
    
    debug_gamma_api_response()
    create_debug_method()
    create_alternative_token_methods()
    
    print("=" * 60)
    print("🎯 下一步行动:")
    print("1. 添加调试方法到clob_client_auto_creds.py")
    print("2. 测试不同的Gamma API端点")
    print("3. 分析实际的API响应结构")
    print("4. 实现备选的token获取方法")
    print("5. 添加多层fallback机制")
    print("=" * 60)
