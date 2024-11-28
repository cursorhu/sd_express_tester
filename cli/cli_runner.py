from argparse import ArgumentParser, RawTextHelpFormatter, SUPPRESS
from pathlib import Path
from core.controller import SDController
from core.card_ops import CardOperations
from core.test_suite import TestSuite
from utils.logger import get_logger
from utils.config import config
import sys
from datetime import datetime

logger = get_logger(__name__)

class CLIRunner:
    def __init__(self):
        logger.debug("初始化CLI运行器")
        self.parser = ArgumentParser(
            description='SD Express Card 测试工具',
            add_help=False,  # 禁用默认的help选项
            formatter_class=RawTextHelpFormatter  # 保持帮助信息的格式
        )
        self._setup_arguments()
        self.controller = SDController()
        self.card_ops = CardOperations()
        self.test_suite = TestSuite(self.card_ops)
        logger.debug("CLI运行器初始化完成")
    
    def _setup_arguments(self):
        """设置命令行参数"""
        # 添加程序描述
        self.parser.usage = """
SDExpressTester [选项]

示例:
  ./SDExpressTester.exe --cli --run  # 按config.yaml配置运行测试
"""
        
        basic = self.parser.add_argument_group('基本选项')
        basic.add_argument('-h', '--help', 
                          action='help', 
                          default=SUPPRESS,
                          help='显示帮助信息并退出')
        basic.add_argument('--cli',
                          action='store_true',
                          help='以命令行模式运行')
        basic.add_argument('--run',
                          action='store_true',
                          help='使用config.yaml配置运行测试')
    
    def run(self):
        """运行CLI测试"""
        try:
            args = self.parser.parse_args()
            logger.debug(f"CLI参数: {args}")
            
            # 只有--cli参数时显示帮助信息
            if args.cli and not args.run:
                self.parser.print_help()
                return True
            
            # 同时有--cli和--run参数时执行测试
            if args.cli and args.run:
                logger.info("开始执行CLI测试")
            else:
                logger.info("请使用--cli和--run参数运行测试")
                return False
            
            # 检查控制器
            compatibility = self.controller.check_compatibility()
            if not compatibility:
                logger.error("主机控制器不兼容")
                print("错误: 主机控制器不兼容")
                return False
            else:
                logger.info(f"控制器兼容性: {compatibility}")
                print(f"控制器兼容性: {compatibility}")
            
            # 等待并检测SD卡
            print("请插入SD卡...")
            logger.info("等待SD卡插入...")
            card_info = self.card_ops.wait_for_card(timeout=300)  # 使用默认超时时间
            if not card_info:
                logger.error("未检测到SD卡或等待超时")
                print("错误: 未检测到SD卡或等待超时")
                return False
                
            logger.info(f"检测到SD卡: {card_info}")
            print(f"检测到SD卡: {card_info}")
            
            # 获取循环测试配置
            loop_enabled = config.get('test.loop.enabled', False)
            loop_count = config.get('test.loop.count', 1)
            
            # 使用配置文件中的设置
            test_config = {
                'mode': 'all',
                'type': 'quick',
                'timeout': 300,
                'config': config,  # 传递完整的配置对象
                'progress_callback': self._update_progress,
                'result_callback': self._show_result,
                'status_callback': self._update_status
            }
            
            # 设置输出文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"test_report_{timestamp}.txt")
            
            try:
                logger.info(f"开始测试，配置: {test_config}")
                # 初始化结果列表
                all_results = []

                # 执行循环测试
                for i in range(loop_count if loop_enabled else 1):
                    if loop_enabled:
                        print(f"\n=== 第 {i+1}/{loop_count} 次测试 ===")
                        logger.info(f"开始第 {i+1}/{loop_count} 次测试")
                    
                    results = self.test_suite.run_tests(test_config)
                    if not results: break
                    all_results.append(results)
                
                # 生成报告
                self._generate_report(all_results if loop_enabled else results, output_path)
                logger.info(f"测试报告已保存至: {output_path}")
                print(f"测试报告已保存至: {output_path}")
                
                logger.info("测试完成")
                return True
                
            except Exception as e:
                logger.error(f"测试过程出错: {str(e)}", exc_info=True)
                print(f"错误: 测试过程出错: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"CLI运行错误: {str(e)}", exc_info=True)
            print(f"错误: {str(e)}")
            return False
    
    def _generate_report(self, all_results, output_path):
        """生成测试报告"""
        with open(output_path, 'w', encoding='utf-8') as f:
            # 写入报告头部
            f.write("=== SD Express Tester 测试报告 ===\n")
            f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # 写入配置信息
            f.write("测试配置:\n")
            f.write(f"- 循环测试: {'启用' if config.get('test.loop.enabled') else '禁用'}\n")
            if config.get('test.loop.enabled'):
                f.write(f"- 循环次数: {config.get('test.loop.count')}\n")
            f.write(f"- 性能测试总大小: {config.get('test.performance.total_size')}MB\n")
            f.write(f"- 性能测试块大小: {config.get('test.performance.block_size')}MB\n")
            f.write(f"- 性能测试迭代次数: {config.get('test.performance.iterations')}\n\n")
            
            # 写入测试结果
            if isinstance(all_results, list):  # 循环测试结果
                total_rounds = len(all_results)
                passed_rounds = sum(1 for results in all_results 
                                  if all(r.get('passed', False) for r in results.values()))
                failed_rounds = total_rounds - passed_rounds
                
                f.write(f"测试结果汇总:\n")
                f.write(f"- 完成测试轮数: {total_rounds}\n")
                f.write(f"- 通过轮数: {passed_rounds}\n")
                f.write(f"- 失败轮数: {failed_rounds}\n\n")
                
                # 写入每轮测试的详细结果
                for round_num, results in enumerate(all_results, 1):
                    f.write(f"\n=== 第 {round_num}/{total_rounds} 轮测试 ===\n")
                    self._write_test_details(f, results)
                    
            else:  # 单次测试结果
                f.write("测试结果:\n")
                self._write_test_details(f, all_results)

    def _write_test_details(self, f, results):
        """写入测试详情"""
        for test_name, result in results.items():
            status = "通过" if result['passed'] else "失败"
            f.write(f"\n{test_name}: {status}\n")
            # 处理多行详情
            details = result['details'].split('\n')
        for detail in details:
                if detail.strip():
                    f.write(f"  {detail}\n")

    def _update_progress(self, value):
        """更新进度"""
        print(f"\r进度: {value}%", end="", flush=True)
        if value == 100:
            print()  # 完成时换行
            
    def _show_result(self, result):
        """显示测试结果"""
        for test_name, test_result in result.items():
            status = "通过" if test_result['passed'] else "失败"
            print(f"{test_name}: {status}")
            print(f"详情: {test_result['details']}\n")
            
    def _update_status(self, message):
        """更新状态"""
        print(f"\r{message}", end="\n", flush=True)