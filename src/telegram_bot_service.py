#!/usr/bin/env python3
"""
Telegram Bot交互服务
为自动交易系统提供Telegram远程控制功能
支持状态查询、策略管理、参数调整等交互命令
"""

import os
import json
import time
import threading
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import requests
import logging
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from logger_config import get_telegram_logger

@dataclass
class BotCommand:
    """Bot命令定义"""
    command: str
    description: str
    handler: Callable
    admin_only: bool = False

class TelegramBotService:
    """Telegram Bot交互服务"""
    
    def __init__(self, token: str, chat_id: str, strategy_manager=None):
        self.token = token
        self.chat_id = chat_id
        self.strategy_manager = strategy_manager
        
        # 初始化日志记录器
        self.logger = get_telegram_logger()
        self.logger.info(f"初始化Telegram Bot服务 - Chat ID: {chat_id}")
        
        # 进程锁机制
        self.lock_file = f"/tmp/telegram_bot_{chat_id}.lock"
        self._check_single_instance()
        
        # 运行状态
        self.is_running = False
        self.bot_thread = None
        
        # Bot配置
        self.bot = Bot(token=token)
        self.application = None
        
        # 用户权限
        self.admin_users = {int(chat_id)}  # 默认只有配置的用户是管理员
        
        # 命令注册
        self.commands: Dict[str, BotCommand] = {}
        self._register_commands()
    
    def _check_single_instance(self):
        """检查单实例，防止多实例运行"""
        try:
            import os
            import fcntl
            
            # 尝试创建锁文件
            self.lock_fd = open(self.lock_file, 'w')
            
            try:
                # 尝试获取文件锁
                fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                # 写入进程信息
                self.lock_fd.write(f"{os.getpid()}\n")
                self.lock_fd.flush()
                
                self.logger.info("✅ 获取Telegram Bot实例锁成功")
                
            except IOError:
                # 锁文件被占用，说明已有实例在运行
                self.logger.error("❌ 检测到其他Telegram Bot实例正在运行")
                self.logger.error("💡 请先停止其他实例或等待其完成")
                raise RuntimeError("多个Telegram Bot实例冲突")
                
        except ImportError:
            # Windows系统或其他不支持fcntl的系统
            self.logger.warning("⚠️  系统不支持文件锁，跳过单实例检查")
            self.lock_fd = None
        except Exception as e:
            self.logger.error(f"❌ 单实例检查失败: {e}")
            self.lock_fd = None
    
    def _release_lock(self):
        """释放进程锁"""
        try:
            if hasattr(self, 'lock_fd') and self.lock_fd:
                self.lock_fd.close()
                
            # 删除锁文件
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
                
            self.logger.info("✅ Telegram Bot实例锁已释放")
            
        except Exception as e:
            self.logger.error(f"❌ 释放实例锁失败: {e}")
    
    def _register_commands(self):
        """注册所有命令"""
        commands = [
            BotCommand("start", "🚀 启动Bot并显示帮助", self.cmd_start),
            BotCommand("help", "📖 显示帮助信息", self.cmd_help),
            BotCommand("status", "📊 查看系统状态", self.cmd_status),
            BotCommand("strategies", "🎯 查看策略信息", self.cmd_strategies),
            BotCommand("performance", "📈 查看策略表现", self.cmd_performance),
            BotCommand("positions", "💼 查看当前持仓", self.cmd_positions),
            BotCommand("trades", "📋 查看交易历史", self.cmd_trades),
            BotCommand("risk", "⚠️ 查看风险状态", self.cmd_risk),
            BotCommand("config", "⚙️ 查看配置信息", self.cmd_config),
            BotCommand("set", "🔧 设置参数", self.cmd_set, admin_only=True),
            BotCommand("restart", "🔄 重启策略", self.cmd_restart, admin_only=True),
            BotCommand("stop", "⏹️ 停止策略", self.cmd_stop, admin_only=True),
            BotCommand("emergency", "🚨 紧急停止所有交易", self.cmd_emergency, admin_only=True),
        ]
        
        for cmd in commands:
            self.commands[cmd.command] = cmd
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """启动命令"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        
        if not self._check_permission(user_id):
            await update.message.reply_text("❌ 您没有权限使用此Bot")
            return
        
        welcome_msg = f"""
