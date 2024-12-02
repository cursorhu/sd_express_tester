import wmi
import win32com.client
from enum import Enum
from utils.logger import get_logger

logger = get_logger(__name__)

class ControllerType(Enum):
    NVME = "NVMe SD EXPRESS"
    SD_HOST = "SD Host"

class SDMode(Enum):
    SD_EXPRESS = "SD Express 7.0/8.0"
    UHS_II = "SD 4.0 UHS-II"
    UHS_I = "SD 3.0 UHS-I"
    SD_2 = "SD 2.0"

class SDController:
    def __init__(self):
        logger.debug("Initializing SD controller")
        self.wmi = wmi.WMI()
        self.bayhub_vid = "VEN_1217"
        self.last_bayhub_info = None  # Save historical Bayhub controller info
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
        """Get all modes supported by the controller"""
        try:
            # First, get all PCIe device information
            wmi = win32com.client.GetObject("winmgmts:")
            
            # Find Bayhub controller and NVMe controller
            current_bayhub_info = None
            nvme_info = None
            
            # Search from storage controllers
            for controller in wmi.InstancesOf("Win32_SCSIController"):
                pcie_info = self._extract_pcie_info(controller.PNPDeviceID)
                if not pcie_info:
                    continue
                    
                # Record device information
                device_id = controller.PNPDeviceID.upper()
                bus_id = pcie_info.get('bus')
                dev_id = pcie_info.get('device')
                
                logger.debug(f"Storage controller: {device_id}")
                logger.debug(f"Bus: {bus_id}, Device: {dev_id}")
                
                # Check if it's a Bayhub controller
                if self.bayhub_vid in device_id:
                    current_bayhub_info = {
                        'name': controller.Name,
                        'bus': bus_id,
                        'device': dev_id,
                        'device_id': device_id
                    }
                    logger.info(f"Found Bayhub controller: {device_id}")
                    # Update historical information
                    self.last_bayhub_info = current_bayhub_info
                    
                # Check if it's an NVMe controller
                if "NVM" in controller.Name or "NVME" in device_id:
                    nvme_info = {
                        'name': controller.Name,
                        'bus': bus_id,
                        'device': dev_id,
                        'device_id': device_id
                    }
                    logger.info(f"Found NVMe controller: {controller.Name}")
            
            # If the Bayhub controller is found
            if current_bayhub_info:
                for dev_id in self.controller_capabilities.keys():
                    if dev_id in current_bayhub_info['device_id']:
                        return {
                            'name': current_bayhub_info['name'],
                            'capabilities': self.controller_capabilities[dev_id]
                        }
            
            # If the NVMe controller is found
            if nvme_info:
                # First check if it matches historical Bayhub controller, used for re-detection after card insertion/removal
                if self.last_bayhub_info:
                    if (nvme_info['bus'] == self.last_bayhub_info['bus'] and 
                        nvme_info['device'] == self.last_bayhub_info['device']):
                        logger.info("NVMe controller matches historical Bayhub controller location")
                        return {
                            'name': nvme_info['name'],
                            'capabilities': ["SD Express"]
                        }
                
                # If no Bayhub controller history, there might be two cases:
                # 1. Initial state with SD Express card inserted, NVMe controller is NVMe SD Express
                # 2. Initial state without card, NVMe controller is platform's other NVMe SSD
                else:   
                    # If current card exists and is NVMe SD Express type
                    if (self.current_card_info and 
                        self.current_card_info.controller_type == ControllerType.NVME):
                        logger.info("Is NVMe SD Express controller")
                        return {
                            'name': nvme_info['name'],
                            'capabilities': ["SD Express"]
                        }
                    else:
                        # If no SD Express card detected, it's regular NVMe SSD
                        logger.info("Is NVMe SSD controller")
                        return None
                    
            logger.warning("No supported controller detected")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get controller capabilities: {str(e)}", exc_info=True)
            return None
        
    def update_card_info(self, card_info):
        """Update current card information"""
        self.current_card_info = card_info

    def _extract_pcie_info(self, pnp_device_id):
        """Extract PCIe information from PNPDeviceID"""
        try:
            # PNPDeviceID format example: PCI\VEN_1217&DEV_9860&SUBSYS_98601217&REV_00\3&11583659&0&E8
            # Where 3 is the bus number and E8 is the device number
            parts = pnp_device_id.split('\\')
            if len(parts) >= 3:
                location_info = parts[2]
                # Extract bus number and device number
                location_parts = location_info.split('&')
                if len(location_parts) >= 3:
                    bus_number = location_parts[0]  # Use the first number directly as the bus number
                    device_number = location_parts[2]  # The last part is the device number
                    
                    logger.debug(f"Parsing PCIe information: {pnp_device_id}")
                    logger.debug(f"Bus Number: {bus_number}")
                    logger.debug(f"Device Number: {device_number}")
                    
                    return {
                        'bus': bus_number,
                        'device': device_number
                    }
            return None
        except Exception as e:
            logger.error(f"Failed to extract PCIe information: {str(e)}", exc_info=True)
            return None
    
