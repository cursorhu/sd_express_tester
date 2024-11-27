import wmi
import win32com.client
from enum import Enum
from utils.logger import get_logger

logger = get_logger(__name__)

class ControllerType(Enum):
    NVME = "NVMe"
    SD_HOST = "SD Host"

class SDMode(Enum):
    EXPRESS_8 = "SD Express 8.0"
    EXPRESS_7 = "SD Express 7.0"
    UHS_II = "SD 4.0 UHS-II"
    UHS_I = "SD 3.0 UHS-I"
    SD_2 = "SD 2.0"

class SDController:
    def __init__(self):
        logger.info("初始化SD控制器")
        self.wmi = wmi.WMI()
        self.bayhub_vid = "VEN_1217"
        self.last_bayhub_info = None  # 保存历史的Bayhub控制器信息
        self.controller_capabilities = {
            "DEV_9860": ["SD 7.0/8.0", "SD 4.0", "SD 3.0"],
            "DEV_9861": ["SD 7.0/8.0", "SD 3.0"],
            "DEV_9862": ["SD 7.0/8.0", "SD 4.0", "SD 3.0"],
            "DEV_9863": ["SD 4.0", "SD 3.0"],
            "DEV_8620": ["SD 3.0"],
            "DEV_8621": ["SD 3.0"]
        }
        
    def check_compatibility(self, card_mode=None):
        """检查主机控制器兼容性"""
        try:
            # 获取控制器支持的所有模式
            supported_modes = self._get_controller_capabilities()
            current_mode = None
            
            # 如果提供了卡的模式，确定当前工作模式
            if card_mode:
                current_mode = self._determine_working_mode(card_mode, supported_modes)
                
            # 构建返回信息
            if supported_modes:
                info = f"控制器支持: {', '.join(supported_modes)}"
                if current_mode:
                    info += f"\n当前工作模式: {current_mode}"
                logger.info(info)
                return info
            else:
                logger.warning("未检测到支持的控制器")
                return None
                
        except Exception as e:
            logger.error(f"控制器兼容性检查失败: {str(e)}", exc_info=True)
            return None
            
    def _get_controller_capabilities(self):
        """获取控制器支持的所有模式"""
        try:
            # 首先获取所有PCIe设备的信息
            wmi = win32com.client.GetObject("winmgmts:")
            
            # 查找Bayhub控制器和NVMe控制器
            current_bayhub_info = None
            nvme_info = None
            
            # 从存储控制器中查找
            for controller in wmi.InstancesOf("Win32_SCSIController"):
                pcie_info = self._extract_pcie_info(controller.PNPDeviceID)
                if not pcie_info:
                    continue
                    
                # 记录设备信息
                device_id = controller.PNPDeviceID.upper()
                bus_id = pcie_info.get('bus')
                dev_id = pcie_info.get('device')
                
                logger.debug(f"存储控制器: {device_id}")
                logger.debug(f"Bus: {bus_id}, Device: {dev_id}")
                
                # 检查是否是Bayhub控制器
                if self.bayhub_vid in device_id:
                    current_bayhub_info = {
                        'bus': bus_id,
                        'device': dev_id,
                        'device_id': device_id
                    }
                    logger.info(f"找到当前Bayhub控制器: {device_id}")
                    # 更新历史信息
                    self.last_bayhub_info = current_bayhub_info
                    
                # 检查是否是NVMe控制器
                if "NVM" in controller.Name or "NVME" in device_id:
                    nvme_info = {
                        'bus': bus_id,
                        'device': dev_id,
                        'device_id': device_id,
                        'name': controller.Name
                    }
                    logger.info(f"找到NVMe控制器: {controller.Name}")
            
            # 如果找到了当前的Bayhub控制器
            if current_bayhub_info:
                for dev_id in self.controller_capabilities.keys():
                    if dev_id in current_bayhub_info['device_id']:
                        return self.controller_capabilities[dev_id]
            
            # 如果找到了NVMe控制器
            if nvme_info:
                # 首先检查是否与历史Bayhub控制器匹配，用于插拔卡后重新识别
                if self.last_bayhub_info:
                    if (nvme_info['bus'] == self.last_bayhub_info['bus'] and 
                        nvme_info['device'] == self.last_bayhub_info['device']):
                        logger.info("NVMe控制器与历史Bayhub控制器位置匹配")
                        # 从历史信息中获取控制器能力
                        for dev_id in self.controller_capabilities.keys():
                            if dev_id in self.last_bayhub_info['device_id']:
                                return self.controller_capabilities[dev_id]
                
                # 如果没有Bayhub控制器历史信息，说明初始状态是插入了SD Express卡
                else:  
                    logger.info("检测到SD Express NVMe控制器")
                    # 直接返回完整能力集
                    return ["SD Express"]
            
            logger.warning("未检测到支持的控制器")
            return None
            
        except Exception as e:
            logger.error(f"获取控制器能力失败: {str(e)}", exc_info=True)
            return None
            
    def _extract_pcie_info(self, pnp_device_id):
        """从PNPDeviceID提取PCIe信息"""
        try:
            # PNPDeviceID格式示例: PCI\VEN_1217&DEV_9860&SUBSYS_98601217&REV_00\3&11583659&0&E8
            # 其中3是bus number，E8是device number
            parts = pnp_device_id.split('\\')
            if len(parts) >= 3:
                location_info = parts[2]
                # 提取bus number和device number
                location_parts = location_info.split('&')
                if len(location_parts) >= 3:
                    bus_number = location_parts[0]  # 直接使用第一个数字作为bus number
                    device_number = location_parts[2]  # 最后一个部分是device number
                    
                    logger.debug(f"解析PCIe信息: {pnp_device_id}")
                    logger.debug(f"Bus Number: {bus_number}")
                    logger.debug(f"Device Number: {device_number}")
                    
                    return {
                        'bus': bus_number,
                        'device': device_number
                    }
            return None
        except Exception as e:
            logger.error(f"提取PCIe信息失败: {str(e)}", exc_info=True)
            return None
    
    def _determine_working_mode(self, card_mode, supported_modes):
        """根据卡模式和控制器支持的模式确定当前工作模式"""
        if not supported_modes:
            return None
            
        # 将卡模式映射到控制器支持的模式
        mode_mapping = {
            "8.0": "SD 7.0/8.0",  # 8.0卡在支持7.0/8.0的控制器上以8.0模式工作
            "7.0": "SD 7.0/8.0",  # 7.0卡在支持7.0/8.0的控制器上以7.0模式工作
            "4.0": "SD 4.0",
            "3.0": "SD 3.0"
        }
        
        # 从卡模式中提取版本号
        for version in mode_mapping:
            if version in card_mode:
                target_mode = mode_mapping[version]
                if target_mode in supported_modes:
                    return target_mode
                # 如果不支持目标模式，尝试降
                for supported_mode in supported_modes:
                    if "SD 7.0/8.0" in supported_mode:
                        continue  # 跳过Express模式的降级
                    if float(supported_mode.split()[1]) < float(version):
                        return supported_mode
                        
        return None
    
    def _check_nvme_controller(self):
        """检查NVMe控制器支持"""
        try:
            for controller in self.wmi.Win32_PnPEntity(["Name", "DeviceID"]):
                if "NVM" in controller.Name:
                    return True
            return False
        except Exception as e:
            logger.error(f"NVMe控制器检查错误: {str(e)}", exc_info=True)
            return False
    
    def _check_sd_controller(self):
        """检查Bayhub SD控制器支持"""
        try:
            for controller in self.wmi.Win32_PnPEntity():
                if (self.bayhub_vid in controller.DeviceID and 
                    "SD" in controller.Name):
                    return True
            return False
        except Exception as e:
            logger.error(f"SD控制器检查错误: {str(e)}", exc_info=True)
            return False
    
    def get_controller_type(self, device_path):
        """获取指定设备的控制器类型"""
        if device_path is None:
            logger.warning("设备路径为空，无法确定控制器类型")
            return ControllerType.SD_HOST
            
        if "NVME" in device_path.upper():
            logger.debug(f"检测到NVMe控制器: {device_path}")
            return ControllerType.NVME
            
        logger.debug(f"检测到SD Host控制器: {device_path}")
        return ControllerType.SD_HOST
    
    def get_controller_info(self):
        """获取控制器详细信息"""
        try:
            wmi = win32com.client.GetObject("winmgmts:")
            
            # 从存储控制器中查找
            for controller in wmi.InstancesOf("Win32_SCSIController"):
                # 检查是否是Bayhub控制器
                if self.bayhub_vid in controller.PNPDeviceID.upper():
                    capabilities = None
                    for dev_id in self.controller_capabilities.keys():
                        if dev_id in controller.PNPDeviceID.upper():
                            capabilities = self.controller_capabilities[dev_id]
                            break
                    
                    return {
                        'name': controller.Name,
                        'capabilities': capabilities
                    }
                
                # 检查是否是NVMe控制器
                if "NVM" in controller.Name or "NVME" in controller.PNPDeviceID.upper():
                    return {
                        'name': controller.Name,
                        'capabilities': ["SD Express"]
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"获取控制器信息失败: {str(e)}", exc_info=True)
            return None