🎯 **Polymarket自动交易系统**

欢迎 {user_name}！

我是您的交易助手，提供以下功能：
📊 实时状态监控
🎯 策略管理
⚙️ 参数调整
🚨 风险控制

使用 /help 查看所有命令
"""
        
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """帮助命令"""
        if not self._check_permission(update.effective_user.id):
            return
        
        help_text = "📖 **命令列表**\n\n"
        
        # 普通命令
        normal_cmds = [cmd for cmd in self.commands.values() if not cmd.admin_only]
        help_text += "🔹 **基础命令**\n"
        for cmd in normal_cmds:
            help_text += f"/{cmd.command} - {cmd.description}\n"
        
        # 管理员命令
        admin_cmds = [cmd for cmd in self.commands.values() if cmd.admin_only]
        if admin_cmds:
            help_text += "\n🔹 **管理员命令**\n"
            for cmd in admin_cmds:
                help_text += f"/{cmd.command} - {cmd.description}\n"
        
        help_text += "\n💡 提示: 使用 /set 参数名=值 来调整参数"
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """状态查询命令"""
        if not self._check_permission(update.effective_user.id):
            return
        
        if not self.strategy_manager:
            await update.message.reply_text("❌ 策略管理器未连接")
            return
        
        try:
            # 获取系统状态
            manager = self.strategy_manager
            
            # 安全获取属性
            is_running = getattr(manager, 'is_running', True)
            total_trades = manager.daily_stats.get('total_trades', 0) if hasattr(manager, 'daily_stats') else 0
            successful_trades = manager.daily_stats.get('successful_trades', 0) if hasattr(manager, 'daily_stats') else 0
            total_pnl = manager.daily_stats.get('total_pnl', 0.0) if hasattr(manager, 'daily_stats') else 0.0
            total_capital = getattr(manager, 'total_capital', 1000.0)
            
            # 计算运行时间
            start_time = getattr(manager, 'start_time', datetime.now())
            runtime = datetime.now() - start_time
            
            # 安全计算成功率
            success_rate = ((successful_trades/total_trades)*100) if total_trades > 0 else 0.0
            
            # 安全计算活跃策略
            strategies_dict = getattr(manager, 'strategies', {})
            active_strategies = len([s for s in strategies_dict.values() if s])
            total_strategies = len(strategies_dict)
            strategy_ratio = f"{active_strategies}/{total_strategies}" if total_strategies > 0 else "0/0"
            
            status_msg = f"""
📊 **系统状态**
━━━━━━━━━━━━━━━━━━━━

🔄 运行状态: {'🟢 运行中' if is_running else '🔴 已停止'}
⏰ 运行时间: {str(runtime).split('.')[0]}
💰 总资金: ${total_capital:,.2f}

📋 今日交易:
   • 总交易数: {total_trades}
   • 成功交易: {successful_trades}
   • 成功率: {success_rate:.1f}%
   • 总盈亏: ${total_pnl:+.2f}

🎯 活跃策略: {strategy_ratio}
"""
            
            # 创建控制按钮
            keyboard = [
                [InlineKeyboardButton("🔄 刷新状态", callback_data="refresh_status")],
                [InlineKeyboardButton("📈 策略表现", callback_data="show_performance")],
                [InlineKeyboardButton("⚙️ 参数设置", callback_data="show_config")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(status_msg, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            await update.message.reply_text(f"❌ 获取状态失败: {e}")
    
    async def cmd_strategies(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """策略信息查询"""
        if not self._check_permission(update.effective_user.id):
            return
        
        if not self.strategy_manager:
            await update.message.reply_text("❌ 策略管理器未连接")
            return
        
        try:
            manager = self.strategy_manager
            strategies_msg = "🎯 **策略信息**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for name, config in manager.strategy_configs.items():
                strategy = manager.strategies.get(name)
                status = "🟢 活跃" if strategy else "🔴 停用"
                
                strategies_msg += f"""
📊 **{config['name']}**
   状态: {status}
   权重: {config['weight']:.1%}
   最大仓位: {config['max_position_size']:.1%}
   最小置信度: {config['min_confidence']:.1%}
   启用状态: {'🟢 启用' if config['enabled'] else '🔴 禁用'}
