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
 
 # python会将单个反斜杠作为转义字符，即使是在字符串中要表示反斜杠本身也得用\\
 # 此处生成config.yaml的registry_path的\\字符，应该用\\\\才能生成
    def _get_default_config_yaml(self):
        """Get default config YAML text with comments"""
        return '''# Card Configuration
card:
  sd_express_model: ""  # SD Express card model name, empty for automatic detection
  sd4_disable: null     # SD4.0 mode control: (true/false/null). true to disable SD4.0, false to re-enable SD4.0, null for no control
  registry_path: "SYSTEM\\\\CurrentControlSet\\\\Services\\\\bhtsddr\\\\GG8"  # Registry path for SD host controller
  registry_item: "sd_card_mode_dis"  # Registry item name for card configuration
  
  # Speed thresholds for card mode detection (MB/s)
  # Notice: 
  # UHS-II speed range: FD156 is 156MB/s, HD312 is 312MB/s,
  # UHS-I speed range: SDR50 is 50MB/s, SDR104 is 104MB/s 
  # SD Express 8.0 (PCIe Gen4) theoretical speed up to 2000MB/s
  # SD Express 7.0 (PCIe Gen3) theoretical speed up to 1000MB/s
  # We leave some margin for minimum speed threshold.
  speed_threshold:
    sd_express_8: 800    # SD Express 8.0 minimum speed threshold (800 MB/s)
    sd_4: 120          # SD 4.0 (UHS-II) minimum speed threshold (120 MB/s)
    sd_3: 30           # SD 3.0 (UHS-I) minimum speed threshold (30 MB/s)

# Test Configuration
test:
  # Loop test configuration
  loop:
    enabled: false  # Enable loop test (true/false)
    count: 1       # Loop count (1-100)

  # Performance test configuration
  performance:
    total_size: 128  # Total data size(MB) (1-1024)
    block_size: 1    # Block size(MB) (1-64)
    iterations: 3    # Average count (1-10)

  # Test timeout configuration (seconds)
  timeout: 600       # Single test loop timeout (10 minutes)

# UI Configuration
ui:
  always_on_top: false  # Keep window always on top (true/false)

# Logger Configuration
logger:
  level: INFO  # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL 
'''
    
    def _load_config(self):
        """Load configuration file"""
        try:
            # Ensure config file is read from exe directory first
            exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(__file__))
            config_file = os.path.join(exe_dir, 'config.yaml')
            
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f)
                logger.info(f"Loaded config file: {config_file}")
                
                # Update log level
                log_level = self.config.get('logger', {}).get('level', 'INFO')
                update_log_level(log_level)
                
            else:
                # Use default configuration
                self.config = yaml.safe_load(self._get_default_config_yaml())
                logger.warning("Config file not found, using default configuration")
                
                # Create default config file
                try:
                    with open(config_file, 'w', encoding='utf-8') as f:
                        f.write(self._get_default_config_yaml())
                    logger.info(f"Created default config file: {config_file}")
                except Exception as e:
                    logger.warning(f"Failed to create default config file: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Failed to load config file: {str(e)}", exc_info=True)
    
    def get(self, key, default=None):
        """Get configuration value"""
        try:
            keys = key.split('.')
            value = self.config
            for k in keys:
                value = value[k]
            return value
        except:
            return default
    
    def set(self, key, value):
        """Set configuration value and save to file"""
        try:
            # Update configuration in memory
            keys = key.split('.')
            config = self.config
            for k in keys[:-1]:
                config = config[k]
            config[keys[-1]] = value
            
            # Save to file
            exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(__file__))
            config_file = os.path.join(exe_dir, 'config.yaml')
            
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, allow_unicode=True)
            logger.info(f"Configuration updated and saved to: {config_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}", exc_info=True)
            return False
    
    def reload(self):
        """Reload configuration file"""
        logger.info("Reload configuration file")
        self._load_config()
        return True
    
    def get_config_path(self):
        """Get configuration file path"""
        try:
            if getattr(sys, 'frozen', False):
                # If it's a packaged exe
                return os.path.join(os.path.dirname(sys.executable), 'config.yaml')
            else:
                # If it's a development environment
                return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        except Exception as e:
            logger.error(f"Failed to get configuration file path: {str(e)}", exc_info=True)
            return None

# Global configuration example
config = Config() 