import time
import win32file
import win32api
import win32com.client
import os
from .controller import ControllerType
from core.controller import SDController
from utils.logger import get_logger

logger = get_logger(__name__)

class CardInfo:
    def __init__(self):
        self.mode = None  # "8.0"/"7.0"/"4.0"/"3.0"
        self.controller_type = None
        self.device_path = None
        self.drive_letter = None
        self.capacity = 0  # Default value is 0
        self.name = None   # Add card name property
 
class CardOperations:
    def __init__(self, controller=None, sd_express_model=None):
        self.controller = controller
        self.timeout = 30
        self._last_card_info = None
        self.sd_express_model = sd_express_model
    def check_card(self, quick_mode=True):
        """Unified card detection entry
        Args:
            quick_mode: True for quick detection, False for full detection
        Returns:
            CardInfo: First valid SD card info found, returns None if not found
        """
        try:
            # Get all disk drives (including SD cards, USB devices, NVMe SD Express etc.)
            drives = self._get_drives()
            if not drives:
                return None

            # Iterate through all drives, find valid SD cards
            for drive_letter in drives:
                # Basic detection
                card_info = self._analyze_drive(drive_letter, full_check=False)
                if card_info:  # Found valid SD card
                    # Update card info in controller
                    self.controller.update_card_info(card_info)
                    # Check if full check is needed
                    if not quick_mode or self._is_card_changed(card_info):
                        detailed_card_info = self._analyze_drive(drive_letter, full_check=True)
                        if detailed_card_info:
                            self._last_card_info = detailed_card_info
                            return detailed_card_info
                    else:
                        # Use last performance info
                        if self._last_card_info and self._last_card_info.device_path == card_info.device_path:
                            card_info.mode = self._last_card_info.mode
                            card_info.capacity = self._last_card_info.capacity
                
                    self._last_card_info = card_info
                    return card_info

            # No valid SD card found
            if self._last_card_info:
                logger.info("SD card removed")
                self.controller.update_card_info(None)

            self._last_card_info = None
            return None

        except Exception as e:
            logger.error(f"Card detection failed: {str(e)}", exc_info=True)
            self._last_card_info = None
            return None
    
    def _analyze_drive(self, drive_letter, full_check=False):
        """Analyze drive and return card info
        Args:
            drive_letter: Drive letter
            full_check: Whether to perform full check (including performance test)
        """
        try:
            # Get device path
            device_path = self._get_device_path(drive_letter)
            if not device_path:
                return None

            # Basic device info detection
            card_info = self._detect_device_type(device_path, drive_letter)
            if not card_info:
                return None

            # If full check is needed, add detailed info
            if full_check:
                self._enhance_card_info(card_info)
            else:
                # Only get capacity info, no performance test
                card_info.capacity = self._get_drive_capacity(drive_letter)

            return card_info

        except Exception as e:
            logger.error(f"Drive analysis failed {drive_letter}: {str(e)}", exc_info=True)
            return None
        
    def _is_sd_express(self, disk):
        """Check if it's an SD Express card"""
        try:
            # Check device descriptor for features
            descriptors = [
                disk.Model,
                disk.Caption,
                disk.Description,
                disk.PNPDeviceID
            ]
            
            # Print device descriptor info
            logger.debug("Device descriptor info:")
            logger.debug(f"Model: {disk.Model}")
            logger.debug(f"Caption: {disk.Caption}")
            logger.debug(f"Description: {disk.Description}")
            logger.debug(f"PNPDeviceID: {disk.PNPDeviceID}")

            # Check if contains SSD keywords, if yes then it's an SSD drive not SD Express card
            # Note that not all vendor's SSD Model Name contains SSD keyword
            ssd_keywords = [
                "SSD",
            ]
            
            for desc in descriptors:
                if desc:
                    desc = desc.upper()
                    for keyword in ssd_keywords:
                        if keyword.upper() in desc:
                            logger.debug(f"Detected SSD keyword: {keyword}")
                            return False

            # SD Express card specific identifiers (not very effective, SD Express card may not contain these keywords)
            sd_express_keywords = [
                "SD EXPRESS",
                "SDEX",
                "SD-EXPRESS",
                "SD XS",
                "SDXC EXPRESS"
            ]
            
            # Check if SD Express features are present
            for desc in descriptors:
                if desc:
                    desc = desc.upper()
                    for keyword in sd_express_keywords:
                        if keyword in desc:
                            return True
                            
            # Check physical features (if available)
            if hasattr(disk, 'Size'):
                size_gb = int(disk.Size) / (1024**3)
                if size_gb <= 2048:  # SD Express card currently max 2TB
                    return True
                    
            return False
        
        except Exception as e:
            logger.error(f"SD Express detection failed: {str(e)}")
            return False
        
    def _detect_device_type(self, device_path, drive_letter):
        """Detect device type (NVMe/SD/USB) and return basic card info"""
        try:
            wmi = win32com.client.GetObject("winmgmts:")
            for disk in wmi.InstancesOf("Win32_DiskDrive"):
                if disk.DeviceID == device_path:
                    # Create basic card info object
                    card_info = CardInfo()
                    card_info.name = disk.Model
                    card_info.drive_letter = drive_letter
                    card_info.device_path = device_path

                    logger.debug(f"Disk media type: {disk.MediaType}")

                    # Check if it's a traditional SD card (excluding USB devices)
                    if "Removable Media" in disk.MediaType:
                        if ("USB" in disk.Model or 
                            "USB" in disk.Caption or 
                            "USB" in disk.Description):
                            return None

                        if ("SD" in disk.Model or 
                            "SD" in disk.Caption or 
                            "MMC" in disk.Model or 
                            "MMC" in disk.Caption or
                            "Card" in disk.Model or
                            "Card" in disk.Caption):
                            card_info.controller_type = ControllerType.SD_HOST
                            return card_info

                    # Check SD Express card (NVMe mode) or NVMe SSD.
                    # SD express card is not removable media, same as NVMe SSD.
                    if any(keyword in disk.Model.upper() or 
                           keyword in disk.Caption.upper() or
                           keyword in disk.PNPDeviceID.upper() 
                           for keyword in ["NVM", "NVME", "SD", "SDEX"]):
                        
                        # If specified SD Express model, directly match
                        if self.sd_express_model:
                            if self.sd_express_model.upper() in disk.Model.upper():
                                card_info.controller_type = ControllerType.NVME
                                card_info.is_sd_express = True
                                logger.info(f"Matched SD Express model: {disk.Model}")
                                return card_info
                            else:
                                # not match specified model, consider it as NVMe SSD
                                return None
                        
                        # If not specified SD Express model, use automatic logic to determine
                        else:
                            # check detailed info
                            if self._is_sd_express(disk):
                                card_info.controller_type = ControllerType.NVME
                                card_info.is_sd_express = True
                                return card_info
                            else:
                                return None

            return None

        except Exception as e:
            logger.error(f"Device type detection failed: {str(e)}", exc_info=True)
            return None
    
    def _enhance_card_info(self, card_info):
        """Enhance card info (add mode and capacity info)"""
        try:
            # Determine mode based on controller type
            if card_info.controller_type == ControllerType.NVME:
                card_info.mode = self._determine_express_mode(card_info.device_path)
            else:
                card_info.mode = self._determine_sd_mode(card_info.device_path)

            # Get capacity info
            card_info.capacity = self._get_drive_capacity(card_info.drive_letter)

        except Exception as e:
            logger.error(f"Failed to enhance card info: {str(e)}", exc_info=True)
    
    def _get_device_path(self, drive_letter):
        """Get device path of the drive"""
        try:
            # Use WMI to query device path
            wmi = win32com.client.GetObject("winmgmts:")
            for disk in wmi.InstancesOf("Win32_DiskDrive"):
                for partition in disk.Associators_("Win32_DiskDriveToDiskPartition"):
                    for logical_disk in partition.Associators_("Win32_LogicalDiskToPartition"):
                        if logical_disk.DeviceID.lower() == drive_letter[0].lower() + ":":
                            logger.debug(f"Found device path: {disk.DeviceID} for drive: {drive_letter}")
                            return disk.DeviceID
            
            logger.warning(f"Device path not found for drive {drive_letter}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting device path: {str(e)}", exc_info=True)
            return None
    
    def _is_card_changed(self, new_card_info):
        """Check if card info has changed"""
        # If last card info is None, consider it as a new card
        if not self._last_card_info:
            return True
            
        # Compare key attributes
        return (new_card_info.device_path != self._last_card_info.device_path or
                new_card_info.drive_letter != self._last_card_info.drive_letter or
                new_card_info.name != self._last_card_info.name)
    
    def _determine_express_mode(self, device_path):
        """Determine Express mode (7.0 or 8.0)"""
        try:
            # Use WMI to get detailed device info
            wmi = win32com.client.GetObject("winmgmts:")
            for disk in wmi.InstancesOf("Win32_DiskDrive"):
                if disk.DeviceID == device_path:
                    # Get device instance path
                    pnp_id = disk.PNPDeviceID
                    
                    # Get more info from device manager
                    for controller in wmi.InstancesOf("Win32_PnPEntity"):
                        if pnp_id in controller.PNPDeviceID:
                            # Check device properties and description
                            desc = controller.Description.upper() if controller.Description else ""
                            name = controller.Name.upper() if controller.Name else ""
                            
                            logger.debug(f"SD Express card device info: {desc} | {name}")
                            
                            # Check transfer rate to determine version
                            if hasattr(controller, 'MaximumTransferRate'):
                                rate = float(controller.MaximumTransferRate)
                                if rate >= 2000:  # Above 2GB/s considered as 8.0
                                    logger.info("Detected SD Express 8.0 card")
                                    return "8.0"
                                else:
                                    logger.info("Detected SD Express 7.0 card")
                                    return "7.0"
                            
                            # If unable to get rate, determine version from description
                            if "PCIE GEN4" in desc or "GEN 4" in desc:
                                logger.info("Detected SD Express 8.0 card based on PCIe version")
                                return "8.0"
                            elif "PCIE GEN3" in desc or "GEN 3" in desc:
                                logger.info("Detected SD Express 7.0 card based on PCIe version")
                                return "7.0"
            
            # If unable to determine specific version, return conservative estimate
            logger.warning("Unable to determine specific SD Express version, defaulting to 7.0")
            return "7.0"
            
        except Exception as e:
            logger.error(f"SD Express mode detection failed: {str(e)}", exc_info=True)
            return "7.0"  # Return conservative estimate on error
    
    def _determine_sd_mode(self, device_path):
        """Determine SD card mode through performance test (4.0/3.0/2.0)"""
        try:
            perf_info = self._get_disk_performance(device_path)
            if not perf_info:
                logger.error("Unable to get performance info")
                return "unknown"
            
            max_speed = perf_info['read_speed']
            logger.debug(f"Measured max speed: {max_speed:.2f}MB/s")
            
            # UHS-II speed range: FD156 is 156MB/s, HD312 is 312MB/s
            if max_speed >= 120:  # UHS-II minimum speed threshold
                logger.info(f"Based on speed({max_speed:.2f}MB/s) determined as SD 4.0 (UHS-II) card")
                return "4.0"
            # UHS-I speed range: SDR50 is 50MB/s, SDR104 is 104MB/s
            elif max_speed >= 30:  # UHS-I minimum speed threshold
                logger.info(f"Based on speed({max_speed:.2f}MB/s) determined as SD 3.0 (UHS-I) card")
                return "3.0"
            else:
                logger.info(f"Based on speed({max_speed:.2f}MB/s) determined as SD 2.0 card")
                return "2.0"
                
        except Exception as e:
            logger.error(f"SD card mode detection failed: {str(e)}", exc_info=True)
            return "unknown"  # Error

    def _get_disk_performance(self, device_path):
        """Get disk performance characteristics"""
        try:
            # Get drive letter
            drive_letter = None
            wmi = win32com.client.GetObject("winmgmts:")
            for disk in wmi.InstancesOf("Win32_DiskDrive"):
                if disk.DeviceID == device_path:
                    for partition in disk.Associators_("Win32_DiskDriveToDiskPartition"):
                        for logical_disk in partition.Associators_("Win32_LogicalDiskToPartition"):
                            drive_letter = logical_disk.DeviceID + "\\"
                            break
                    break
            
            if not drive_letter:
                logger.error("Unable to get drive letter")
                return None

            # Wait for disk activity to finish
            time.sleep(1)
            
            # Create test file
            test_file = os.path.join(drive_letter, "speed_test.bin")
            test_size = 4 * 1024 * 1024  # 4MB
            block_size = 1024 * 1024  # 1MB
            
            try:
                # First create and write test file
                with open(test_file, 'wb') as f:
                    f.write(os.urandom(test_size))
                
                # Perform read test
                max_read_speed = 0
                for _ in range(2):  # Test 3 times and take the maximum
                    handle = win32file.CreateFile(
                        test_file,
                        win32file.GENERIC_READ,
                        win32file.FILE_SHARE_READ,  # Allow shared read
                        None,
                        win32file.OPEN_EXISTING,
                        win32file.FILE_FLAG_NO_BUFFERING | 
                        win32file.FILE_FLAG_SEQUENTIAL_SCAN,
                        None
                    )
                    
                    # Use high-precision timer to avoid small data timing being considered as 0
                    start_time = time.perf_counter()  
                    bytes_read = 0
                    
                    while bytes_read < test_size:
                        win32file.ReadFile(handle, block_size)
                        bytes_read += block_size
                    
                    read_time = time.perf_counter() - start_time
                    read_speed = test_size / read_time / (1024 * 1024)  # MB/s
                    max_read_speed = max(max_read_speed, read_speed)
                    handle.Close()
                    
                    time.sleep(0.1)  # Wait between tests
                
                logger.debug(f"Performance test result: Read={max_read_speed:.1f}MB/s")
                return {'read_speed': max_read_speed}
                
            finally:
                # Clean up test file
                if os.path.exists(test_file):
                    try:
                        os.remove(test_file)
                    except:
                        pass
        
        except Exception as e:
            logger.error(f"Failed to get disk performance characteristics: {str(e)}", exc_info=True)
            return None
    
    def _get_drive_capacity(self, drive_letter):
        """Get drive capacity"""
        try:
            # Use GetDiskFreeSpaceEx to get total capacity
            free_bytes, total_bytes, total_free_bytes = win32file.GetDiskFreeSpaceEx(drive_letter)
            logger.debug(f"Drive {drive_letter} capacity info:")
            logger.debug(f"Total capacity: {total_bytes/1024/1024/1024:.1f}GB")
            logger.debug(f"Available space: {free_bytes/1024/1024/1024:.1f}GB")
            return total_bytes
        except Exception as e:
            logger.error(f"Error getting drive capacity: {str(e)}", exc_info=True)
            
            # Try alternative method
            try:
                # Use wmi query to get capacity
                wmi = win32com.client.GetObject("winmgmts:")
                for disk in wmi.InstancesOf("Win32_LogicalDisk"):
                    if disk.DeviceID.lower() == drive_letter[0].lower() + ":":
                        size = int(disk.Size)
                        logger.debug(f"Got drive {drive_letter} capacity through WMI: {size/1024/1024/1024:.1f}GB")
                        return size
            except Exception as e2:
                logger.error(f"WMI drive capacity query failed: {str(e2)}", exc_info=True)
            
            return 0
    
    def _get_drives(self):
        """Get all possible SD card drives (including removable drives and NVMe drives)"""
        try:
            drives = []
            bitmask = win32api.GetLogicalDrives()
            
            # Use WMI to query all disk information
            wmi = win32com.client.GetObject("winmgmts:")
            physical_disks = {disk.DeviceID: disk for disk in wmi.InstancesOf("Win32_DiskDrive")}
            
            for letter in range(26):
                if bitmask & (1 << letter):
                    drive_letter = f"{chr(65 + letter)}:\\"
                    drive_type = win32file.GetDriveType(drive_letter)
                    logger.debug(f"Checking drive {drive_letter}, type: {drive_type}")
                    
                    # NVMe SD Express cards are not Removable, hard to distinguish from NVMe SSD
                    # So here we return all disk drives and analyze in _analyze_drive
                    logger.debug(f"Found disk drive: {drive_letter} ")
                    drives.append(drive_letter)
            
            logger.debug(f"Scan complete, found drives: {drives}")
            return drives
            
        except Exception as e:
            logger.error(f"Error getting drives: {str(e)}", exc_info=True)
            return []
    
    def wait_for_card(self, timeout=300):
        """Wait for SD card insertion
        Args:
            timeout: Timeout in seconds
        Returns:
            CardInfo: Detected SD card info, returns None if timeout
        """
        try:
            logger.info(f"Waiting for SD card insertion, timeout: {timeout} seconds")
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                card_info = self.check_card()
                if card_info:
                    logger.info(f"SD card detected: {card_info}")
                    return card_info
                
                # Check every second
                time.sleep(1)
            
            logger.warning("Wait for SD card timeout")
            return None
            
        except Exception as e:
            logger.error(f"Error waiting for SD card: {str(e)}", exc_info=True)
            return None