"""
            
            await update.message.reply_text(strategies_msg, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ 获取策略信息失败: {e}")
    
    async def cmd_performance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """策略表现查询"""
        if not self._check_permission(update.effective_user.id):
            return
        
        if not self.strategy_manager:
            await update.message.reply_text("❌ 策略管理器未连接")
            return
        
        try:
            manager = self.strategy_manager
            performance_msg = "📈 **策略表现**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for name, performance in manager.strategy_performances.items():
                config = manager.strategy_configs.get(name)
                if not config:
                    continue
                
                success_rate = (performance['successful_trades'] / performance['total_trades'] * 100) if performance['total_trades'] > 0 else 0
                
                performance_msg += f"""
🎯 **{config['name']}**
   • 总交易: {performance['total_trades']}
   • 成功交易: {performance['successful_trades']}
   • 成功率: {success_rate:.1f}%
   • 总收益: {performance['total_return']:+.2%}
   • 当前仓位: {len(performance['current_positions'])}
   • 最大回撤: {performance['max_drawdown']:.2%}
   • 夏普比率: {performance['sharpe_ratio']:.2f}
"""
            
            await update.message.reply_text(performance_msg, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ 获取表现数据失败: {e}")
    
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """持仓查询"""
        if not self._check_permission(update.effective_user.id):
            return
        
        if not self.strategy_manager:
            await update.message.reply_text("❌ 策略管理器未连接")
            return
        
        try:
            manager = self.strategy_manager
            positions_msg = "💼 **当前持仓**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            
            total_positions = 0
            for name, performance in manager.strategy_performances.items():
                if performance['current_positions']:
                    positions_msg += f"🎯 **{name}**\n"
                    for pos in performance['current_positions'][:5]:  # 只显示前5个
                        positions_msg += f"   • {pos.get('market', 'Unknown')}: ${pos.get('size', 0):.2f}\n"
                    total_positions += len(performance['current_positions'])
            
            if total_positions == 0:
                positions_msg += "📝 当前无持仓"
            
            await update.message.reply_text(positions_msg, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ 获取持仓信息失败: {e}")
    
    async def cmd_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """交易历史查询"""
        if not self._check_permission(update.effective_user.id):
            return
        
        try:
            # 获取最近交易记录
            trades_file = "data/trades.json"
            if os.path.exists(trades_file):
                with open(trades_file, 'r', encoding='utf-8') as f:
                    trades = json.load(f)
                
                trades_msg = "📋 **最近交易**\n━━━━━━━━━━━━━━━━━━━━\n\n"
                
                for trade in trades[-10:]:  # 显示最近10笔
                    timestamp = trade.get('timestamp', '')
                    strategy = trade.get('strategy', 'Unknown')
                    market = trade.get('market', 'Unknown')[:30]
                    signal = trade.get('signal', 'Unknown')
                    confidence = trade.get('confidence', 0)
                    
                    trades_msg += f"🕐 {timestamp}\n"
                    trades_msg += f"🎯 {strategy}: {signal}\n"
                    trades_msg += f"📈 {market}\n"
                    trades_msg += f"🎲 置信度: {confidence:.1%}\n\n"
            else:
                trades_msg = "📝 暂无交易记录"
            
            await update.message.reply_text(trades_msg, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ 获取交易历史失败: {e}")
    
    async def cmd_risk(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """风险状态查询"""
        if not self._check_permission(update.effective_user.id):
            return
        
        if not self.strategy_manager:
            await update.message.reply_text("❌ 策略管理器未连接")
            return
        
        try:
            manager = self.strategy_manager
            risk_msg = "⚠️ **风险状态**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # 风险指标
            daily_loss = manager.daily_stats.get('total_pnl', 0)
            max_daily_loss = float(os.getenv('MAX_DAILY_LOSS_USD', '50'))
            
            risk_level = "🟢 正常"
            if daily_loss < -max_daily_loss * 0.5:
                risk_level = "🟡 警告"
            if daily_loss < -max_daily_loss:
                risk_level = "🔴 危险"
            
            risk_msg += f"""
