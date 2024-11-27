import logging
import os
import sys
from datetime import datetime

def get_app_dir():
    """获取应用程序目录"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的可执行文件
        return os.path.dirname(sys.executable)
    else:
        # 如果是开发环境
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def setup_logger(level=logging.INFO):
    """设置logger，避免重复添加handler"""
    logger = logging.getLogger('sd_express_tester')
    
    # 如果logger已经有handler，说明已经初始化过，直接返回
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 创建logs目录
    log_dir = os.path.join(get_app_dir(), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 配置日志文件名（按日期和时间）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f'sd_express_tester_{timestamp}.log')
    
    # 创建文件处理器
    file_handler = logging.FileHandler(
        log_file,
        mode='w',
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # 设置日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器到logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # 添加启动信息
    logger.info("="*50)
    logger.info("程序启动")
    logger.info(f"日志文件: {log_file}")
    logger.info(f"日志级别: {logging.getLevelName(level)}")
    logger.info("="*50)
    
    return logger

# 全局logger实例
logger = setup_logger()

def get_logger(name=None):
    """获取logger实例"""
    if name:
        child_logger = logging.getLogger(name)
        # 确保子logger继承父logger的设置
        child_logger.parent = logger
        return child_logger
    return logger

def update_log_level(level):
    """更新日志级别"""
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    level_num = level_map.get(level.upper(), logging.INFO)
    logger.setLevel(level_num)
    for handler in logger.handlers:
        handler.setLevel(level_num)
    logger.info(f"日志级别已更新为: {level}") 