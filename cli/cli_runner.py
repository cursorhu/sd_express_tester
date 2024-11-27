from argparse import ArgumentParser, SUPPRESS
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
        logger.info("初始化CLI运行器")
        self.parser = ArgumentParser(
            description='SD Express Card 测试工具',
            add_help=False,  # 禁用默认的help选项
            formatter_class=argparse.RawTextHelpFormatter  # 保持帮助信息的格式
        )
        self._setup_arguments()
        self.controller = SDController()
        self.card_ops = CardOperations()
        self.test_suite = TestSuite(self.card_ops)
        logger.info("CLI运行器初始化完成")
    
    def _setup_arguments(self):
        """设置命令行参数"""
        # 添加程序描述
        self.parser.usage = """
SDExpressTester [选项]

示例:
  SDExpressTester --cli --run  # 按config.yaml配置运行测试
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
            # 如果没有参数，显示帮助信息
            if len(sys.argv) == 1:
                self.parser.print_help()
                return True
                
            args = self.parser.parse_args()
            logger.info(f"CLI参数: {args}")
            
            # 如果没有--cli参数且没有--run参数，返回False
            if not (args.cli or args.run):
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
            
            # 使用配置文件中的设置
            test_config = {
                'mode': 'all',  # 自动检测模式
                'type': 'quick',  # 默认快速测试
                'config': config  # 传递配置对象
            }
            
            # 设置输出文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"test_report_{timestamp}.txt")
            
            try:
                logger.info(f"开始测试，配置: {test_config}")
                results = self.test_suite.run_tests(test_config)
                
                # 生成报告
                self._generate_report(results, output_path)
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
    
    def _generate_report(self, results, output_path):
        """生成测试报告"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            logger.info(f"开始生成测试报告: {output_path}")
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"SD Express 测试报告 - {timestamp}\n")
                f.write("-" * 50 + "\n")
                for test_name, result in results.items():
                    f.write(f"\n{test_name}:\n")
                    f.write(f"状态: {'通过' if result['passed'] else '失败'}\n")
                    f.write(f"详情: {result['details']}\n")
            logger.info("测试报告生成完成")
        except Exception as e:
            logger.error(f"生成测试报告失败: {str(e)}", exc_info=True)
            raise