🎯 风险等级: {risk_level}
💰 今日盈亏: ${daily_loss:+.2f}
🚨 最大日损失: ${max_daily_loss:.2f}
📊 总风险敞口: ${manager.total_capital * 0.8:.2f}

🛡️ 风险控制:
   • 单笔最大交易: ${float(os.getenv('MAX_TRADE_AMOUNT_USD', '10')):.2f}
   • 最大仓位比例: {manager.risk_params.get('max_position_ratio', 0.2):.1%}
   • 止损比例: {manager.risk_params.get('stop_loss_ratio', 0.1):.1%}
"""
            
            await update.message.reply_text(risk_msg, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ 获取风险状态失败: {e}")
    
    async def cmd_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """配置信息查询"""
        if not self._check_permission(update.effective_user.id):
            return
        
        if not self.strategy_manager:
            await update.message.reply_text("❌ 策略管理器未连接")
            return
        
        try:
            manager = self.strategy_manager
            config_msg = "⚙️ **系统配置**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            
            config_msg += f"""
💰 **资金配置**
   总资金: ${manager.total_capital:,.2f}
   交易模式: {'实盘' if manager.enable_trading else '模拟'}

🎯 **策略权重**
"""
            for name, config in manager.strategy_configs.items():
                config_msg += f"   • {config['name']}: {config['weight']:.1%}\n"
            
            config_msg += f"""
⚠️ **风险参数**
   最大日损失: ${float(os.getenv('MAX_DAILY_LOSS_USD', '50')):.2f}
   最大单笔: ${float(os.getenv('MAX_TRADE_AMOUNT_USD', '10')):.2f}
   最大仓位: {float(os.getenv('MAX_POSITION_SIZE', '0.3')):.1%}
   止损比例: {float(os.getenv('STOP_LOSS_PERCENTAGE', '10')):.1%}
"""
            
            # 创建参数调整按钮
            keyboard = [
                [InlineKeyboardButton("💰 调整资金", callback_data="adjust_capital")],
                [InlineKeyboardButton("⚖️ 调整权重", callback_data="adjust_weights")],
                [InlineKeyboardButton("🛡️ 风险设置", callback_data="risk_settings")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(config_msg, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            await update.message.reply_text(f"❌ 获取配置信息失败: {e}")
    
    async def cmd_set(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """参数设置命令"""
        if not self._check_admin_permission(update.effective_user.id):
            await update.message.reply_text("❌ 需要管理员权限")
            return
        
        if not context.args:
            await update.message.reply_text("""
🔧 **参数设置用法**
/set 参数名=值

