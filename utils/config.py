import yaml
import os
import sys
from utils.logger import get_logger, update_log_level

logger = get_logger(__name__)

class Config:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _get_default_config_yaml(self):
        """获取带注释的默认配置YAML文本"""
        return '''# 测试配置
test:
  # 循环测试配置
  loop:
    enabled: false  # 是否启用循环测试 (true/false)
    count: 1       # 循环次数 (1-100)

  # 性能测试配置
  performance:
    total_size: 128  # 总数据大小(MB) (1-1024)
    block_size: 1    # 块大小(MB) (1-64)
    iterations: 3    # 平均次数 (1-10)

# 界面配置
ui:
  always_on_top: true  # 窗口是否始终置顶 (true/false)

# 日志配置
logger:
  level: INFO  # 日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL 
'''
    
    def _load_config(self):
        """加载配置文件"""
        try:
            # 确保配置文件优先从exe目录读取
            exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(__file__))
            config_file = os.path.join(exe_dir, 'config.yaml')
            
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f)
                logger.info(f"已加载配置文件: {config_file}")
                
                # 更新日志级别
                log_level = self.config.get('logger', {}).get('level', 'INFO')
                update_log_level(log_level)
                
            else:
                # 使用默认配置
                self.config = yaml.safe_load(self._get_default_config_yaml())
                logger.warning("未找到配置文件，使用默认配置")
                
                # 创建默认配置文件
                try:
                    with open(config_file, 'w', encoding='utf-8') as f:
                        f.write(self._get_default_config_yaml())
                    logger.info(f"已创建默认配置文件: {config_file}")
                except Exception as e:
                    logger.warning(f"创建默认配置文件失败: {str(e)}")
                    
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}", exc_info=True)
    
    def get(self, key, default=None):
        """获取配置值"""
        try:
            keys = key.split('.')
            value = self.config
            for k in keys:
                value = value[k]
            return value
        except:
            return default
    
    def set(self, key, value):
        """设置配置值并保存到文件"""
        try:
            # 更新内存中的配置
            keys = key.split('.')
            config = self.config
            for k in keys[:-1]:
                config = config[k]
            config[keys[-1]] = value
            
            # 保存到文件
            exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(__file__))
            config_file = os.path.join(exe_dir, 'config.yaml')
            
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, allow_unicode=True)
            logger.info(f"配置已更新并保存到: {config_file}")
            return True
        except Exception as e:
            logger.error(f"保存配置失败: {str(e)}", exc_info=True)
            return False
    
    def reload(self):
        """重新加载配置文件"""
        logger.info("重新加载配置文件")
        self._load_config()
        return True
    
    def get_config_path(self):
        """获取配置文件路径"""
        try:
            if getattr(sys, 'frozen', False):
                # 如果是打包后的exe
                return os.path.join(os.path.dirname(sys.executable), 'config.yaml')
            else:
                # 如果是开发环境
                return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        except Exception as e:
            logger.error(f"获取配置文件路径失败: {str(e)}", exc_info=True)
            return None

# 全局配置例
config = Config() 