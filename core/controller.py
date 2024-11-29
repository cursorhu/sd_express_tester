import wmi
import win32com.client
from enum import Enum
from utils.logger import get_logger

logger = get_logger(__name__)

class ControllerType(Enum):
    NVME = "NVMe SD EXPRESS"
    SD_HOST = "SD Host"

class SDMode(Enum):
    EXPRESS_8 = "SD Express 8.0"
    EXPRESS_7 = "SD Express 7.0"
    UHS_II = "SD 4.0 UHS-II"
    UHS_I = "SD 3.0 UHS-I"
    SD_2 = "SD 2.0"

class SDController:
    def __init__(self):
        logger.debug("初始化SD控制器")
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
        self.current_card_info = None

    def _controller_info(self):
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
                        'name': controller.Name,
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
                        'name': controller.Name,
                        'bus': bus_id,
                        'device': dev_id,
                        'device_id': device_id
                    }
                    logger.info(f"找到NVMe控制器: {controller.Name}")
            
            # 如果找到了当前的Bayhub控制器
            if current_bayhub_info:
                for dev_id in self.controller_capabilities.keys():
                    if dev_id in current_bayhub_info['device_id']:
                        return {
                            'name': current_bayhub_info['name'],
                            'capabilities': self.controller_capabilities[dev_id]
                        }
            
            # 如果找到了NVMe控制器
            if nvme_info:
                # 首先检查是否与历史Bayhub控制器匹配，用于插拔卡后重新识别
                if self.last_bayhub_info:
                    if (nvme_info['bus'] == self.last_bayhub_info['bus'] and 
                        nvme_info['device'] == self.last_bayhub_info['device']):
                        logger.info("NVMe控制器与历史Bayhub控制器位置匹配")
                        # 从历史信息中获取控制器能力
                        # for dev_id in self.controller_capabilities.keys():
                        #     if dev_id in self.last_bayhub_info['device_id']:
                        #         return {
                        #             'name': nvme_info['name'],
                        #             'capabilities': self.controller_capabilities[dev_id]
                        #         }
                        return {
                            'name': nvme_info['name'],
                            'capabilities': ["SD Express"]
                        }
                
                # 如果没有Bayhub控制器历史信息，可能有两种情况：
                # 1. 初始状态已经插入SD Express卡，此时NVMe控制器是NVMe SD Express
                # 2. 初始状态没有插入卡，NVMe控制器是平台其他的NVMe SSD.
                else:   
                    # 如果当前有卡且卡类型为NVMe SD Express
                    if (self.current_card_info and 
                        self.current_card_info.controller_type == ControllerType.NVME):
                        logger.info("是NVMe SD Express控制器")
                        return {
                            'name': nvme_info['name'],
                            'capabilities': ["SD Express"]
                        }
                    else:
                        # 如果没有检测到SD Express卡，说明是普通NVMe SSD
                        logger.info("是NVMe SSD控制器")
                        return None
                    
            logger.warning("未检测到支持的控制器")
            return None
            
        except Exception as e:
            logger.error(f"获取控制器能力失败: {str(e)}", exc_info=True)
            return None
        
    def update_card_info(self, card_info):
        """更新当前卡信息"""
        self.current_card_info = card_info

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
    