支持的参数:
• capital=10000 - 设置总资金
• max_trade=500 - 设置最大单笔交易
• max_loss=10 - 设置最大日损失
• strategy_name.weight=0.3 - 设置策略权重
• strategy_name.confidence=0.7 - 设置策略最小置信度
""")
            return
        
        try:
            # 解析参数
            param_text = context.args[0]
            if '=' not in param_text:
                await update.message.reply_text("❌ 参数格式错误，使用: 参数名=值")
                return
            
            param_name, param_value = param_text.split('=', 1)
            
            # 处理不同类型的参数
            success = await self._update_parameter(param_name.strip(), param_value.strip())
            
            if success:
                await update.message.reply_text(f"✅ 参数更新成功: {param_name}={param_value}")
            else:
                await update.message.reply_text(f"❌ 参数更新失败: {param_name}")
                
        except Exception as e:
            await update.message.reply_text(f"❌ 参数设置失败: {e}")
    
    async def cmd_restart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """重启策略"""
        if not self._check_admin_permission(update.effective_user.id):
            await update.message.reply_text("❌ 需要管理员权限")
            return
        
        try:
            if self.strategy_manager:
                await update.message.reply_text("🔄 正在重启策略...")
                
                # 停止所有策略
                self.strategy_manager.is_running = False
                time.sleep(2)
                
                # 重新启动
                self.strategy_manager.is_running = True
                self.strategy_manager.start_all_strategies()
                
                await update.message.reply_text("✅ 策略重启完成")
            else:
                await update.message.reply_text("❌ 策略管理器未连接")
                
        except Exception as e:
            await update.message.reply_text(f"❌ 策略重启失败: {e}")
    
    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """停止策略"""
        if not self._check_admin_permission(update.effective_user.id):
            await update.message.reply_text("❌ 需要管理员权限")
            return
        
        try:
            if self.strategy_manager:
                self.strategy_manager.is_running = False
                await update.message.reply_text("⏹️ 所有策略已停止")
            else:
                await update.message.reply_text("❌ 策略管理器未连接")
                
        except Exception as e:
            await update.message.reply_text(f"❌ 策略停止失败: {e}")
    
    async def cmd_emergency(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """紧急停止"""
        if not self._check_admin_permission(update.effective_user.id):
            await update.message.reply_text("❌ 需要管理员权限")
            return
        
        try:
            if self.strategy_manager:
                # 立即停止所有交易
                self.strategy_manager.is_running = False
                self.strategy_manager.enable_trading = False
                
                # 发送紧急通知
                await update.message.reply_text("🚨 **紧急停止已执行**\n所有交易已立即停止！")
                
                # 发送通知到其他渠道
                if hasattr(self.strategy_manager, 'notification_service'):
                    self.strategy_manager.notification_service.critical(
                        "紧急停止", 
                        "管理员执行了紧急停止，所有交易已暂停"
                    )
            else:
                await update.message.reply_text("❌ 策略管理器未连接")
                
        except Exception as e:
            await update.message.reply_text(f"❌ 紧急停止失败: {e}")
    
    async def _update_parameter(self, param_name: str, param_value: str) -> bool:
        """更新参数"""
        try:
            if not self.strategy_manager:
                return False
            
            manager = self.strategy_manager
            
            # 处理不同参数
            if param_name == "capital":
                manager.total_capital = float(param_value)
            elif param_name == "max_trade":
                manager.risk_params['max_trade_size'] = float(param_value)
            elif param_name == "max_loss":
                manager.risk_params['max_daily_loss'] = float(param_value)
            elif '.' in param_name:
                # 策略参数
                parts = param_name.split('.')
                if len(parts) == 3 and parts[2] == "weight":
                    strategy_name = parts[0] + "_" + parts[1]
                    if strategy_name in manager.strategy_configs:
                        old_weight = manager.strategy_configs[strategy_name]['weight']
                        new_weight = float(param_value)
                        manager.strategy_configs[strategy_name]['weight'] = new_weight
                        manager.strategy_configs[strategy_name]['enabled'] = new_weight > 0
                        
                        # 同时更新环境变量
                        env_var_name = f"{parts[0].upper()}_{parts[1].upper()}_WEIGHT"
                        os.environ[env_var_name] = str(new_weight)
                        
                        return True
                elif len(parts) == 3 and parts[2] == "confidence":
                    strategy_name = parts[0] + "_" + parts[1]
                    if strategy_name in manager.strategy_configs:
                        old_confidence = manager.strategy_configs[strategy_name]['min_confidence']
                        new_confidence = float(param_value)
                        manager.strategy_configs[strategy_name]['min_confidence'] = new_confidence
                        
                        # 同时更新环境变量
                        env_var_name = f"{parts[0].upper()}_{parts[1].upper()}_MIN_CONFIDENCE"
                        os.environ[env_var_name] = str(new_confidence)
                        
                        return True
            else:
                return False
            
            return True
            
        except Exception:
            return False
    
    async def cmd_adjust_capital(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """调整资金设置"""
        if not self._check_admin_permission(update.effective_user.id):
            await update.callback_query.message.reply_text("❌ 需要管理员权限")
            return
        
        await update.callback_query.message.reply_text("""
💰 **资金调整**

当前资金设置:
• 总资金: $10,000.00

📝 **使用方法:**
/set capital=15000  (设置总资金为$15,000)
/set max_trade=20    (设置单笔最大交易为$20)
/set max_loss=100    (设置日最大损失为$100)

💡 示例: /set capital=15000
""")
    
    async def cmd_adjust_weights(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """调整策略权重"""
        if not self._check_admin_permission(update.effective_user.id):
            await update.callback_query.message.reply_text("❌ 需要管理员权限")
            return
        
        await update.callback_query.message.reply_text("""
⚖️ **策略权重调整**

当前策略权重:
• Probability Arbitrage: 100.0%

📝 **使用方法:**
/set probability_arbitrage.weight=0.6  (设置权重为60%)
/set probability_arbitrage.confidence=0.8  (设置最小置信度为80%)

💡 示例: /set probability_arbitrage.weight=0.6
""")
    
    async def cmd_risk_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """风险设置"""
        if not self._check_admin_permission(update.effective_user.id):
            await update.callback_query.message.reply_text("❌ 需要管理员权限")
            return
        
        # 从环境变量读取当前风险设置
        max_daily_loss = float(os.getenv('MAX_DAILY_LOSS_USD', '50'))
        max_trade_size = float(os.getenv('MAX_TRADE_AMOUNT_USD', '10'))
        max_position_size = float(os.getenv('MAX_POSITION_SIZE', '0.3'))
        stop_loss_percentage = float(os.getenv('STOP_LOSS_PERCENTAGE', '10'))
        
        await update.callback_query.message.reply_text(f"""
🛡️ **风险参数设置**

当前风险设置:
• 最大日损失: ${max_daily_loss:.2f}
• 单笔最大交易: ${max_trade_size:.2f}
• 最大仓位比例: {max_position_size:.1%}
• 止损比例: {stop_loss_percentage:.1%}

📝 **使用方法:**
/set max_loss=100     (设置日最大损失为$100)
/set max_trade=25     (设置单笔最大交易为$25)
/set max_position=0.5 (设置最大仓位比例为50%)
/set stop_loss=0.15   (设置止损比例为15%)

💡 示例: /set max_loss=100
""")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """按钮回调处理"""
        query = update.callback_query
        await query.answer()
        
        if not self._check_permission(query.from_user.id):
            return
        
        data = query.data
        
        try:
            if data == "refresh_status":
                # 创建一个模拟的message对象用于回调处理
                await self.cmd_status_callback(update, context)
            elif data == "show_performance":
                await self.cmd_performance_callback(update, context)
            elif data == "show_config":
                await self.cmd_config_callback(update, context)
            elif data == "adjust_capital":
                await self.cmd_adjust_capital(update, context)
            elif data == "adjust_weights":
                await self.cmd_adjust_weights(update, context)
            elif data == "risk_settings":
                await self.cmd_risk_settings(update, context)
        except Exception as e:
            self.logger.error(f"按钮回调处理失败: {e}")
            await query.message.reply_text(f"❌ 按钮操作失败: {e}")
        # 可以添加更多按钮处理
    
    async def cmd_status_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """状态查询回调（用于按钮）"""
        query = update.callback_query
        await self.cmd_status_from_callback(query, context)
    
    async def cmd_performance_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """策略表现查询回调（用于按钮）"""
        query = update.callback_query
        await self.cmd_performance_from_callback(query, context)
    
    async def cmd_config_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """配置信息查询回调（用于按钮）"""
        query = update.callback_query
        await self.cmd_config_from_callback(query, context)
    
    async def cmd_status_from_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """从回调处理状态查询"""
        if not self.strategy_manager:
            await query.message.reply_text("❌ 策略管理器未连接")
            return
        
        try:
            # 获取系统状态
            manager = self.strategy_manager
            
            # 安全获取属性
            is_running = getattr(manager, 'is_running', True)
            total_trades = manager.daily_stats.get('total_trades', 0) if hasattr(manager, 'daily_stats') else 0
            successful_trades = manager.daily_stats.get('successful_trades', 0) if hasattr(manager, 'daily_stats') else 0
            total_pnl = manager.daily_stats.get('total_pnl', 0.0) if hasattr(manager, 'daily_stats') else 0.0
            total_capital = getattr(manager, 'total_capital', 1000.0)
            
            # 计算运行时间
            start_time = getattr(manager, 'start_time', datetime.now())
            runtime = datetime.now() - start_time
            
            # 安全计算成功率
            success_rate = ((successful_trades/total_trades)*100) if total_trades > 0 else 0.0
            
            # 安全计算活跃策略
            strategies_dict = getattr(manager, 'strategies', {})
            active_strategies = len([s for s in strategies_dict.values() if s])
            total_strategies = len(strategies_dict)
            strategy_ratio = f"{active_strategies}/{total_strategies}" if total_strategies > 0 else "0/0"
            
            status_msg = f"""
📊 **系统状态**
━━━━━━━━━━━━━━━━━━━━

🔄 运行状态: {'🟢 运行中' if is_running else '🔴 已停止'}
⏰ 运行时间: {str(runtime).split('.')[0]}
💰 总资金: ${total_capital:,.2f}

📋 今日交易:
   • 总交易数: {total_trades}
   • 成功交易: {successful_trades}
   • 成功率: {success_rate:.1f}%
   • 总盈亏: ${total_pnl:+.2f}

🎯 活跃策略: {strategy_ratio}
"""
            
            # 创建控制按钮
            keyboard = [
                [InlineKeyboardButton("🔄 刷新状态", callback_data="refresh_status")],
                [InlineKeyboardButton("📈 策略表现", callback_data="show_performance")],
                [InlineKeyboardButton("⚙️ 参数设置", callback_data="show_config")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(status_msg, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            await query.message.reply_text(f"❌ 获取状态失败: {e}")
    
    async def cmd_performance_from_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """从回调处理策略表现查询"""
        if not self.strategy_manager:
            await query.message.reply_text("❌ 策略管理器未连接")
            return
        
        try:
            manager = self.strategy_manager
            performance_msg = "📈 **策略表现**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for name, performance in manager.strategy_performances.items():
                config = manager.strategy_configs.get(name)
                if not config:
                    continue
                
                success_rate = (performance['successful_trades'] / performance['total_trades'] * 100) if performance['total_trades'] > 0 else 0
                
                performance_msg += f"""
🎯 **{config['name']}**
   • 总交易: {performance['total_trades']}
   • 成功交易: {performance['successful_trades']}
   • 成功率: {success_rate:.1f}%
   • 总收益: {performance['total_return']:+.2%}
   • 当前仓位: {len(performance['current_positions'])}
   • 最大回撤: {performance['max_drawdown']:.2%}
   • 夏普比率: {performance['sharpe_ratio']:.2f}
"""
            
            await query.message.reply_text(performance_msg, parse_mode='Markdown')
            
        except Exception as e:
            await query.message.reply_text(f"❌ 获取表现数据失败: {e}")
    
    async def cmd_config_from_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """从回调处理配置信息查询"""
        if not self.strategy_manager:
            await query.message.reply_text("❌ 策略管理器未连接")
            return
        
        try:
            manager = self.strategy_manager
            config_msg = "⚙️ **系统配置**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            
            config_msg += f"""
💰 **资金配置**
   总资金: ${manager.total_capital:,.2f}
   交易模式: {'实盘' if manager.enable_trading else '模拟'}

🎯 **策略权重**
"""
            for name, config in manager.strategy_configs.items():
                config_msg += f"   • {config['name']}: {config['weight']:.1%}\n"
            
            config_msg += f"""
⚠️ **风险参数**
   最大日损失: ${float(os.getenv('MAX_DAILY_LOSS_USD', '50')):.2f}
   最大单笔: ${float(os.getenv('MAX_TRADE_AMOUNT_USD', '10')):.2f}
   最大仓位: {float(os.getenv('MAX_POSITION_SIZE', '0.3')):.1%}
   止损比例: {float(os.getenv('STOP_LOSS_PERCENTAGE', '10')):.1%}
"""
            
            # 创建参数调整按钮
            keyboard = [
                [InlineKeyboardButton("💰 调整资金", callback_data="adjust_capital")],
                [InlineKeyboardButton("⚖️ 调整权重", callback_data="adjust_weights")],
                [InlineKeyboardButton("🛡️ 风险设置", callback_data="risk_settings")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(config_msg, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            await query.message.reply_text(f"❌ 获取配置信息失败: {e}")
    
    def _check_permission(self, user_id: int) -> bool:
        """检查用户权限"""
        return user_id in self.admin_users
    
    def _check_admin_permission(self, user_id: int) -> bool:
        """检查管理员权限"""
        return user_id in self.admin_users
    
    def start_bot(self):
        """启动Bot"""
        if self.is_running:
            return
        
        try:
            # 创建应用
            self.application = Application.builder().token(self.token).build()
            
            # 注册命令处理器
            for cmd_name, cmd_info in self.commands.items():
                if cmd_info.admin_only:
                    self.application.add_handler(CommandHandler(cmd_name, cmd_info.handler))
                else:
                    self.application.add_handler(CommandHandler(cmd_name, cmd_info.handler))
            
            # 注册按钮回调
            self.application.add_handler(CallbackQueryHandler(self.button_callback))
            
            # 在后台线程启动
            self.bot_thread = threading.Thread(target=self._run_bot, daemon=True)
            self.bot_thread.start()
            
            self.is_running = True
            print("✅ Telegram Bot已启动")
            
        except Exception as e:
            print(f"❌ Bot启动失败: {e}")
    
    def _run_bot(self):
        """运行Bot"""
        try:
            import asyncio
            from telegram.error import Conflict, TimedOut, NetworkError
            
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def run_polling():
                try:
                    await self.application.initialize()
                    await self.application.start()
                    
                    # 添加重试机制和冲突处理
                    max_retries = 3
                    retry_count = 0
                    
                    while retry_count < max_retries and self.is_running:
                        try:
                            await self.application.updater.start_polling(drop_pending_updates=True)
                            break  # 成功启动，退出重试循环
                        except Conflict as e:
                            self.logger.warning(f"Telegram Bot冲突: {e}")
                            if retry_count < max_retries - 1:
                                retry_count += 1
                                self.logger.info(f"等待 {retry_count * 5} 秒后重试...")
                                await asyncio.sleep(retry_count * 5)
                                continue
                            else:
                                self.logger.error("多次重试后仍有冲突，停止Bot")
                                return
                        except (TimedOut, NetworkError) as e:
                            self.logger.warning(f"Telegram网络错误: {e}")
                            if retry_count < max_retries - 1:
                                retry_count += 1
                                self.logger.info(f"等待 {retry_count * 3} 秒后重试...")
                                await asyncio.sleep(retry_count * 3)
                                continue
                            else:
                                self.logger.error("多次重试后仍有网络问题，停止Bot")
                                return
                    
                    # 保持运行
                    while self.is_running:
                        await asyncio.sleep(1)
                
                except Exception as e:
                    self.logger.error(f"Bot启动失败: {e}")
                finally:
                    # 清理
                    try:
                        if hasattr(self.application, 'updater') and self.application.updater.is_running:
                            await self.application.updater.stop()
                        if self.application.running:
                            await self.application.stop()
                        await self.application.shutdown()
                    except Exception as e:
                        self.logger.error(f"Bot清理失败: {e}")
            
            loop.run_until_complete(run_polling())
            loop.close()
            
        except Exception as e:
            self.logger.error(f"Bot运行错误: {e}")
            self.logger.info("建议: 检查是否有其他Bot实例在运行")
    
    def stop_bot(self):
        """停止Bot"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        try:
            if self.application:
                self.application.stop()
                self.logger.info("✅ Telegram Bot已停止")
        except Exception as e:
            self.logger.error(f"❌ 停止Bot失败: {e}")
        finally:
            # 释放进程锁
            self._release_lock()
        
        print("⏹️ Telegram Bot已停止")
    
    def send_message(self, text: str, parse_mode: str = 'Markdown'):
        """发送消息到指定聊天"""
        try:
            self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode
            )
        except Exception as e:
            self.logger.error(f"发送消息失败: {e}")

# 全局Bot实例
_telegram_bot: Optional[TelegramBotService] = None

def get_telegram_bot(token: str = None, chat_id: str = None, strategy_manager=None) -> TelegramBotService:
    """获取全局Bot实例"""
    global _telegram_bot
    if _telegram_bot is None and token and chat_id:
        _telegram_bot = TelegramBotService(token, chat_id, strategy_manager)
    return _telegram_bot

def init_telegram_bot(token: str, chat_id: str, strategy_manager=None) -> TelegramBotService:
    """初始化Bot"""
    global _telegram_bot
    _telegram_bot = TelegramBotService(token, chat_id, strategy_manager)
    return _telegram_bot
